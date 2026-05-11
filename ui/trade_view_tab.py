"""Trade View tab - human-readable trade units."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable
from datetime import datetime

from core.fifo_matcher import fetch_active_trades, match_fifo
from core.pnl_calculator import calculate_match_pnl
from core.mtf_interest import apply_mtf_interest
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
        self.search_var = tk.StringVar(value="")
        self.sort_var = tk.StringVar(value="Date")
        self.show_raw_var = tk.BooleanVar(value=False)
        self.total_trades_var = tk.StringVar(value="0")
        self.closed_trades_var = tk.StringVar(value="0")
        self.open_trades_var = tk.StringVar(value="0")
        self.total_pnl_var = tk.StringVar(value="₹ 0.00")
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

        summary_frame = ttk.Frame(main_frame)
        summary_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(summary_frame, text="Total Trades:", font=('Arial', 9)).pack(side='left', padx=(0, 4))
        ttk.Label(summary_frame, textvariable=self.total_trades_var, font=('Consolas', 10, 'bold')).pack(side='left', padx=(0, 12))

        ttk.Label(summary_frame, text="Closed:", font=('Arial', 9)).pack(side='left', padx=(0, 4))
        ttk.Label(summary_frame, textvariable=self.closed_trades_var, font=('Consolas', 10, 'bold')).pack(side='left', padx=(0, 12))

        ttk.Label(summary_frame, text="Open:", font=('Arial', 9)).pack(side='left', padx=(0, 4))
        ttk.Label(summary_frame, textvariable=self.open_trades_var, font=('Consolas', 10, 'bold')).pack(side='left', padx=(0, 12))

        ttk.Label(summary_frame, text="Total P/L (realized):", font=('Arial', 9)).pack(side='left', padx=(0, 4))
        ttk.Label(summary_frame, textvariable=self.total_pnl_var, font=('Consolas', 10, 'bold')).pack(side='left')

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

        ttk.Label(controls, text="Sort by:", font=('Arial', 10)).pack(side='left', padx=(20, 5))
        self.sort_entry = ttk.Combobox(
            controls,
            textvariable=self.sort_var,
            values=["Date", "Profit/Loss", "Holding Days"],
            state='readonly',
            width=14
        )
        self.sort_entry.pack(side='left', padx=(0, 10))
        self.sort_entry.bind('<<ComboboxSelected>>', lambda _e: self.refresh_units())

        ttk.Label(controls, text="Search:", font=('Arial', 10)).pack(side='left', padx=(20, 5))
        self.search_entry = ttk.Entry(controls, textvariable=self.search_var, width=28)
        self.search_entry.pack(side='left', padx=(0, 10))
        self.search_entry.bind('<KeyRelease>', lambda _e: self.refresh_units())

        ttk.Checkbutton(
            controls,
            text="Show raw trades",
            variable=self.show_raw_var,
            command=self.refresh_units
        ).pack(side='left', padx=(10, 0))

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
            'P/L', 'MTF Interest', 'Net P/L', 'Holding Days', 'Status', 'Remaining Qty'
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

        self.units_tree.column('Trade Label', width=420, anchor='w')
        self.units_tree.column('Contract', width=260, anchor='w')
        self.units_tree.column('Buy Qty', width=80, anchor='e')
        self.units_tree.column('Avg Buy', width=100, anchor='e')
        self.units_tree.column('Sell Qty', width=80, anchor='e')
        self.units_tree.column('Avg Sell', width=100, anchor='e')
        self.units_tree.column('P/L', width=100, anchor='e')
        self.units_tree.column('MTF Interest', width=110, anchor='e')
        self.units_tree.column('Net P/L', width=110, anchor='e')
        self.units_tree.column('Holding Days', width=90, anchor='center')
        self.units_tree.column('Status', width=80, anchor='center')
        self.units_tree.column('Remaining Qty', width=110, anchor='e')

        self.units_tree.tag_configure('profit', foreground='#27ae60')
        self.units_tree.tag_configure('loss', foreground='#e74c3c')
        self.units_tree.tag_configure('detail', foreground='gray')
        self.units_tree.tag_configure('open', foreground='#2c3e50')
        self.units_tree.tag_configure('status_open', background='#fff9e6')
        self.units_tree.tag_configure('status_closed', background='#eef7ff')

        self.units_tree.pack(fill='both', expand=True)

        self.help_tip = ttk.Label(
            main_frame,
            text="Remaining Investment = FIFO remaining cost (incl. brokerage).",
            font=('Arial', 9),
            foreground='gray'
        )
        self.help_tip.pack(anchor='w', pady=(6, 0))

    def refresh_units(self) -> None:
        """Reload trade units and update the table."""
        for item in self.units_tree.get_children():
            self.units_tree.delete(item)

        try:
            trades = fetch_active_trades()
            if not trades:
                self.units_tree.insert('', 'end', values=(
                    "No trades found", "", "", "", "", "", "", "", "", "", "", ""
                ), tags=('detail',))
                return

            matches = match_fifo(trades)
            if not matches:
                self.units_tree.insert('', 'end', values=(
                    "No SELL trades yet", "", "", "", "", "", "", "", "", "", "", ""
                ), tags=('detail',))
                return

            trades_by_id = build_trades_by_id(trades)
            pnl_results = calculate_match_pnl(matches, trades_by_id)
            pnl_results = apply_mtf_interest(pnl_results, trades_by_id)
            units = build_trade_units(
                trades,
                pnl_results,
                grouping=self.grouping_var.get()
            )

            # Apply search filter if provided
            search_term = self.search_var.get().strip().lower()
            if search_term:
                units = [u for u in units if (
                    search_term in (u.get('trade_label') or '').lower()
                    or search_term in (u.get('contract_display') or '').lower()
                    or search_term in (u.get('equity') or '').lower()
                )]

            units = self._sort_units(units)
            self._update_summary(units)

            for unit in units:
                pnl_display = format_money(unit['realized_pnl'])
                mtf_display = format_money_abs(unit.get('mtf_interest', 0)) if unit.get('mtf_interest') else ""
                net_display = format_money(unit.get('net_pnl', unit['realized_pnl']))
                avg_buy_display = format_money_abs(unit['avg_buy_price'])
                avg_sell_display = format_money_abs(unit['avg_sell_price']) if unit['total_sell_qty'] else ""

                remaining_display = f"{unit['remaining_qty']:,}" if unit['remaining_qty'] else ""
                holding_display = str(unit['holding_days']) if unit['holding_days'] else ""

                net_pnl_value = unit.get('net_pnl', unit['realized_pnl'])
                row_tag = 'profit' if net_pnl_value > 0 else 'loss' if net_pnl_value < 0 else 'open'
                status_tag = 'status_closed' if unit['status'] == 'Closed' else 'status_open'

                parent_id = self.units_tree.insert('', 'end', values=(
                    unit['trade_label'],
                    unit['contract_display'],
                    f"{unit['total_buy_qty']:,}",
                    avg_buy_display,
                    f"{unit['total_sell_qty']:,}" if unit['total_sell_qty'] else "",
                    avg_sell_display,
                    pnl_display,
                    mtf_display,
                    net_display,
                    holding_display,
                    unit['status'],
                    remaining_display
                ), tags=(row_tag, status_tag))

                detail_text = f"Buy IDs: {', '.join(map(str, unit['buy_trade_ids'])) or '-'}"
                detail_text += f" | Sell IDs: {', '.join(map(str, unit['sell_trade_ids'])) or '-'}"
                if unit.get('mtf_interest'):
                    detail_text += f" | MTF Interest: {format_money_abs(unit['mtf_interest'])}"

                if unit['status'] == 'Open':
                    remaining_display = format_money_abs(unit['remaining_investment'])
                    detail_text += f" | Remaining Investment: {remaining_display}"

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
                    "",
                    "",
                    ""
                ), tags=('detail',))

                if self.show_raw_var.get():
                    self._insert_raw_trades(parent_id, unit, trades)

            self.update_status(f"Loaded {len(units)} trade units")

        except Exception as exc:
            logger.error(f"Failed to load trade units: {str(exc)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load trade units:\n{str(exc)}")
            self.update_status("❌ Error loading trade units")

    def _sort_units(self, units: list[dict]) -> list[dict]:
        mode = self.sort_var.get().strip().lower()
        if mode == "profit/loss":
            return sorted(units, key=lambda u: u['realized_pnl'], reverse=True)
        if mode == "holding days":
            return sorted(units, key=lambda u: u['holding_days'], reverse=True)

        def sort_date(unit: dict) -> datetime:
            date_str = unit.get('end_date') or unit.get('start_date')
            if not date_str:
                return datetime.min
            return datetime.strptime(date_str, "%Y-%m-%d")

        return sorted(units, key=sort_date, reverse=True)

    def _update_summary(self, units: list[dict]) -> None:
        total_trades = len(units)
        closed_trades = sum(1 for u in units if u['status'] == 'Closed')
        open_trades = sum(1 for u in units if u['status'] == 'Open')
        total_pnl = sum(u.get('net_pnl', u['realized_pnl']) for u in units)

        self.total_trades_var.set(str(total_trades))
        self.closed_trades_var.set(str(closed_trades))
        self.open_trades_var.set(str(open_trades))
        self.total_pnl_var.set(format_money(total_pnl))

    def _insert_raw_trades(self, parent_id: str, unit: dict, trades: list[tuple]) -> None:
        trades_by_id = {trade[0]: trade for trade in trades}
        trade_ids = unit['buy_trade_ids'] + unit['sell_trade_ids']
        for trade_id in trade_ids:
            trade = trades_by_id.get(trade_id)
            if not trade:
                continue
            trade_date = datetime.strptime(trade[1], "%Y-%m-%d").strftime("%d %b %Y")
            trade_type = trade[3]
            qty = trade[8]
            price = format_money_abs(trade[9])
            brokerage = format_money_abs(trade[10])
            detail = f"{trade_date} | {trade_type} {qty} @ {price} | Brk {brokerage}"

            self.units_tree.insert(parent_id, 'end', values=(
                detail,
                "",
                "",
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
