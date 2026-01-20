"""
View Records Tab - Phase 2

Responsibilities:
- Fetch trades from database
- Display all trades in table
- Filter by equity, trade type, date range
- Allow edit trade (update existing record)
- Allow soft delete (set is_active = 0)

Does NOT:
- Calculate FIFO
- Calculate P/L
- Prevent oversells
- Auto-fix data
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import sqlite3
import csv
from pathlib import Path
from typing import Callable, Optional
from core.logger import get_logger
from core.utils import format_money

logger = get_logger('ui.view_records_tab')

CALENDAR_AVAILABLE: bool
try:
    from tkcalendar import DateEntry  # type: ignore
    CALENDAR_AVAILABLE = True
except ImportError:
    DateEntry = None  # type: ignore
    CALENDAR_AVAILABLE = False
    logger.warning("tkcalendar not installed - using text entry for dates")


class ViewRecordsTab:
    """View Records tab - display and manage trade records."""
    
    def __init__(self, parent: ttk.Frame, status_callback: Callable[[str], None]) -> None:
        logger.info("Initializing View Records tab")
        self.parent = parent
        self.update_status = status_callback
        self.selected_trade_id: Optional[int] = None
        self.show_deleted_trades = tk.BooleanVar(value=False)
        
        # Create UI
        self.create_widgets()
        
        # Load initial data
        self.refresh_records()
        logger.debug("View Records tab initialized")
    
    def create_widgets(self) -> None:
        """Create all UI widgets for View Records tab."""
        
        # Main container
        main_frame = ttk.Frame(self.parent, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Header
        header = ttk.Label(
            main_frame,
            text="VIEW TRADE RECORDS",
            font=('Consolas', 16, 'bold')
        )
        header.pack(pady=(0, 10))
        
        # Filter section
        self.create_filter_section(main_frame)
        
        # Table section
        self.create_table_section(main_frame)
        
        # Button section
        self.create_button_section(main_frame)
    
    def create_filter_section(self, parent: ttk.Frame) -> None:
        """Create filter controls."""
        
        filter_frame = ttk.LabelFrame(parent, text="Filters", padding="10")
        filter_frame.pack(fill='x', pady=(0, 10))
        
        # Row 1: Equity and Trade Type
        row1 = ttk.Frame(filter_frame)
        row1.pack(fill='x', pady=5)
        
        # Equity filter
        ttk.Label(row1, text="Stock:", font=('Arial', 9)).pack(side='left', padx=(0, 5))
        self.equity_filter = ttk.Combobox(row1, width=15, state='readonly')
        self.equity_filter.pack(side='left', padx=(0, 20))
        self.equity_filter.set("All")
        
        # Trade Type filter
        ttk.Label(row1, text="Type:", font=('Arial', 9)).pack(side='left', padx=(0, 5))
        self.type_filter = ttk.Combobox(row1, width=10, state='readonly', values=["All", "BUY", "SELL"])
        self.type_filter.pack(side='left', padx=(0, 20))
        self.type_filter.set("All")
        
        # Show deleted toggle
        self.show_deleted_check = ttk.Checkbutton(
            row1,
            text="Show Deleted",
            variable=self.show_deleted_trades,
            command=self.refresh_records
        )
        self.show_deleted_check.pack(side='left', padx=(0, 20))
        
        # Apply button
        ttk.Button(row1, text="Apply Filters", command=self.apply_filters, width=12).pack(side='left', padx=10)
        ttk.Button(row1, text="Clear Filters", command=self.clear_filters, width=12).pack(side='left')
        
        # Row 2: Date Range Filter
        row2 = ttk.Frame(filter_frame)
        row2.pack(fill='x', pady=5)
        
        ttk.Label(row2, text="From:", font=('Arial', 9)).pack(side='left', padx=(0, 5))
        
        if CALENDAR_AVAILABLE:
            # Use calendar picker
            self.date_from_entry = DateEntry(
                row2,
                width=12,
                background='darkblue',
                foreground='white',
                borderwidth=2,
                date_pattern='dd-mm-yyyy',
                font=('Arial', 9)
            )
            self.date_from_entry.pack(side='left', padx=(0, 15))
        else:
            # Fallback to text entry
            self.date_from_entry = ttk.Entry(row2, width=12)
            self.date_from_entry.pack(side='left', padx=(0, 5))
            self.date_from_entry.bind('<FocusOut>', lambda e: self.validate_date_field(self.date_from_entry))
            ttk.Label(row2, text="(DD-MM-YYYY)", font=('Arial', 8), foreground='gray').pack(side='left', padx=(0, 15))
        
        ttk.Label(row2, text="To:", font=('Arial', 9)).pack(side='left', padx=(0, 5))
        
        if CALENDAR_AVAILABLE:
            # Use calendar picker
            self.date_to_entry = DateEntry(
                row2,
                width=12,
                background='darkblue',
                foreground='white',
                borderwidth=2,
                date_pattern='dd-mm-yyyy',
                font=('Arial', 9)
            )
            self.date_to_entry.pack(side='left')
        else:
            # Fallback to text entry
            self.date_to_entry = ttk.Entry(row2, width=12)
            self.date_to_entry.pack(side='left', padx=(0, 5))
            self.date_to_entry.bind('<FocusOut>', lambda e: self.validate_date_field(self.date_to_entry))
            ttk.Label(row2, text="(DD-MM-YYYY)", font=('Arial', 8), foreground='gray').pack(side='left')
    
    def create_table_section(self, parent: ttk.Frame) -> None:
        """Create table to display records."""
        
        # Table frame with scrollbars
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical")
        hsb = ttk.Scrollbar(table_frame, orient="horizontal")
        
        # Treeview
        columns = ('ID', 'Date', 'Stock', 'Type', 'Qty', 'Price', 'Brokerage', 'Notes', 'Status')
        self.records_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show='headings',
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )
        
        vsb.config(command=self.records_tree.yview)
        hsb.config(command=self.records_tree.xview)
        
        # Configure columns
        self.records_tree.heading('ID', text='ID')
        self.records_tree.heading('Date', text='Date')
        self.records_tree.heading('Stock', text='Stock')
        self.records_tree.heading('Type', text='Type')
        self.records_tree.heading('Qty', text='Qty')
        self.records_tree.heading('Price', text='Price (₹)')
        self.records_tree.heading('Brokerage', text='Brokerage (₹)')
        self.records_tree.heading('Notes', text='Notes')
        self.records_tree.heading('Status', text='Status')
        
        self.records_tree.column('ID', width=50, anchor='center')
        self.records_tree.column('Date', width=100, anchor='center')
        self.records_tree.column('Stock', width=80, anchor='center')
        self.records_tree.column('Type', width=60, anchor='center')
        self.records_tree.column('Qty', width=60, anchor='center')
        self.records_tree.column('Price', width=100, anchor='e')
        self.records_tree.column('Brokerage', width=100, anchor='e')
        self.records_tree.column('Notes', width=200, anchor='w')
        self.records_tree.column('Status', width=80, anchor='center')
        
        # Grid layout
        self.records_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click to inline edit
        self.records_tree.bind('<Double-Button-1>', self.on_double_click)
        
        # Bind selection
        self.records_tree.bind('<<TreeviewSelect>>', self.on_select)
        
        # Bind mousewheel for scrolling
        self.records_tree.bind('<MouseWheel>', lambda e: self.records_tree.yview_scroll(int(-1*(e.delta/120)), "units"))
    
    def create_button_section(self, parent: ttk.Frame) -> None:
        """Create action buttons."""
        
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill='x')
        
        ttk.Button(
            button_frame,
            text="Refresh",
            command=self.refresh_records,
            width=15
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="✏️ Edit Trade",
            command=self.edit_selected_trade,
            width=15
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="Delete Trade",
            command=self.delete_selected_trade,
            width=15
        ).pack(side='left', padx=5)
        
        # Separator
        ttk.Separator(button_frame, orient='vertical').pack(side='left', fill='y', padx=10)
        
        ttk.Button(
            button_frame,
            text="💾 Backup DB",
            command=self.backup_database,
            width=15
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="📥 Restore DB",
            command=self.restore_database,
            width=15
        ).pack(side='left', padx=5)
        
        # Separator
        ttk.Separator(button_frame, orient='vertical').pack(side='left', fill='y', padx=10)
        
        ttk.Button(
            button_frame,
            text="💾 Export CSV",
            command=self.export_to_csv,
            width=15
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="📄 Export Excel",
            command=self.export_to_excel,
            width=15
        ).pack(side='left', padx=5)
        
        # Info label
        self.info_label = ttk.Label(button_frame, text="", font=('Arial', 9), foreground='blue')
        self.info_label.pack(side='right', padx=10)
    
    def load_equity_list(self) -> None:
        """Load unique equity list for filter dropdown."""
        try:
            conn = sqlite3.connect('data/trades.db')
            c = conn.cursor()
            c.execute("SELECT DISTINCT equity FROM trade_events ORDER BY equity")
            equities = [row[0] for row in c.fetchall()]
            conn.close()
            
            self.equity_filter['values'] = ["All"] + equities
            logger.debug(f"Loaded {len(equities)} unique equities for filter")
        except Exception as e:
            logger.error(f"Failed to load equity list: {str(e)}", exc_info=True)
    
    def refresh_records(self) -> None:
        """Load all trade records from database."""
        logger.info("Refreshing trade records")
        
        # Clear existing items
        for item in self.records_tree.get_children():
            self.records_tree.delete(item)
        
        try:
            # Load equity list for filter
            self.load_equity_list()
            
            # Build query based on filters
            query = """
                SELECT id, trade_date, equity, trade_type, quantity, price, brokerage, notes, is_active
                FROM trade_events
                WHERE 1=1
            """
            params = []
            
            # Apply filters
            equity_filter = self.equity_filter.get()
            if equity_filter and equity_filter != "All":
                query += " AND equity = ?"
                params.append(equity_filter)
            
            type_filter = self.type_filter.get()
            if type_filter and type_filter != "All":
                query += " AND trade_type = ?"
                params.append(type_filter)
            
            # Date range filter
            date_from = self.date_from_entry.get().strip()
            date_to = self.date_to_entry.get().strip()
            
            if date_from:
                try:
                    # Convert DD-MM-YYYY to YYYY-MM-DD
                    day, month, year = date_from.split('-')
                    date_from_db = f"{year}-{month}-{day}"
                    query += " AND trade_date >= ?"
                    params.append(date_from_db)
                except ValueError:
                    logger.warning(f"Invalid date format for 'from': {date_from}")
            
            if date_to:
                try:
                    # Convert DD-MM-YYYY to YYYY-MM-DD
                    day, month, year = date_to.split('-')
                    date_to_db = f"{year}-{month}-{day}"
                    query += " AND trade_date <= ?"
                    params.append(date_to_db)
                except ValueError:
                    logger.warning(f"Invalid date format for 'to': {date_to}")
            
            # Apply deleted filter based on checkbox
            if not self.show_deleted_trades.get():
                query += " AND is_active = 1"  # Only show active trades
            # If checkbox is checked, show all (active + deleted)
            
            query += " ORDER BY id DESC"
            
            # Execute query
            conn = sqlite3.connect('data/trades.db')
            c = conn.cursor()
            c.execute(query, params)
            trades = c.fetchall()
            conn.close()
            
            logger.debug(f"Loaded {len(trades)} trade records")
            
            # Populate table
            for trade in trades:
                trade_id, trade_date, equity, trade_type, quantity, price_paise, brokerage_paise, notes, is_active = trade
                
                # Format date DD-MM-YYYY
                year, month, day = trade_date.split('-')
                display_date = f"{day}-{month}-{year}"
                
                # Status
                status = "Active" if is_active == 1 else "Deleted"
                
                # Insert into tree
                item = self.records_tree.insert('', 'end', values=(
                    trade_id,
                    display_date,
                    equity,
                    trade_type,
                    quantity,
                    format_money(price_paise),
                    format_money(brokerage_paise),
                    notes[:50] + "..." if len(notes) > 50 else notes,
                    status
                ))
                
                # Apply visual styling
                if is_active == 0:
                    # Deleted rows: gray text
                    self.records_tree.item(item, tags=('deleted',))
                elif trade_type == 'SELL':
                    # SELL rows: light red background
                    self.records_tree.item(item, tags=('sell',))
                elif trade_type == 'BUY':
                    # BUY rows: light green background
                    self.records_tree.item(item, tags=('buy',))
            
            # Configure tag colors
            self.records_tree.tag_configure('deleted', foreground='gray')
            self.records_tree.tag_configure('sell', background='#ffe6e6')  # Light red
            self.records_tree.tag_configure('buy', background='#e6ffe6')   # Light green
            
            # Update info label
            self.info_label.config(text=f"Total: {len(trades)} records")
            self.update_status(f"Loaded {len(trades)} trade records")
            
        except Exception as e:
            logger.error(f"Failed to load records: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load records:\n{str(e)}")
            self.update_status("❌ Error loading records")
    
    def apply_filters(self) -> None:
        """Apply current filters and refresh."""
        date_from = self.date_from_entry.get().strip()
        date_to = self.date_to_entry.get().strip()
        logger.info(f"Applying filters - Equity: {self.equity_filter.get()}, Type: {self.type_filter.get()}, Date: {date_from} to {date_to}, Show Deleted: {self.show_deleted_trades.get()}")
        self.refresh_records()
    
    def validate_date_field(self, entry: ttk.Entry) -> bool:
        """Validate date format in entry field. Clear if invalid."""
        value = entry.get().strip()
        if not value:
            return True
        
        try:
            day, month, year = value.split('-')
            if len(day) != 2 or len(month) != 2 or len(year) != 4:
                raise ValueError("Invalid format")
            # Basic range check
            if not (1 <= int(day) <= 31 and 1 <= int(month) <= 12 and 1900 <= int(year) <= 2100):
                raise ValueError("Invalid date range")
            return True
        except (ValueError, AttributeError):
            messagebox.showwarning("Invalid Date", f"Please enter date in DD-MM-YYYY format\n(e.g., 20-01-2026)")
            entry.delete(0, tk.END)
            return False
    
    def clear_filters(self) -> None:
        """Clear all filters and refresh."""
        logger.info("Clearing all filters")
        self.equity_filter.set("All")
        self.type_filter.set("All")
        
        # Clear date fields (handle both DateEntry and Entry widgets)
        if CALENDAR_AVAILABLE:
            self.date_from_entry.set_date('')  # Clear DateEntry
            self.date_to_entry.set_date('')
        else:
            self.date_from_entry.delete(0, tk.END)
            self.date_to_entry.delete(0, tk.END)
        
        self.show_deleted_trades.set(False)
        self.refresh_records()
    
    def on_select(self, event: tk.Event) -> None:  # type: ignore
        """Handle row selection."""
        selection = self.records_tree.selection()
        if selection:
            item = self.records_tree.item(selection[0])
            self.selected_trade_id = item['values'][0]
            logger.debug(f"Selected trade ID: {self.selected_trade_id}")
    
    def edit_selected_trade(self) -> None:
        """Open edit dialog for selected trade."""
        selection = self.records_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trade to edit")
            return
        
        item = self.records_tree.item(selection[0])
        trade_id = item['values'][0]
        status = item['values'][8]  # Status column
        
        # Prevent editing deleted trades
        if status == "Deleted":
            logger.warning(f"Attempted to edit deleted trade ID: {trade_id}")
            messagebox.showwarning(
                "Cannot Edit",
                "Cannot edit a deleted trade.\n\nPlease restore it first (feature coming soon)."
            )
            return
        
        logger.info(f"Opening edit dialog for trade ID: {trade_id}")
        
        # Fetch full trade details
        try:
            conn = sqlite3.connect('data/trades.db')
            c = conn.cursor()
            c.execute("""
                SELECT trade_date, equity, trade_type, quantity, price, brokerage, notes, is_active
                FROM trade_events
                WHERE id = ?
            """, (trade_id,))
            trade = c.fetchone()
            conn.close()
            
            if not trade:
                messagebox.showerror("Error", "Trade not found")
                return
            
            # Confirm editing (UX warning)
            trade_date = trade[0]
            result = messagebox.askyesno(
                "Confirm Edit",
                f"You are about to edit trade #{trade_id} from {trade_date}.\n\n"
                f"⚠️ Warning: Editing historical trades may affect your P/L calculations.\n\n"
                f"Do you want to continue?"
            )
            
            if not result:
                logger.info(f"Edit cancelled by user for trade ID: {trade_id}")
                return
            
            # Open edit dialog
            EditTradeDialog(self.parent, int(trade_id), trade, self.refresh_records, self.update_status)
            
        except Exception as e:
            logger.error(f"Failed to load trade for editing: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load trade:\n{str(e)}")
    
    def delete_selected_trade(self) -> None:
        """Soft delete selected trade (set is_active = 0)."""
        selection = self.records_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a trade to delete")
            return
        
        item = self.records_tree.item(selection[0])
        trade_id = item['values'][0]
        trade_info = f"{item['values'][3]} {item['values'][4]} {item['values'][2]} on {item['values'][1]}"
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete this trade?\n\n{trade_info}\n\nThis will set is_active = 0 (soft delete)."
        )
        
        if not result:
            logger.info(f"Delete cancelled by user for trade ID: {trade_id}")
            return
        
        try:
            logger.info(f"Soft deleting trade ID: {trade_id}")
            conn = sqlite3.connect('data/trades.db')
            c = conn.cursor()
            c.execute("UPDATE trade_events SET is_active = 0 WHERE id = ?", (trade_id,))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Trade ID {trade_id} soft deleted successfully")
            self.update_status(f"✅ Trade deleted: {trade_info}")
            messagebox.showinfo("Success", "Trade deleted successfully")
            
            # Refresh
            self.refresh_records()
            
        except Exception as e:
            logger.error(f"Failed to delete trade: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to delete trade:\n{str(e)}")
            self.update_status("❌ Error deleting trade")
    
    def on_double_click(self, event: tk.Event) -> None:  # type: ignore
        """Handle double-click for inline editing."""
        # Identify column and item
        region = self.records_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        
        column = self.records_tree.identify_column(event.x)
        item = self.records_tree.identify_row(event.y)
        
        if not item:
            return
        
        # Get column name
        col_index = int(column[1:]) - 1  # #1 -> 0, #2 -> 1, etc.
        columns = ('ID', 'Date', 'Stock', 'Type', 'Qty', 'Price', 'Brokerage', 'Notes', 'Status')
        col_name = columns[col_index]
        
        # Don't allow editing ID or Status columns
        if col_name in ('ID', 'Status'):
            logger.debug(f"Inline edit: Column {col_name} is readonly")
            return
        
        # Check if trade is deleted
        values = self.records_tree.item(item, 'values')
        if values[8] == "Deleted":  # Status column
            messagebox.showwarning("Cannot Edit", "Cannot edit a deleted trade.")
            return
        
        logger.info(f"Inline edit: Starting edit for item {item}, column {col_name}")
        self.start_inline_edit(item, col_index, col_name)
    
    def start_inline_edit(self, item: str, col_index: int, col_name: str) -> None:
        """Start inline editing of a cell."""
        # Get cell position
        bbox = self.records_tree.bbox(item, col_index)
        if not bbox:
            return
        
        x, y, width, height = bbox
        current_value = self.records_tree.item(item, 'values')[col_index]
        
        # Remove currency symbols for editing
        if col_name in ('Price', 'Brokerage'):
            current_value = current_value.replace('₹', '').strip()
        
        # Create entry widget for inline editing
        if col_name == 'Notes':
            # For Notes, use a larger entry
            edit_entry = ttk.Entry(self.records_tree, width=40)
        elif col_name == 'Type':
            # For Type, use combobox
            edit_entry = ttk.Combobox(self.records_tree, width=10, values=['BUY', 'SELL'], state='readonly')
        else:
            edit_entry = ttk.Entry(self.records_tree)
        
        edit_entry.insert(0, current_value)
        edit_entry.select_range(0, tk.END)
        edit_entry.place(x=x, y=y, width=width, height=height)
        edit_entry.focus()
        
        # Save on Enter or focus loss
        def save_edit(event=None):
            new_value = edit_entry.get()
            edit_entry.destroy()
            self.update_inline_edit(item, col_index, col_name, new_value)
        
        def cancel_edit(event=None):
            edit_entry.destroy()
        
        edit_entry.bind('<Return>', save_edit)
        edit_entry.bind('<FocusOut>', save_edit)
        edit_entry.bind('<Escape>', cancel_edit)
    
    def update_inline_edit(self, item: str, col_index: int, col_name: str, new_value: str) -> None:
        """Update database with inline edited value."""
        try:
            values = self.records_tree.item(item, 'values')
            trade_id = values[0]
            
            logger.info(f"Inline edit: Updating trade ID {trade_id}, column {col_name} to '{new_value}'")
            
            # Map column name to database field
            column_map = {
                'Date': ('trade_date', 'date'),
                'Stock': ('equity', 'text'),
                'Type': ('trade_type', 'text'),
                'Qty': ('quantity', 'int'),
                'Price': ('price', 'money'),
                'Brokerage': ('brokerage', 'money'),
                'Notes': ('notes', 'text')
            }
            
            if col_name not in column_map:
                return
            
            db_field, value_type = column_map[col_name]
            
            # Convert value based on type
            if value_type == 'date':
                # DD-MM-YYYY -> YYYY-MM-DD
                day, month, year = new_value.split('-')
                db_value = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            elif value_type == 'int':
                db_value = int(new_value)
            elif value_type == 'money':
                # Convert rupees to paise
                db_value = int(float(new_value) * 100)
            elif value_type == 'text':
                db_value = new_value.strip().upper() if col_name in ('Stock', 'Type') else new_value.strip()
            else:
                db_value = new_value
            
            # Update database
            conn = sqlite3.connect('data/trades.db')
            c = conn.cursor()
            c.execute(f"UPDATE trade_events SET {db_field} = ? WHERE id = ?", (db_value, trade_id))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Inline edit: Trade ID {trade_id} updated successfully")
            self.update_status(f"✅ Updated trade #{trade_id}")
            
            # Refresh display
            self.refresh_records()
            
        except Exception as e:
            logger.error(f"Inline edit failed: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to update:\n{str(e)}")
    
    def export_to_csv(self) -> None:
        """Export current filtered records to CSV."""
        logger.info("Exporting records to CSV")
        
        try:
            # Get timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"trades_export_{timestamp}.csv"
            filepath = Path("data") / "exports" / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Get all displayed rows
            rows = []
            for item in self.records_tree.get_children():
                values = self.records_tree.item(item, 'values')
                rows.append(values)
            
            if not rows:
                messagebox.showwarning("No Data", "No records to export")
                return
            
            # Write CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Header
                writer.writerow(['ID', 'Date', 'Stock', 'Type', 'Qty', 'Price', 'Brokerage', 'Notes', 'Status'])
                # Data
                writer.writerows(rows)
            
            logger.info(f"✅ Exported {len(rows)} records to {filepath}")
            self.update_status(f"✅ Exported to {filename}")
            messagebox.showinfo("Export Successful", f"Exported {len(rows)} records to:\n{filepath}")
            
        except Exception as e:
            logger.error(f"CSV export failed: {str(e)}", exc_info=True)
            messagebox.showerror("Export Failed", f"Failed to export CSV:\n{str(e)}")
    
    def export_to_excel(self) -> None:
        """Export current filtered records to Excel."""
        logger.info("Exporting records to Excel")
        
        try:
            # Try importing openpyxl
            try:
                from openpyxl import Workbook
                from openpyxl.styles import Font, PatternFill, Alignment
            except ImportError:
                logger.warning("openpyxl not installed")
                messagebox.showerror(
                    "Missing Dependency",
                    "openpyxl is required for Excel export.\n\n"
                    "Install it with:\npip install openpyxl"
                )
                return
            
            # Get timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"trades_export_{timestamp}.xlsx"
            filepath = Path("data") / "exports" / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Get all displayed rows
            rows = []
            for item in self.records_tree.get_children():
                values = self.records_tree.item(item, 'values')
                rows.append(values)
            
            if not rows:
                messagebox.showwarning("No Data", "No records to export")
                return
            
            # Create workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Trades"
            
            # Header row
            headers = ['ID', 'Date', 'Stock', 'Type', 'Qty', 'Price', 'Brokerage', 'Notes', 'Status']
            ws.append(headers)
            
            # Style header
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            if ws:  # Type guard for openpyxl worksheet
                for cell in ws[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center")
            
            # Data rows
            for row in rows:
                ws.append(row)
            
            # Auto-width columns
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Save
            wb.save(filepath)
            
            logger.info(f"✅ Exported {len(rows)} records to {filepath}")
            self.update_status(f"✅ Exported to {filename}")
            messagebox.showinfo("Export Successful", f"Exported {len(rows)} records to:\n{filepath}")
            
        except Exception as e:
            logger.error(f"Excel export failed: {str(e)}", exc_info=True)
            messagebox.showerror("Export Failed", f"Failed to export Excel:\n{str(e)}")
    
    def backup_database(self) -> None:
        """Create a timestamped backup of the database."""
        logger.info("Creating database backup")
        
        try:
            import shutil
            from tkinter import filedialog
            
            # Generate default filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"trades_backup_{timestamp}.db"
            
            # Ask user where to save
            filepath = filedialog.asksaveasfilename(
                title="Save Database Backup",
                defaultextension=".db",
                initialfile=default_filename,
                filetypes=[("Database files", "*.db"), ("All files", "*.*")]
            )
            
            if not filepath:
                logger.info("Backup cancelled by user")
                return
            
            # Copy database file
            shutil.copy2("data/trades.db", filepath)
            
            logger.info(f"✅ Database backed up to: {filepath}")
            self.update_status(f"✅ Backup saved: {Path(filepath).name}")
            messagebox.showinfo("Backup Successful", f"Database backed up to:\n{filepath}")
            
        except Exception as e:
            logger.error(f"Backup failed: {str(e)}", exc_info=True)
            messagebox.showerror("Backup Failed", f"Failed to backup database:\n{str(e)}")
    
    def restore_database(self) -> None:
        """Restore database from a backup file."""
        logger.info("Restoring database from backup")
        
        try:
            import shutil
            from tkinter import filedialog
            
            # Warn user
            result = messagebox.askyesno(
                "Confirm Restore",
                "⚠️ WARNING: This will replace your current database!\n\n"
                "All current trades will be replaced with the backup data.\n\n"
                "It's recommended to create a backup of your current database first.\n\n"
                "Do you want to continue?"
            )
            
            if not result:
                logger.info("Restore cancelled by user")
                return
            
            # Ask user to select backup file
            filepath = filedialog.askopenfilename(
                title="Select Backup File to Restore",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")]
            )
            
            if not filepath:
                logger.info("Restore cancelled - no file selected")
                return
            
            # Create a safety backup of current database
            safety_backup = f"data/trades_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2("data/trades.db", safety_backup)
            logger.info(f"Created safety backup: {safety_backup}")
            
            # Restore from backup
            shutil.copy2(filepath, "data/trades.db")
            
            logger.info(f"✅ Database restored from: {filepath}")
            self.update_status("✅ Database restored")
            messagebox.showinfo(
                "Restore Successful",
                f"Database restored from:\n{filepath}\n\n"
                f"Safety backup created:\n{safety_backup}\n\n"
                "Refreshing records..."
            )
            
            # Refresh display
            self.refresh_records()
            
        except Exception as e:
            logger.error(f"Restore failed: {str(e)}", exc_info=True)
            messagebox.showerror("Restore Failed", f"Failed to restore database:\n{str(e)}")


class EditTradeDialog:
    """Dialog for editing trade details."""
    
    def __init__(self, parent, trade_id: int, trade_data: tuple, refresh_callback: Callable, status_callback: Callable):
        self.trade_id = trade_id
        self.refresh_callback = refresh_callback
        self.update_status = status_callback
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit Trade #{trade_id}")
        self.dialog.geometry("550x500")
        self.dialog.resizable(False, False)  # Prevent accidental resizing
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Unpack trade data
        trade_date, equity, trade_type, quantity, price_paise, brokerage_paise, notes, _ = trade_data
        
        # Convert for display
        price_rupees = price_paise / 100
        brokerage_rupees = brokerage_paise / 100
        year, month, day = trade_date.split('-')
        display_date = f"{day}-{month}-{year}"
        
        # Create form
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text=f"EDIT TRADE #{trade_id}", font=('Consolas', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        row = 1
        
        # Trade ID (readonly display)
        ttk.Label(main_frame, text="Trade ID:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        id_display = ttk.Label(main_frame, text=f"#{trade_id}", font=('Consolas', 10, 'bold'), foreground='blue')
        id_display.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        row += 1
        
        # Date
        ttk.Label(main_frame, text="Date:", font=('Arial', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.date_entry = ttk.Entry(main_frame, width=25)
        self.date_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.date_entry.insert(0, display_date)
        row += 1
        
        # Equity
        ttk.Label(main_frame, text="Stock:", font=('Arial', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.equity_entry = ttk.Entry(main_frame, width=25)
        self.equity_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.equity_entry.insert(0, equity)
        row += 1
        
        # Trade Type
        ttk.Label(main_frame, text="Type:", font=('Arial', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.trade_type_var = tk.StringVar(value=trade_type)
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        ttk.Radiobutton(type_frame, text="BUY", variable=self.trade_type_var, value='BUY').pack(side='left', padx=5)
        ttk.Radiobutton(type_frame, text="SELL", variable=self.trade_type_var, value='SELL').pack(side='left', padx=5)
        row += 1
        
        # Quantity
        ttk.Label(main_frame, text="Quantity:", font=('Arial', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.quantity_entry = ttk.Entry(main_frame, width=25)
        self.quantity_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.quantity_entry.insert(0, str(quantity))
        row += 1
        
        # Price
        ttk.Label(main_frame, text="Price (₹):", font=('Arial', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.price_entry = ttk.Entry(main_frame, width=25)
        self.price_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.price_entry.insert(0, f"{price_rupees:.2f}")
        row += 1
        
        # Brokerage
        ttk.Label(main_frame, text="Brokerage (₹):", font=('Arial', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.brokerage_entry = ttk.Entry(main_frame, width=25)
        self.brokerage_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.brokerage_entry.insert(0, f"{brokerage_rupees:.2f}")
        row += 1
        
        # Notes
        ttk.Label(main_frame, text="Notes:", font=('Arial', 10)).grid(row=row, column=0, sticky='ne', padx=5, pady=8)
        self.notes_entry = tk.Text(main_frame, width=30, height=3, font=('Arial', 10))
        self.notes_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.notes_entry.insert('1.0', notes)
        row += 1
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy, width=15).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Save Changes", command=self.save_changes, width=15).pack(side='left', padx=10)
    
    def save_changes(self) -> None:
        """Save edited trade to database."""
        try:
            # Get values
            date_str = self.date_entry.get().strip()
            day, month, year = date_str.split('-')
            trade_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            equity = self.equity_entry.get().strip().upper()
            trade_type = self.trade_type_var.get()
            quantity = int(self.quantity_entry.get())
            
            price_rupees = float(self.price_entry.get())
            price_paise = int(price_rupees * 100)
            
            brokerage_rupees = float(self.brokerage_entry.get())
            brokerage_paise = int(brokerage_rupees * 100)
            
            notes = self.notes_entry.get('1.0', 'end-1c').strip()
            
            logger.info(f"Updating trade ID {self.trade_id}: {trade_type} {quantity} {equity} @ ₹{price_rupees:.2f}")
            
            # Update database
            conn = sqlite3.connect('data/trades.db')
            c = conn.cursor()
            c.execute("""
                UPDATE trade_events
                SET trade_date = ?, equity = ?, trade_type = ?, quantity = ?, 
                    price = ?, brokerage = ?, notes = ?
                WHERE id = ?
            """, (trade_date, equity, trade_type, quantity, price_paise, brokerage_paise, notes, self.trade_id))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Trade ID {self.trade_id} updated successfully")
            self.update_status(f"✅ Trade #{self.trade_id} updated")
            messagebox.showinfo("Success", "Trade updated successfully")
            
            # Close dialog and refresh
            self.dialog.destroy()
            self.refresh_callback()
            
        except Exception as e:
            logger.error(f"Failed to update trade: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to update trade:\n{str(e)}")
