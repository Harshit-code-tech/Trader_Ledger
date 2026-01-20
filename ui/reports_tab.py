"""
Reports Tab - Phase 3

Responsibilities:
- Run FIFO engine on tab open (recalculate every time)
- Calculate realized P/L
- Display summary cards (Total Profit, Total Loss, Net P/L)
- Show emotion indicator based on net P/L (😢 loss, 🙂 profit)
- Display daily/monthly aggregations
- Show detailed P/L breakdown

Does NOT:
- Cache results (always fresh calculation)
- Edit trades
- Validate data integrity
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable
from datetime import datetime
from core.logger import get_logger

# Import FIFO and P/L calculation modules
from core.fifo_matcher import fetch_active_trades, match_fifo
from core.pnl_calculator import calculate_match_pnl
from core.pnl_aggregator import aggregate_pnl_by_date, aggregate_pnl_by_month
from core.run_ledger import build_trades_by_id  # Use engine's conversion function

logger = get_logger('ui.reports_tab')


class ReportsTab:
    """Reports tab - display P/L analysis with FIFO-based calculations."""
    
    def __init__(self, parent: ttk.Frame, status_callback: Callable[[str], None]) -> None:
        logger.info("Initializing Reports tab")
        self.parent = parent
        self.update_status = status_callback
        
        # Data containers
        self.total_profit = 0
        self.total_loss = 0
        self.net_pnl = 0
        self.daily_pnl = {}
        self.monthly_pnl = {}
        
        # Create UI
        self.create_widgets()
        
        # Don't auto-calculate on init, only when tab is selected
        logger.debug("Reports tab initialized (calculations deferred)")
    
    def _convert_to_pnl_breakdown(self, pnl_totals: dict[str, int]) -> dict[str, dict[str, int]]:
        """
        Convert engine's simple P/L format to UI's profit/loss/net breakdown.
        Engine returns: {'2026-01-20': 1000} (net P/L in paise)
        UI needs: {'2026-01-20': {'profit': 1500, 'loss': -500, 'net': 1000}}
        
        For aggregated data, we don't have individual profit/loss split,
        so we treat positive as profit and negative as loss.
        """
        breakdown = {}
        for key, net_pnl in pnl_totals.items():
            if net_pnl > 0:
                breakdown[key] = {'profit': net_pnl, 'loss': 0, 'net': net_pnl}
            elif net_pnl < 0:
                breakdown[key] = {'profit': 0, 'loss': net_pnl, 'net': net_pnl}
            else:
                breakdown[key] = {'profit': 0, 'loss': 0, 'net': 0}
        return breakdown
    
    def create_widgets(self) -> None:
        """Create all UI widgets for Reports tab."""
        
        # Main container with scrollbar
        canvas = tk.Canvas(self.parent)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Main frame inside scrollable area
        main_frame = ttk.Frame(scrollable_frame, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(
            header_frame,
            text="PROFIT/LOSS REPORTS",
            font=('Arial', 14, 'bold')
        ).pack(side='left')
        
        ttk.Button(
            header_frame,
            text="🔄 Recalculate",
            command=self.calculate_reports,
            width=15
        ).pack(side='right', padx=5)
        
        # Summary Cards Section
        self.create_summary_cards(main_frame)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=20)
        
        # Daily P/L Section
        self.create_daily_pnl_section(main_frame)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=20)
        
        # Monthly P/L Section
        self.create_monthly_pnl_section(main_frame)
    
    def create_summary_cards(self, parent: ttk.Frame) -> None:
        """Create summary cards for Total Profit, Total Loss, Net P/L."""
        
        cards_frame = ttk.Frame(parent)
        cards_frame.pack(fill='x', pady=(0, 10))
        
        # Configure grid to center cards
        cards_frame.columnconfigure(0, weight=1)
        cards_frame.columnconfigure(1, weight=1)
        cards_frame.columnconfigure(2, weight=1)
        
        # Card 1: Total Profit
        profit_card = ttk.LabelFrame(cards_frame, text="📈 Total Realized Profit", padding="15")
        profit_card.grid(row=0, column=0, padx=10, pady=5, sticky='ew')
        
        self.profit_label = ttk.Label(
            profit_card,
            text="₹0.00",
            font=('Arial', 18, 'bold'),
            foreground='green'
        )
        self.profit_label.pack()
        
        # Card 2: Total Loss
        loss_card = ttk.LabelFrame(cards_frame, text="📉 Total Realized Loss", padding="15")
        loss_card.grid(row=0, column=1, padx=10, pady=5, sticky='ew')
        
        self.loss_label = ttk.Label(
            loss_card,
            text="₹0.00",
            font=('Arial', 18, 'bold'),
            foreground='red'
        )
        self.loss_label.pack()
        
        # Card 3: Net P/L with emotion
        net_card = ttk.LabelFrame(cards_frame, text="🧮 Net Profit/Loss", padding="15")
        net_card.grid(row=0, column=2, padx=10, pady=5, sticky='ew')
        
        emotion_frame = ttk.Frame(net_card)
        emotion_frame.pack()
        
        self.emotion_label = ttk.Label(
            emotion_frame,
            text="😐",
            font=('Arial', 24)
        )
        self.emotion_label.pack(side='left', padx=(0, 10))
        
        self.net_label = ttk.Label(
            emotion_frame,
            text="₹0.00",
            font=('Arial', 18, 'bold')
        )
        self.net_label.pack(side='left')
    
    def create_daily_pnl_section(self, parent: ttk.Frame) -> None:
        """Create daily P/L breakdown table."""
        
        ttk.Label(
            parent,
            text="Daily P/L Breakdown",
            font=('Arial', 12, 'bold')
        ).pack(anchor='w', pady=(0, 10))
        
        # Table frame
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side='right', fill='y')
        
        # Treeview
        columns = ('Date', 'Profit', 'Loss', 'Net P/L')
        self.daily_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show='headings',
            height=8,
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.daily_tree.yview)
        
        # Configure columns
        self.daily_tree.heading('Date', text='Date')
        self.daily_tree.heading('Profit', text='Profit')
        self.daily_tree.heading('Loss', text='Loss')
        self.daily_tree.heading('Net P/L', text='Net P/L')
        
        self.daily_tree.column('Date', width=150, anchor='center')
        self.daily_tree.column('Profit', width=150, anchor='e')
        self.daily_tree.column('Loss', width=150, anchor='e')
        self.daily_tree.column('Net P/L', width=150, anchor='e')
        
        self.daily_tree.pack(fill='both', expand=True)
    
    def create_monthly_pnl_section(self, parent: ttk.Frame) -> None:
        """Create monthly P/L breakdown table."""
        
        ttk.Label(
            parent,
            text="Monthly P/L Breakdown",
            font=('Arial', 12, 'bold')
        ).pack(anchor='w', pady=(0, 10))
        
        # Table frame
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side='right', fill='y')
        
        # Treeview
        columns = ('Month', 'Profit', 'Loss', 'Net P/L')
        self.monthly_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show='headings',
            height=8,
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.monthly_tree.yview)
        
        # Configure columns
        self.monthly_tree.heading('Month', text='Month')
        self.monthly_tree.heading('Profit', text='Profit')
        self.monthly_tree.heading('Loss', text='Loss')
        self.monthly_tree.heading('Net P/L', text='Net P/L')
        
        self.monthly_tree.column('Month', width=150, anchor='center')
        self.monthly_tree.column('Profit', width=150, anchor='e')
        self.monthly_tree.column('Loss', width=150, anchor='e')
        self.monthly_tree.column('Net P/L', width=150, anchor='e')
        
        self.monthly_tree.pack(fill='both', expand=True)
    
    def calculate_reports(self) -> None:
        """
        Recalculate all reports from scratch.
        Runs FIFO engine and P/L calculations every time.
        """
        logger.info("="*60)
        logger.info("Starting P/L report calculation")
        logger.info("="*60)
        
        self.update_status("⏳ Calculating P/L reports...")
        
        try:
            # Step 1: Fetch active trades
            logger.info("Step 1: Fetching active trades from database")
            trades = fetch_active_trades()
            logger.info(f"Fetched {len(trades)} active trades")
            
            if not trades:
                logger.warning("No active trades found")
                messagebox.showinfo("No Data", "No active trades found in database.")
                self.update_status("⚠️ No trades to analyze")
                self.reset_displays()
                return
            
            # Step 2: Run FIFO matching
            logger.info("Step 2: Running FIFO matching")
            matches = match_fifo(trades)
            logger.info(f"Generated {len(matches)} FIFO matches")
            
            if not matches:
                logger.warning("No FIFO matches generated (all BUYs, no SELLs?)")
                messagebox.showinfo("No Matches", "No SELL trades found. P/L can only be calculated after selling.")
                self.update_status("⚠️ No realized P/L yet")
                self.reset_displays()
                return
            
            # Step 3: Calculate P/L for each match
            logger.info("Step 3: Calculating P/L for each match")
            
            # Use engine's conversion function to build trades dictionary
            trades_by_id = build_trades_by_id(trades)
            
            # Calculate P/L for all matches
            pnl_results = calculate_match_pnl(matches, trades_by_id)
            
            for pnl in pnl_results:
                logger.debug(f"Match: BUY #{pnl['buy_id']} -> SELL #{pnl['sell_id']}, P/L: {pnl['realized_pnl']} paise")
            
            logger.info(f"Calculated P/L for {len(pnl_results)} matches")
            
            # Step 4: Aggregate by date and month
            logger.info("Step 4: Aggregating P/L by date and month")
            daily_pnl_totals = aggregate_pnl_by_date(pnl_results, trades_by_id)
            monthly_pnl_totals = aggregate_pnl_by_month(daily_pnl_totals)
            
            # Convert to UI format with profit/loss breakdown
            self.daily_pnl = self._convert_to_pnl_breakdown(daily_pnl_totals)
            self.monthly_pnl = self._convert_to_pnl_breakdown(monthly_pnl_totals)
            
            logger.info(f"Daily aggregations: {len(self.daily_pnl)} days")
            logger.info(f"Monthly aggregations: {len(self.monthly_pnl)} months")
            
            # Step 5: Calculate totals
            logger.info("Step 5: Calculating total profit/loss")
            self.total_profit = sum(pnl['realized_pnl'] for pnl in pnl_results if pnl['realized_pnl'] > 0)
            self.total_loss = sum(pnl['realized_pnl'] for pnl in pnl_results if pnl['realized_pnl'] < 0)
            self.net_pnl = self.total_profit + self.total_loss  # loss is negative
            
            logger.info(f"Total Profit: {self.total_profit} paise (₹{self.total_profit/100:.2f})")
            logger.info(f"Total Loss: {self.total_loss} paise (₹{self.total_loss/100:.2f})")
            logger.info(f"Net P/L: {self.net_pnl} paise (₹{self.net_pnl/100:.2f})")
            
            # Step 6: Update UI
            logger.info("Step 6: Updating UI displays")
            self.update_displays()
            
            self.update_status(f"✅ Reports calculated: Net P/L = ₹{self.net_pnl/100:.2f}")
            logger.info("="*60)
            logger.info("P/L report calculation completed successfully")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate reports: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to calculate reports:\n\n{str(e)}")
            self.update_status("❌ Error calculating reports")
            self.reset_displays()
    
    def update_displays(self) -> None:
        """Update all display elements with calculated values."""
        
        # Update summary cards
        self.profit_label.config(text=f"₹{self.total_profit/100:.2f}")
        self.loss_label.config(text=f"₹{abs(self.total_loss)/100:.2f}")
        self.net_label.config(text=f"₹{self.net_pnl/100:.2f}")
        
        # Update emotion and net P/L color
        if self.net_pnl > 0:
            self.emotion_label.config(text="🙂")  # Happy
            self.net_label.config(foreground='green')
        elif self.net_pnl < 0:
            self.emotion_label.config(text="😢")  # Sad
            self.net_label.config(foreground='red')
        else:
            self.emotion_label.config(text="😐")  # Neutral
            self.net_label.config(foreground='black')
        
        # Update daily table
        for item in self.daily_tree.get_children():
            self.daily_tree.delete(item)
        
        for date_str, pnl_data in sorted(self.daily_pnl.items(), reverse=True):
            profit = pnl_data['profit']
            loss = pnl_data['loss']
            net = pnl_data['net']
            
            # Format date DD-MM-YYYY
            year, month, day = date_str.split('-')
            display_date = f"{day}-{month}-{year}"
            
            item = self.daily_tree.insert('', 'end', values=(
                display_date,
                f"₹{profit/100:.2f}" if profit > 0 else "₹0.00",
                f"₹{abs(loss)/100:.2f}" if loss < 0 else "₹0.00",
                f"₹{net/100:.2f}"
            ))
            
            # Color code net P/L
            if net > 0:
                self.daily_tree.item(item, tags=('profit',))
            elif net < 0:
                self.daily_tree.item(item, tags=('loss',))
        
        self.daily_tree.tag_configure('profit', foreground='green')
        self.daily_tree.tag_configure('loss', foreground='red')
        
        # Update monthly table
        for item in self.monthly_tree.get_children():
            self.monthly_tree.delete(item)
        
        for month_str, pnl_data in sorted(self.monthly_pnl.items(), reverse=True):
            profit = pnl_data['profit']
            loss = pnl_data['loss']
            net = pnl_data['net']
            
            # Format month YYYY-MM -> MMM YYYY
            year, month = month_str.split('-')
            month_name = datetime.strptime(month, "%m").strftime("%b")
            display_month = f"{month_name} {year}"
            
            item = self.monthly_tree.insert('', 'end', values=(
                display_month,
                f"₹{profit/100:.2f}" if profit > 0 else "₹0.00",
                f"₹{abs(loss)/100:.2f}" if loss < 0 else "₹0.00",
                f"₹{net/100:.2f}"
            ))
            
            # Color code net P/L
            if net > 0:
                self.monthly_tree.item(item, tags=('profit',))
            elif net < 0:
                self.monthly_tree.item(item, tags=('loss',))
        
        self.monthly_tree.tag_configure('profit', foreground='green')
        self.monthly_tree.tag_configure('loss', foreground='red')
    
    def reset_displays(self) -> None:
        """Reset all displays to zero/empty state."""
        self.total_profit = 0
        self.total_loss = 0
        self.net_pnl = 0
        self.daily_pnl = {}
        self.monthly_pnl = {}
        
        self.profit_label.config(text="₹0.00")
        self.loss_label.config(text="₹0.00")
        self.net_label.config(text="₹0.00", foreground='black')
        self.emotion_label.config(text="😐")
        
        for item in self.daily_tree.get_children():
            self.daily_tree.delete(item)
        
        for item in self.monthly_tree.get_children():
            self.monthly_tree.delete(item)
    
    def on_tab_selected(self) -> None:
        """Called when Reports tab is selected. Triggers recalculation."""
        logger.info("Reports tab selected - triggering automatic recalculation")
        self.calculate_reports()
