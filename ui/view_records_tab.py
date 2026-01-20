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
from tkinter import ttk, messagebox, simpledialog
from datetime import date, datetime
import sqlite3
from typing import Callable, Optional
from core.logger import get_logger

logger = get_logger('ui.view_records_tab')


class ViewRecordsTab:
    """View Records tab - display and manage trade records."""
    
    def __init__(self, parent: ttk.Frame, status_callback: Callable[[str], None]) -> None:
        logger.info("Initializing View Records tab")
        self.parent = parent
        self.update_status = status_callback
        self.selected_trade_id: Optional[int] = None
        
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
            font=('Arial', 14, 'bold')
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
        
        # Status filter
        ttk.Label(row1, text="Status:", font=('Arial', 9)).pack(side='left', padx=(0, 5))
        self.status_filter = ttk.Combobox(row1, width=10, state='readonly', values=["Active", "Deleted", "All"])
        self.status_filter.pack(side='left', padx=(0, 20))
        self.status_filter.set("Active")
        
        # Apply button
        ttk.Button(row1, text="Apply Filters", command=self.apply_filters, width=12).pack(side='left', padx=10)
        ttk.Button(row1, text="Clear Filters", command=self.clear_filters, width=12).pack(side='left')
        
        # Row 2: Date Range (placeholder for future)
        row2 = ttk.Frame(filter_frame)
        row2.pack(fill='x', pady=5)
        ttk.Label(row2, text="Date range filters coming soon", font=('Arial', 8), foreground='gray').pack(side='left')
    
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
        
        # Bind double-click to edit
        self.records_tree.bind('<Double-Button-1>', lambda e: self.edit_selected_trade())
        
        # Bind selection
        self.records_tree.bind('<<TreeviewSelect>>', self.on_select)
    
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
            text="Edit Trade",
            command=self.edit_selected_trade,
            width=15
        ).pack(side='left', padx=5)
        
        ttk.Button(
            button_frame,
            text="Delete Trade",
            command=self.delete_selected_trade,
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
            
            status_filter = self.status_filter.get()
            if status_filter == "Active":
                query += " AND is_active = 1"
            elif status_filter == "Deleted":
                query += " AND is_active = 0"
            # "All" doesn't add any condition
            
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
                
                # Convert paise → rupees
                price_rupees = price_paise / 100
                brokerage_rupees = brokerage_paise / 100
                
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
                    f"₹{price_rupees:.2f}",
                    f"₹{brokerage_rupees:.2f}",
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
        logger.info(f"Applying filters - Equity: {self.equity_filter.get()}, Type: {self.type_filter.get()}, Status: {self.status_filter.get()}")
        self.refresh_records()
    
    def clear_filters(self) -> None:
        """Clear all filters and refresh."""
        logger.info("Clearing all filters")
        self.equity_filter.set("All")
        self.type_filter.set("All")
        self.status_filter.set("Active")
        self.refresh_records()
    
    def on_select(self, event) -> None:
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
            EditTradeDialog(self.parent, trade_id, trade, self.refresh_records, self.update_status)
            
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


class EditTradeDialog:
    """Dialog for editing trade details."""
    
    def __init__(self, parent, trade_id: int, trade_data: tuple, refresh_callback: Callable, status_callback: Callable):
        self.trade_id = trade_id
        self.refresh_callback = refresh_callback
        self.update_status = status_callback
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit Trade #{trade_id}")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Unpack trade data
        trade_date, equity, trade_type, quantity, price_paise, brokerage_paise, notes, is_active = trade_data
        
        # Convert for display
        price_rupees = price_paise / 100
        brokerage_rupees = brokerage_paise / 100
        year, month, day = trade_date.split('-')
        display_date = f"{day}-{month}-{year}"
        
        # Create form
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text=f"EDIT TRADE #{trade_id}", font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        row = 1
        
        # Trade ID (readonly display)
        ttk.Label(main_frame, text="Trade ID:", font=('Arial', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        id_display = ttk.Label(main_frame, text=f"#{trade_id}", font=('Arial', 10, 'bold'), foreground='blue')
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
