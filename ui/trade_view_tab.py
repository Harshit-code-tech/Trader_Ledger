"""Trade View tab - human-readable trade units."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable

from core.fifo_matcher import fetch_active_trades, match_fifo
from core.pnl_calculator import calculate_match_pnl
from core.run_ledger import build_trades_by_id
from core.trade_units import build_trade_units
from core.utils import format_money, format_money_abs
from core.logger import get_logger

logger = get_logger('ui.trade_view_tab')


class TradeViewTab:
    """Trade View tab - shows grouped trade units for non-technical users."""

    def __init__(self, parent: ttk.Frame, status_callback: Callable[[str], None]) -> None:
        self.parent = parent
        self.update_status = status_callback
        self.grouping_var = tk.StringVar(value="lifecycle")
        self.create_widgets()
        self.refresh_units()

    def create_widgets(self) -> None:
        main_frame = ttk.Frame(self.parent, padding="10")
        main_frame.pack(fill='both', expand=True)

        header = ttk.Label(
            main_frame,
            text="TRADE VIEW",
            font=('Consolas', 16, 'bold')
        )
        header.pack(pady=(0, 10))

        controls = ttk.Frame(main_frame)
        controls.pack(fill='x', pady=(0, 10))

        ttk.Label(controls, text="Group by:", font=('Arial', 10)).pack(side='left', padx=(0, 5))
        ttk.Radiobutton(
            controls,
            text="Lifecycle",
            variable=self.grouping_var,
            value="lifecycle",
            command=self.refresh_units
        ).pack(side='left', padx=5)
        ttk.Radiobutton(
            controls,
            text="Sell",
            variable=self.grouping_var,
            value="sell",
            command=self.refresh_units
        ).pack(side='left', padx=5)

        ttk.Button(
            controls,
            text="Refresh",
            command=self.refresh_units,
            width=12
        ).pack(side='right')

        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill='both', expand=True)

        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side='right', fill='y')

        columns = (
            'Trade Label', 'Contract', 'Buy Qty', 'Avg Buy', 'Sell Qty', 'Avg Sell',
            'P/L', 'Holding Days', 'Status', 'Remaining Qty'
        )

        self.units_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show='tree headings',
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.units_tree.yview)

        self.units_tree.heading('#0', text='')
        self.units_tree.column('#0', width=24, stretch=False)

        for col in columns:
            self.units_tree.heading(col, text=col)

        self.units_tree.column('Trade Label', width=240, anchor='w')
        self.units_tree.column('Contract', width=220, anchor='w')
        self.units_tree.column('Buy Qty', width=80, anchor='e')
        self.units_tree.column('Avg Buy', width=100, anchor='e')
        self.units_tree.column('Sell Qty', width=80, anchor='e')
        self.units_tree.column('Avg Sell', width=100, anchor='e')
        self.units_tree.column('P/L', width=100, anchor='e')
        self.units_tree.column('Holding Days', width=90, anchor='center')
        self.units_tree.column('Status', width=80, anchor='center')
        self.units_tree.column('Remaining Qty', width=110, anchor='e')

        self.units_tree.tag_configure('profit', foreground='#27ae60')
        self.units_tree.tag_configure('loss', foreground='#e74c3c')
        self.units_tree.tag_configure('detail', foreground='gray')
        self.units_tree.tag_configure('open', foreground='#2c3e50')

        self.units_tree.pack(fill='both', expand=True)

    def refresh_units(self) -> None:
        """Reload trade units and update the table."""
        for item in self.units_tree.get_children():
            self.units_tree.delete(item)

        try:
            trades = fetch_active_trades()
            if not trades:
                self.units_tree.insert('', 'end', values=(
                    "No trades found", "", "", "", "", "", "", "", "", ""
                ), tags=('detail',))
                return

            matches = match_fifo(trades)
            if not matches:
                self.units_tree.insert('', 'end', values=(
                    "No SELL trades yet", "", "", "", "", "", "", "", "", ""
                ), tags=('detail',))
                return

            trades_by_id = build_trades_by_id(trades)
            pnl_results = calculate_match_pnl(matches, trades_by_id)
            units = build_trade_units(trades, pnl_results, grouping=self.grouping_var.get())

            for unit in units:
                pnl_display = format_money(unit['realized_pnl'])
                avg_buy_display = format_money_abs(unit['avg_buy_price'])
                avg_sell_display = format_money_abs(unit['avg_sell_price']) if unit['total_sell_qty'] else ""

                remaining_display = f"{unit['remaining_qty']:,}" if unit['remaining_qty'] else ""
                holding_display = str(unit['holding_days']) if unit['holding_days'] else ""

                row_tag = 'profit' if unit['realized_pnl'] > 0 else 'loss' if unit['realized_pnl'] < 0 else 'open'

                parent_id = self.units_tree.insert('', 'end', values=(
                    unit['trade_label'],
                    unit['contract_display'],
                    f"{unit['total_buy_qty']:,}",
                    avg_buy_display,
                    f"{unit['total_sell_qty']:,}" if unit['total_sell_qty'] else "",
                    avg_sell_display,
                    pnl_display,
                    holding_display,
                    unit['status'],
                    remaining_display
                ), tags=(row_tag,))

                detail_text = f"Buy IDs: {', '.join(map(str, unit['buy_trade_ids'])) or '-'}"
                detail_text += f" | Sell IDs: {', '.join(map(str, unit['sell_trade_ids'])) or '-'}"

                if unit['status'] == 'Open':
                    invested_display = format_money_abs(unit['invested_amount'])
                    detail_text += f" | Invested: {invested_display}"

                self.units_tree.insert(parent_id, 'end', values=(
                    detail_text,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    ""
                ), tags=('detail',))

            self.update_status(f"Loaded {len(units)} trade units")

        except Exception as exc:
            logger.error(f"Failed to load trade units: {str(exc)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load trade units:\n{str(exc)}")
            self.update_status("❌ Error loading trade units")
