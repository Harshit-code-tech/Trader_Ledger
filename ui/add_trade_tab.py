"""
Add Trade Tab - Phase 1

Responsibilities:
- Accept user input for trade details
- Validate inputs (basic only)
- Normalize equity (strip + uppercase)
- Convert ₹ → paise
- Insert into database
- Display recent trades (display-only, no logic)

Does NOT:
- Compute P/L
- Run FIFO
- Calculate holdings
- Generate reports
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
import sqlite3
from typing import Callable
from core.logger import get_logger
from core.utils import format_money

logger = get_logger('ui.add_trade_tab')


class AddTradeTab:
    """Add Trade tab - allows user to input and save trades."""
    
    def __init__(self, parent: ttk.Frame, status_callback: Callable[[str], None]) -> None:
        logger.info("Initializing Add Trade tab")
        self.parent = parent
        self.update_status = status_callback
        
        # Create UI
        self.create_widgets()
        
        # Set default date to today
        self.date_entry.insert(0, date.today().strftime('%d-%m-%Y'))
        logger.debug("Add Trade tab initialized with default date")
    
    def create_widgets(self) -> None:
        """Create all UI widgets for Add Trade tab."""
        
        # Main container
        main_frame = ttk.Frame(self.parent, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # Header
        header = ttk.Label(
            main_frame,
            text="ADD NEW TRADE",
            font=('Consolas', 16, 'bold')
        )
        header.grid(row=0, column=0, columnspan=4, pady=(0, 20))
        
        # Form fields
        row = 1
        
        # Date
        ttk.Label(main_frame, text="Date:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.date_entry = ttk.Entry(main_frame, width=20, font=('Consolas', 10))
        self.date_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        ttk.Label(main_frame, text="(DD-MM-YYYY)", font=('Consolas', 9), foreground='gray').grid(row=row, column=2, sticky='w', padx=5)
        row += 1
        
        # Stock Symbol
        ttk.Label(main_frame, text="Stock Symbol:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.equity_var = tk.StringVar()
        self.equity_entry = ttk.Combobox(main_frame, textvariable=self.equity_var, width=18, font=('Consolas', 10))
        self.equity_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        ttk.Label(main_frame, text="(e.g., TCS, RELIANCE)", font=('Consolas', 9), foreground='gray').grid(row=row, column=2, sticky='w', padx=5)
        self.load_equity_dropdown()
        row += 1
        
        # Trade Type
        ttk.Label(main_frame, text="Trade Type:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.trade_type_var = tk.StringVar(value='BUY')
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        ttk.Radiobutton(type_frame, text="BUY", variable=self.trade_type_var, value='BUY').pack(side='left', padx=5)
        ttk.Radiobutton(type_frame, text="SELL", variable=self.trade_type_var, value='SELL').pack(side='left', padx=5)
        row += 1
        
        # Quantity
        ttk.Label(main_frame, text="Quantity:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.quantity_entry = ttk.Entry(main_frame, width=20, font=('Consolas', 10))
        self.quantity_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        ttk.Label(main_frame, text="(shares)", font=('Consolas', 9), foreground='gray').grid(row=row, column=2, sticky='w', padx=5)
        row += 1
        
        # Price
        ttk.Label(main_frame, text="Price:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.price_entry = ttk.Entry(main_frame, width=20, font=('Consolas', 10))
        self.price_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        ttk.Label(main_frame, text="(₹ per share)", font=('Consolas', 9), foreground='gray').grid(row=row, column=2, sticky='w', padx=5)
        row += 1
        
        # Brokerage
        ttk.Label(main_frame, text="Brokerage:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.brokerage_entry = ttk.Entry(main_frame, width=20, font=('Consolas', 10))
        self.brokerage_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.brokerage_entry.insert(0, "0")  # Default to 0
        ttk.Label(main_frame, text="(₹)", font=('Consolas', 9), foreground='gray').grid(row=row, column=2, sticky='w', padx=5)
        row += 1
        
        # Notes
        ttk.Label(main_frame, text="Notes:", font=('Consolas', 10)).grid(row=row, column=0, sticky='ne', padx=5, pady=8)
        self.notes_entry = tk.Text(main_frame, width=30, height=3, font=('Consolas', 10))
        self.notes_entry.grid(row=row, column=1, columnspan=2, sticky='w', padx=5, pady=8)
        row += 1
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=4, pady=20)
        
        ttk.Button(
            button_frame,
            text="Clear",
            command=self.clear_form,
            width=15
        ).pack(side='left', padx=10)
        
        ttk.Button(
            button_frame,
            text="Save Trade",
            command=self.save_trade,
            width=15
        ).pack(side='left', padx=10)
        
        row += 1
        
        # Recent Trades section
        ttk.Separator(main_frame, orient='horizontal').grid(row=row, column=0, columnspan=4, sticky='ew', pady=10)
        row += 1
        
        ttk.Label(
            main_frame,
            text="RECENT TRADES (Last 5)",
            font=('Consolas', 13, 'bold')
        ).grid(row=row, column=0, columnspan=4, pady=(10, 5))
        row += 1
        
        # Recent trades table (display-only)
        self.create_recent_trades_table(main_frame, row)
    
    def create_recent_trades_table(self, parent: ttk.Frame, row: int) -> None:
        """Create table showing last 5 trades. Display-only, no logic."""
        
        # Create treeview frame
        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=row, column=0, columnspan=4, sticky='nsew', pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side='right', fill='y')
        
        # Treeview
        columns = ('Date', 'Stock', 'Type', 'Qty', 'Price', 'Total')
        self.recent_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show='headings',
            height=5,
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.recent_tree.yview)
        
        # Configure columns
        self.recent_tree.heading('Date', text='Date')
        self.recent_tree.heading('Stock', text='Stock')
        self.recent_tree.heading('Type', text='Type')
        self.recent_tree.heading('Qty', text='Qty')
        self.recent_tree.heading('Price', text='Price')
        self.recent_tree.heading('Total', text='Total')
        
        self.recent_tree.column('Date', width=100, anchor='center')
        self.recent_tree.column('Stock', width=80, anchor='center')
        self.recent_tree.column('Type', width=60, anchor='center')
        self.recent_tree.column('Qty', width=60, anchor='center')
        self.recent_tree.column('Price', width=100, anchor='e')
        self.recent_tree.column('Total', width=120, anchor='e')
        
        # Add mousewheel scrolling
        self.recent_tree.bind('<MouseWheel>', lambda e: self.recent_tree.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        self.recent_tree.pack(fill='both', expand=True)
        
        # Note about Total column (display-only)
        note = ttk.Label(
            parent,
            text="Note: 'Total' is display-only (BUY: qty\u00d7price+brokerage | SELL: qty\u00d7price-brokerage)",
            font=('Consolas', 8),
            foreground='gray'
        )
        note.grid(row=row+1, column=0, columnspan=4, pady=5)
        
        # Load recent trades
        self.refresh_recent_trades()
    
    def load_equity_dropdown(self) -> None:
        """Load unique equity symbols from database for autocomplete."""
        try:
            conn = sqlite3.connect('data/trades.db')
            c = conn.cursor()
            c.execute("SELECT DISTINCT equity FROM trade_events WHERE is_active = 1 ORDER BY equity")
            equities = [row[0] for row in c.fetchall()]
            conn.close()
            
            self.equity_entry['values'] = equities
            logger.debug(f"Loaded {len(equities)} unique equities for dropdown")
        except Exception as e:
            logger.error(f"Failed to load equities: {str(e)}")
            self.equity_entry['values'] = []
    
    def validate_inputs(self) -> tuple[bool, str]:
        """
        Validate all input fields.
        Returns (is_valid, error_message).
        """
        
        # Check date format
        date_str = self.date_entry.get().strip()
        if not date_str:
            logger.warning("Validation failed: Date is empty")
            return False, "Date is required"
        
        try:
            # Parse DD-MM-YYYY format
            day, month, year = date_str.split('-')
            _ = date(int(year), int(month), int(day))  # Validates the date
        except (ValueError, IndexError) as e:
            logger.warning(f"Validation failed: Invalid date format '{date_str}' - {str(e)}")
            return False, "Invalid date format. Use DD-MM-YYYY"
        
        # Check equity
        equity = self.equity_entry.get().strip()
        if not equity:
            logger.warning("Validation failed: Stock symbol is empty")
            return False, "Stock symbol is required"
        
        # Check quantity
        try:
            quantity = int(self.quantity_entry.get())
            if quantity <= 0:
                logger.warning(f"Validation failed: Invalid quantity {quantity}")
                return False, "Quantity must be positive"
        except ValueError as e:
            logger.warning(f"Validation failed: Quantity is not a number - {str(e)}")
            return False, "Quantity must be a number"
        
        # Check price
        try:
            price = float(self.price_entry.get())
            if price <= 0:
                logger.warning(f"Validation failed: Invalid price {price}")
                return False, "Price must be positive"
        except ValueError as e:
            logger.warning(f"Validation failed: Price is not a number - {str(e)}")
            return False, "Price must be a number"
        
        # Check brokerage
        try:
            brokerage = float(self.brokerage_entry.get())
            if brokerage < 0:
                logger.warning(f"Validation failed: Negative brokerage {brokerage}")
                return False, "Brokerage cannot be negative"
        except ValueError as e:
            logger.warning(f"Validation failed: Brokerage is not a number - {str(e)}")
            return False, "Brokerage must be a number"
        
        logger.debug("Input validation passed")
        return True, ""
    
    def save_trade(self) -> None:
        """Save trade to database."""
        
        # Validate inputs
        is_valid, error_msg = self.validate_inputs()
        if not is_valid:
            messagebox.showerror("Invalid Input", error_msg)
            return
        
        try:
            # Get and normalize values
            date_str = self.date_entry.get().strip()
            day, month, year = date_str.split('-')
            trade_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"  # Convert to YYYY-MM-DD
            
            equity = self.equity_entry.get().strip().upper()  # Normalize
            trade_type = self.trade_type_var.get()
            quantity = int(self.quantity_entry.get())
            
            # Convert ₹ → paise
            price_rupees = float(self.price_entry.get())
            price_paise = int(price_rupees * 100)
            
            brokerage_rupees = float(self.brokerage_entry.get())
            brokerage_paise = int(brokerage_rupees * 100)
            
            notes = self.notes_entry.get('1.0', 'end-1c').strip()
            
            # Normalize equity (uppercase, strip spaces)
            equity = equity.strip().upper()
            
            logger.info(f"Preparing to save trade: {trade_type} {quantity} {equity} @ ₹{price_rupees:.2f} on {date_str}")
            logger.debug(f"Trade details - Date: {trade_date}, Equity: {equity}, Type: {trade_type}, Qty: {quantity}, Price: {price_paise} paise, Brokerage: {brokerage_paise} paise")
            
            # Insert into database
            logger.debug("Connecting to database: data/trades.db")
            conn = sqlite3.connect('data/trades.db')
            c = conn.cursor()
            c.execute("""
                INSERT INTO trade_events (trade_date, equity, trade_type, quantity, price, brokerage, notes, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (trade_date, equity, trade_type, quantity, price_paise, brokerage_paise, notes))
            trade_id = c.lastrowid
            conn.commit()
            conn.close()
            
            # Success
            logger.info(f"✅ Trade saved successfully - ID: {trade_id}, {trade_type} {quantity} {equity} @ ₹{price_rupees:.2f}")
            self.update_status(f"✅ Trade saved: {trade_type} {quantity} {equity} @ ₹{price_rupees:.2f}")
            messagebox.showinfo("Success", f"Trade saved successfully!\n\n{trade_type} {quantity} {equity}")
            
            # Refresh and clear
            logger.debug("Refreshing recent trades display and clearing form")
            self.refresh_recent_trades()
            self.clear_form()
            
        except Exception as e:
            logger.error(f"❌ Failed to save trade: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to save trade:\n{str(e)}")
            self.update_status(f"❌ Error saving trade")
    
    def refresh_recent_trades(self) -> None:
        """Load last 5 trades for display. Total column is display-only."""
        
        logger.debug("Refreshing recent trades display")
        
        # Clear existing items
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)
        
        try:
            conn = sqlite3.connect('data/trades.db')
            c = conn.cursor()
            c.execute("""
                SELECT trade_date, equity, trade_type, quantity, price, brokerage
                FROM trade_events
                WHERE is_active = 1
                ORDER BY id DESC
                LIMIT 5
            """)
            trades = c.fetchall()
            conn.close()
            
            logger.debug(f"Loaded {len(trades)} recent trades from database")
            
            for trade in trades:
                trade_date, equity, trade_type, quantity, price_paise, brokerage_paise = trade
                
                # DISPLAY-ONLY calculation (NOT used in engine)
                if trade_type == 'BUY':
                    total_paise = (quantity * price_paise) + brokerage_paise
                else:  # SELL
                    total_paise = (quantity * price_paise) - brokerage_paise
                
                # Format date DD-MM-YYYY
                year, month, day = trade_date.split('-')
                display_date = f"{day}-{month}-{year}"
                
                self.recent_tree.insert('', 'end', values=(
                    display_date,
                    equity,
                    trade_type,
                    quantity,
                    format_money(price_paise),
                    format_money(total_paise)  # Display-only total
                ))
        
        except Exception as e:
            self.update_status(f"⚠️ Could not load recent trades: {str(e)}")
    
    def clear_form(self) -> None:
        """Clear all input fields."""
        logger.debug("Clearing form")
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, date.today().strftime('%d-%m-%Y'))
        self.equity_entry.delete(0, tk.END)
        self.trade_type_var.set('BUY')
        self.quantity_entry.delete(0, tk.END)
        self.price_entry.delete(0, tk.END)
        self.brokerage_entry.delete(0, tk.END)
        self.brokerage_entry.insert(0, "0")
        self.notes_entry.delete('1.0', tk.END)
        self.equity_entry.focus()
        self.update_status("Form cleared")
