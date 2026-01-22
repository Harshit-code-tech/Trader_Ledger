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
from pathlib import Path
from core.logger import get_logger

# Import FIFO and P/L calculation modules
from core.fifo_matcher import fetch_active_trades, match_fifo
from core.pnl_calculator import calculate_match_pnl
from core.pnl_aggregator import (
    aggregate_pnl_by_date, 
    aggregate_pnl_by_week, 
    aggregate_pnl_by_month, 
    aggregate_pnl_by_year
)
from core.run_ledger import build_trades_by_id  # Use engine's conversion function
from core.utils import format_money, format_money_abs, format_period_label

logger = get_logger('ui.reports_tab')


class ReportsTab:
    """Reports tab - display P/L analysis with FIFO-based calculations."""
    
    @staticmethod
    def build_report_rows(period_totals: dict, mode: str) -> list[dict]:
        """
        Normalize period data into display-ready rows.
        
        Args:
            period_totals: Dict of period_key -> {profit, loss, net}
            mode: Period type for label formatting
        
        Returns:
            List of row dicts with all display values pre-calculated
        """
        rows = []
        accumulated = 0
        
        for period_key in sorted(period_totals.keys()):
            profit = period_totals[period_key]['profit']
            loss = period_totals[period_key]['loss']
            net = period_totals[period_key]['net']
            
            accumulated += net
            
            rows.append({
                'period_key': period_key,
                'label': format_period_label(period_key, mode),
                'profit': profit,
                'loss': loss,
                'net': net,
                'accumulated': accumulated
            })
        
        return rows
    
    def __init__(self, parent: ttk.Frame, status_callback: Callable[[str], None]) -> None:
        logger.info("Initializing Reports tab")
        self.parent = parent
        self.update_status = status_callback
        
        # Data containers
        self.total_profit = 0
        self.total_loss = 0
        self.net_pnl = 0
        self.daily_pnl = {}
        self.weekly_pnl = {}
        self.monthly_pnl = {}
        self.yearly_pnl = {}
        
        # Validation state
        self.has_validation_errors = False
        self.validation_message = ""
        
        # Period selection
        self.period_var = tk.StringVar(value="Daily")
        
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
        
        # Bind mousewheel for scrolling
        canvas.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Store canvas reference for cleanup
        self.canvas = canvas
        
        # Main frame inside scrollable area
        main_frame = ttk.Frame(scrollable_frame, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # Warning banner (initially hidden)
        self.warning_frame = ttk.Frame(main_frame)
        self.warning_label = ttk.Label(
            self.warning_frame,
            text="",
            font=('Consolas', 10, 'bold'),
            foreground='white',
            background='#e74c3c',
            padding=10,
            wraplength=800
        )
        self.warning_label.pack(fill='x')
        # Don't pack warning_frame yet - will show when needed
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(
            header_frame,
            text="PROFIT/LOSS REPORTS",
            font=('Consolas', 16, 'bold')
        ).pack(side='left')
        
        # Period selector
        period_frame = ttk.Frame(header_frame)
        period_frame.pack(side='right', padx=20)
        
        ttk.Label(period_frame, text="View:", font=('Arial', 10)).pack(side='left', padx=(0, 5))
        period_dropdown = ttk.Combobox(
            period_frame,
            textvariable=self.period_var,
            values=["Daily", "Weekly", "Monthly", "Yearly"],
            state='readonly',
            width=12
        )
        period_dropdown.pack(side='left', padx=5)
        period_dropdown.bind('<<ComboboxSelected>>', lambda e: self.update_period_display())
        
        ttk.Button(
            header_frame,
            text="🔄 Recalculate",
            command=self.calculate_reports,
            width=15
        ).pack(side='right', padx=5)
        
        self.print_btn = ttk.Button(
            header_frame,
            text="\ud83d\udda8\ufe0f Print",
            command=self.print_report,
            width=12
        )
        self.print_btn.pack(side='right', padx=5)
        
        # Summary Cards Section
        self.create_summary_cards(main_frame)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=20)
        
        # Dynamic P/L Section (changes based on dropdown)
        self.create_dynamic_pnl_section(main_frame)
    
    def create_dynamic_pnl_section(self, parent: ttk.Frame) -> None:
        """Create dynamic P/L breakdown table that changes based on period selection."""
        
        # Context header (explains what the table shows)
        context_label = ttk.Label(
            parent,
            text="Showing SELL-based P/L (FIFO applied, realized only)",
            font=('Consolas', 9),
            foreground='gray'
        )
        context_label.pack(anchor='w', pady=(0, 5))
        
        # Title label (will update based on selection)
        self.pnl_title_label = ttk.Label(
            parent,
            text="DAILY P/L",
            font=('Consolas', 13, 'bold')
        )
        self.pnl_title_label.pack(anchor='w', pady=(0, 10))
        
        # Table frame
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side='right', fill='y')
        
        # Treeview
        columns = ('Period', 'Profit', 'Loss', 'Net P/L', 'Running Total')
        self.pnl_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show='headings',
            height=12,
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.pnl_tree.yview)
        
        # Configure columns with proper alignment
        self.pnl_tree.heading('Period', text='Period', anchor='w')
        self.pnl_tree.heading('Profit', text='Profit (₹)', anchor='e')
        self.pnl_tree.heading('Loss', text='Loss (₹)', anchor='e')
        self.pnl_tree.heading('Net P/L', text='Net P/L (₹)', anchor='e')
        self.pnl_tree.heading('Running Total', text='⭐ Accumulated (₹)', anchor='e')  # Star for emphasis
        
        self.pnl_tree.column('Period', width=200, anchor='w')
        self.pnl_tree.column('Profit', width=130, anchor='e')
        self.pnl_tree.column('Loss', width=130, anchor='e')
        self.pnl_tree.column('Net P/L', width=130, anchor='e')
        self.pnl_tree.column('Running Total', width=160, anchor='e')  # Slightly wider for emphasis
        
        # Configure zebra striping tags
        self.pnl_tree.tag_configure('evenrow', background='#f8f9fa')
        self.pnl_tree.tag_configure('oddrow', background='white')
        
        # Bind mousewheel
        self.pnl_tree.bind('<MouseWheel>', lambda e: self.pnl_tree.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        self.pnl_tree.pack(fill='both', expand=True)
    
    def create_summary_cards(self, parent: ttk.Frame) -> None:
        """Create summary cards for Total Profit, Total Loss, Net P/L."""
        
        cards_frame = ttk.Frame(parent)
        cards_frame.pack(fill='x', pady=(0, 20))
        
        # Configure grid to center cards
        cards_frame.columnconfigure(0, weight=1)
        cards_frame.columnconfigure(1, weight=1)
        cards_frame.columnconfigure(2, weight=1)
        
        # Card 1: Total Profit
        profit_card = ttk.LabelFrame(cards_frame, text="📈 Total Profit", padding="20")
        profit_card.grid(row=0, column=0, padx=15, pady=10, sticky='ew')
        
        # Small label above
        ttk.Label(profit_card, text="Total Profit", font=('Consolas', 9), foreground='gray').pack()
        
        self.profit_label = ttk.Label(
            profit_card,
            text="₹ +0.00",
            font=('Consolas', 22, 'bold'),
            foreground='#27ae60'
        )
        self.profit_label.pack(pady=(5, 0))
        
        # Card 2: Total Loss
        loss_card = ttk.LabelFrame(cards_frame, text="📉 Total Loss", padding="20")
        loss_card.grid(row=0, column=1, padx=15, pady=10, sticky='ew')
        
        # Small label above
        ttk.Label(loss_card, text="Total Loss", font=('Consolas', 9), foreground='gray').pack()
        
        self.loss_label = ttk.Label(
            loss_card,
            text="₹ -0.00",
            font=('Consolas', 22, 'bold'),
            foreground='#e74c3c'
        )
        self.loss_label.pack(pady=(5, 0))
        
        # Card 3: Net P/L with emotion
        net_card = ttk.LabelFrame(cards_frame, text="🧮 Net P/L", padding="20")
        net_card.grid(row=0, column=2, padx=15, pady=10, sticky='ew')
        
        # Small label above
        ttk.Label(net_card, text="Net P/L", font=('Consolas', 9), foreground='gray').pack()
        
        value_frame = ttk.Frame(net_card)
        value_frame.pack(pady=(5, 0))
        
        self.emotion_label = ttk.Label(
            value_frame,
            text="😐",
            font=('Arial', 28)
        )
        self.emotion_label.pack(side='left', padx=(0, 8))
        
        self.net_label = ttk.Label(
            value_frame,
            text="₹ 0.00",
            font=('Consolas', 22, 'bold')
        )
        self.net_label.pack(side='left')
    
    
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
            logger.info(f"Generated {len(matches) if matches else 0} FIFO matches")
            
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
            
            # Step 4: Aggregate by date, week, month, and year
            logger.info("Step 4: Aggregating P/L by date, week, month, and year")
            daily_pnl_totals = aggregate_pnl_by_date(pnl_results, trades_by_id)
            weekly_pnl_totals = aggregate_pnl_by_week(daily_pnl_totals)
            monthly_pnl_totals = aggregate_pnl_by_month(daily_pnl_totals)
            yearly_pnl_totals = aggregate_pnl_by_year(monthly_pnl_totals)
            
            # Convert to UI format with profit/loss breakdown
            self.daily_pnl = self._convert_to_pnl_breakdown(daily_pnl_totals)
            self.weekly_pnl = self._convert_to_pnl_breakdown(weekly_pnl_totals)
            self.monthly_pnl = self._convert_to_pnl_breakdown(monthly_pnl_totals)
            self.yearly_pnl = self._convert_to_pnl_breakdown(yearly_pnl_totals)
            
            logger.info(f"Daily aggregations: {len(self.daily_pnl)} days")
            logger.info(f"Weekly aggregations: {len(self.weekly_pnl)} weeks")
            logger.info(f"Monthly aggregations: {len(self.monthly_pnl)} months")
            logger.info(f"Yearly aggregations: {len(self.yearly_pnl)} years")
            
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
            self.hide_warning_banner()  # Hide warning on success
            self.update_displays()
            
            self.update_status(f"✅ FIFO validated | Net P/L = ₹{self.net_pnl/100:.2f}")
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
        
        # Update summary cards (format_money already adds +/- signs)
        self.profit_label.config(text=format_money(self.total_profit))
        
        # Loss should show with negative sign (e.g., ₹ -61.16)
        if self.total_loss < 0:
            loss_formatted = format_money_abs(self.total_loss)
            self.loss_label.config(text=f"₹ -{loss_formatted.replace('₹', '').strip()}")
        else:
            self.loss_label.config(text="₹ 0.00")
        
        self.net_label.config(text=format_money(self.net_pnl))
        
        # Update emotion and net P/L color
        if self.net_pnl > 0:
            self.emotion_label.config(text="🙂")  # Happy
            self.net_label.config(foreground='#27ae60')
        elif self.net_pnl < 0:
            self.emotion_label.config(text="😢")  # Sad
            self.net_label.config(foreground='#e74c3c')
        else:
            self.emotion_label.config(text="😐")  # Neutral
            self.net_label.config(foreground='#34495e')
        
        # Update period-specific table
        self.update_period_display()
    
    def update_period_display(self) -> None:
        """Update the P/L table based on selected period."""
        period = self.period_var.get()
        
        # Update title
        title_map = {
            "Daily": "DAILY P/L",
            "Weekly": "WEEKLY P/L", 
            "Monthly": "MONTHLY P/L",
            "Yearly": "YEARLY P/L"
        }
        self.pnl_title_label.config(text=title_map.get(period, "P/L BREAKDOWN"))
        
        # Clear existing data
        for item in self.pnl_tree.get_children():
            self.pnl_tree.delete(item)
        
        # Get appropriate data based on period
        period_map = {
            "Daily": (self.daily_pnl, "daily"),
            "Weekly": (self.weekly_pnl, "weekly"),
            "Monthly": (self.monthly_pnl, "monthly"),
            "Yearly": (self.yearly_pnl, "yearly")
        }
        
        if period not in period_map:
            return
        
        data_dict, mode = period_map[period]
        
        # Handle empty state
        if not data_dict:
            _ = self.pnl_tree.insert('', 'end', values=(
                "No realized P/L in this period",
                "",
                "",
                "(no SELL trades)",
                ""
            ), tags=('empty',))
            self.pnl_tree.tag_configure('empty', foreground='gray')
            return
        
        # Build normalized rows (data → display)
        rows = self.build_report_rows(data_dict, mode)
        
        # Render rows (pure UI, no logic)
        for idx, row in enumerate(reversed(rows)):  # Reverse for descending order
            # Zebra striping
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            
            _ = self.pnl_tree.insert('', 'end', values=(
                row['label'],
                format_money(row['profit']) if row['profit'] != 0 else "\u20b9 0.00",
                format_money(row['loss']) if row['loss'] != 0 else "\u20b9 0.00",
                format_money(row['net']),
                f"→ {format_money(row['accumulated'])}"
            ), tags=(tag,))
    
    def show_warning_banner(self) -> None:
        """Show warning banner at top of Reports tab."""
        if self.has_validation_errors:
            self.warning_label.config(text=f"⚠️ VALIDATION ERROR: {self.validation_message}")
            self.warning_frame.pack(fill='x', pady=(0, 10), before=self.parent.winfo_children()[1])
    
    def hide_warning_banner(self) -> None:
        """Hide warning banner."""
        if hasattr(self, 'warning_frame'):
            self.warning_frame.pack_forget()
    
    def reset_displays(self) -> None:
        """Reset all displays to zero/empty state."""
        self.total_profit = 0
        self.total_loss = 0
        self.net_pnl = 0
        self.daily_pnl = {}
        self.weekly_pnl = {}
        self.monthly_pnl = {}
        self.yearly_pnl = {}
        
        self.profit_label.config(text="₹ +0.00")
        self.loss_label.config(text="₹ -0.00")
        self.net_label.config(text="₹ 0.00", foreground='#34495e')
        self.emotion_label.config(text="😐")
        
        # Clear the unified tree
        for item in self.pnl_tree.get_children():
            self.pnl_tree.delete(item)
    
    def print_report(self) -> None:
        """Generate a print-friendly HTML report."""
        logger.info("Generating print report")
        
        try:
            import webbrowser
            
            # Ensure export directory exists
            Path("data/exports").mkdir(parents=True, exist_ok=True)
            
            # Generate timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"data/exports/report_{timestamp}.html"
            
            # Get current period selection
            period_type = self.period_var.get()
            
            # Build HTML content
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>P/L Report - {datetime.now().strftime("%d %b %Y %I:%M %p")}</title>
    <style>
        @media print {{
            @page {{ margin: 1cm; }}
            body {{ margin: 0; }}
        }}
        
        body {{
            font-family: Consolas, 'Courier New', monospace;
            max-width: 1000px;
            margin: 20px auto;
            padding: 20px;
            background: white;
        }}
        
        h1 {{
            text-align: center;
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        
        .timestamp {{
            text-align: center;
            color: #7f8c8d;
            margin-bottom: 30px;
        }}
        
        .summary {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .card {{
            border: 2px solid #ecf0f1;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        
        .card-title {{
            font-size: 12px;
            color: #7f8c8d;
            margin-bottom: 10px;
        }}
        
        .card-value {{
            font-size: 24px;
            font-weight: bold;
        }}
        
        .profit {{ color: #27ae60; }}
        .loss {{ color: #e74c3c; }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        
        th {{
            background: #34495e;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }}
        
        td {{
            padding: 10px;
            border-bottom: 1px solid #ecf0f1;
        }}
        
        tr:hover {{
            background: #f8f9fa;
        }}
        
        .footer {{
            margin-top: 40px;
            text-align: center;
            color: #7f8c8d;
            font-size: 12px;
            border-top: 1px solid #ecf0f1;
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <h1>📊 PROFIT/LOSS REPORT</h1>
    <div class="timestamp">Generated on {datetime.now().strftime("%d %b %Y at %I:%M %p")}</div>
    
    <div class="summary">
        <div class="card">
            <div class="card-title">Total Profit</div>
            <div class="card-value profit">{format_money(self.total_profit)}</div>
        </div>
        <div class="card">
            <div class="card-title">Total Loss</div>
            <div class="card-value loss">{format_money_abs(self.total_loss)}</div>
        </div>
        <div class="card">
            <div class="card-title">Net P/L</div>
            <div class="card-value {'profit' if self.net_pnl >= 0 else 'loss'}">{format_money(self.net_pnl)}</div>
        </div>
    </div>
    
    <h2>{period_type} P/L Breakdown</h2>
    <table>
        <thead>
            <tr>
                <th>Period</th>
                <th>Profit</th>
                <th>Loss</th>
                <th>Net P/L</th>
                <th>Running Total</th>
            </tr>
        </thead>
        <tbody>
"""
            
            # Add table rows based on current period view
            for item_id in self.pnl_tree.get_children():
                values = self.pnl_tree.item(item_id, 'values')
                if len(values) >= 5:
                    period_name, profit_str, loss_str, net_str, running_str = values
                    
                    # Determine row color based on net P/L
                    row_class = 'profit' if '₹' in net_str and '-' not in net_str else 'loss' if '-' in net_str else ''
                    
                    html_content += f"""
            <tr>
                <td>{period_name}</td>
                <td class="profit">{profit_str}</td>
                <td class="loss">{loss_str}</td>
                <td class="{row_class}">{net_str}</td>
                <td class="{'profit' if '-' not in running_str else 'loss'}">{running_str}</td>
            </tr>
"""
            
            html_content += """
        </tbody>
    </table>
    
    <div class="footer">
        <p>Trader Ledger - FIFO-based P/L Calculation System</p>
        <p>This report was automatically generated. Please verify all figures.</p>
    </div>
</body>
</html>
"""
            
            # Write HTML file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"✅ Report saved: {filepath}")
            
            # Open in browser
            webbrowser.open(f'file:///{Path(filepath).absolute()}')
            
            messagebox.showinfo(
                "Report Generated",
                f"Print-friendly report created:\n{filepath}\n\nOpening in your default browser..."
            )
            
        except Exception as e:
            logger.error(f"Print report failed: {str(e)}", exc_info=True)
            messagebox.showerror("Print Failed", f"Failed to generate report:\n{str(e)}")

    def on_tab_selected(self) -> None:
        """Called when Reports tab is selected. Triggers recalculation."""
        logger.info("Reports tab selected - triggering automatic recalculation")
        self.calculate_reports()
