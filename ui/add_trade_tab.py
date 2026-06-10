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
from collections import defaultdict
from core.logger import get_logger
from core.utils import format_money, format_money_abs, make_trade_ts
from core.fifo_matcher import fetch_active_trades, match_fifo, FifoMatchError
from core.trade_validation import normalize_trade_classification
from core.brokerage import calculate_brokerage_auto
import config

logger = get_logger('ui.add_trade_tab')

CALENDAR_AVAILABLE: bool
try:
    from tkcalendar import DateEntry  # type: ignore
    CALENDAR_AVAILABLE = True
except ImportError:
    DateEntry = None  # type: ignore
    CALENDAR_AVAILABLE = False
    logger.warning("tkcalendar not installed - using text entry for dates")


class AddTradeTab:
    """Add Trade tab - allows user to input and save trades."""
    
    def __init__(self, parent: ttk.Frame, status_callback: Callable[[str], None]) -> None:
        logger.info("Initializing Add Trade tab")
        self.parent = parent
        self.update_status = status_callback
        self.sell_reference_meta: dict[str, dict[str, int]] = {}
        self.equity_values: list[str] = []
        
        # Create UI
        self.create_widgets()
        self.update_derivative_fields()
        self.update_sell_reference_fields()
        
        # Set default date to today (only for text entry fallback)
        if not CALENDAR_AVAILABLE:
            self.date_entry.insert(0, date.today().strftime('%d-%m-%Y'))
        
        logger.debug("Add Trade tab initialized")
    
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
        
        if CALENDAR_AVAILABLE:
            # Use calendar picker with today's date as default
            self.date_entry = DateEntry(
                main_frame,
                width=18,
                background='darkblue',
                foreground='white',
                borderwidth=2,
                date_pattern='dd-mm-yyyy',
                font=('Consolas', 10)
            )
            self.date_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        else:
            # Fallback to text entry
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
        self.equity_entry.bind('<KeyRelease>', self._filter_equity_suggestions)
        self.equity_var.trace_add('write', lambda *_: self.update_sell_reference_fields())
        row += 1
        
        # Trade Type
        ttk.Label(main_frame, text="Trade Type:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.trade_type_var = tk.StringVar(value='BUY')
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        ttk.Radiobutton(type_frame, text="BUY", variable=self.trade_type_var, value='BUY').pack(side='left', padx=5)
        ttk.Radiobutton(type_frame, text="SELL", variable=self.trade_type_var, value='SELL').pack(side='left', padx=5)
        self.trade_type_var.trace_add('write', lambda *_: self.update_sell_reference_fields())
        row += 1

        # Type1 (classification)
        ttk.Label(main_frame, text="Type1:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.type1_var = tk.StringVar(value='DELIVERY')
        self.type1_entry = ttk.Combobox(
            main_frame,
            textvariable=self.type1_var,
            width=18,
            state='readonly',
            values=['INTRADAY', 'DELIVERY', 'MTF', 'FUTURES', 'OPTIONS'],
            font=('Consolas', 10)
        )
        self.type1_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.type1_entry.bind('<<ComboboxSelected>>', lambda _e: self.update_derivative_fields())
        ttk.Label(main_frame, text="(classification)", font=('Consolas', 9), foreground='gray').grid(row=row, column=2, sticky='w', padx=5)
        row += 1

        # Type2 (options only)
        self.type2_label = ttk.Label(main_frame, text="Type2:", font=('Consolas', 10))
        self.type2_label.grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.type2_var = tk.StringVar(value='')
        self.type2_entry = ttk.Combobox(
            main_frame,
            textvariable=self.type2_var,
            width=18,
            state='readonly',
            values=['CE', 'PE'],
            font=('Consolas', 10)
        )
        self.type2_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.type2_hint = ttk.Label(main_frame, text="(CE/PE for options)", font=('Consolas', 9), foreground='gray')
        self.type2_hint.grid(row=row, column=2, sticky='w', padx=5)
        self.type2_entry.bind('<<ComboboxSelected>>', lambda _e: self.update_sell_reference_fields())
        row += 1

        # Strike (options only)
        self.strike_label = ttk.Label(main_frame, text="Strike:", font=('Consolas', 10))
        self.strike_label.grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.strike_entry = ttk.Entry(main_frame, width=20, font=('Consolas', 10))
        self.strike_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.strike_hint = ttk.Label(main_frame, text="(options only)", font=('Consolas', 9), foreground='gray')
        self.strike_hint.grid(row=row, column=2, sticky='w', padx=5)
        self.strike_entry.bind('<FocusOut>', lambda _e: self.update_sell_reference_fields())
        row += 1

        # Expiry (options/futures)
        self.expiry_label = ttk.Label(main_frame, text="Expiry:", font=('Consolas', 10))
        self.expiry_label.grid(row=row, column=0, sticky='e', padx=5, pady=8)
        if CALENDAR_AVAILABLE:
            self.expiry_entry = DateEntry(
                main_frame,
                width=18,
                background='darkblue',
                foreground='white',
                borderwidth=2,
                date_pattern='dd-mm-yyyy',
                font=('Consolas', 10)
            )
            self.expiry_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
            self.expiry_entry.delete(0, 'end')
            self.expiry_hint = ttk.Label(main_frame, text="", font=('Consolas', 9))
            self.expiry_hint.grid(row=row, column=2, sticky='w', padx=5)
            self.expiry_entry.bind('<<DateEntrySelected>>', lambda _e: self.update_sell_reference_fields())
        else:
            self.expiry_entry = ttk.Entry(main_frame, width=20, font=('Consolas', 10))
            self.expiry_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
            self.expiry_hint = ttk.Label(main_frame, text="(DD-MM-YYYY)", font=('Consolas', 9), foreground='gray')
            self.expiry_hint.grid(row=row, column=2, sticky='w', padx=5)
            self.expiry_entry.bind('<FocusOut>', lambda _e: self.update_sell_reference_fields())
        row += 1

        # Sell reference (SELL only)
        self.sell_ref_label = ttk.Label(main_frame, text="Sell Against:", font=('Consolas', 10))
        self.sell_ref_label.grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.sell_ref_var = tk.StringVar()
        self.sell_ref_entry = ttk.Combobox(
            main_frame,
            textvariable=self.sell_ref_var,
            width=28,
            state='readonly',
            font=('Consolas', 10)
        )
        self.sell_ref_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.sell_ref_hint = ttk.Label(
            main_frame,
            text="(reference only; FIFO applies)",
            font=('Consolas', 9),
            foreground='gray'
        )
        self.sell_ref_hint.grid(row=row, column=2, sticky='w', padx=5)
        self.sell_ref_entry.bind('<<ComboboxSelected>>', lambda _e: self.update_price_preview())
        row += 1
        
        # Quantity
        ttk.Label(main_frame, text="Quantity:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.quantity_entry = ttk.Entry(main_frame, width=20, font=('Consolas', 10))
        self.quantity_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        ttk.Label(main_frame, text="(shares)", font=('Consolas', 9), foreground='gray').grid(row=row, column=2, sticky='w', padx=5)
        self.quantity_entry.bind('<KeyRelease>', lambda _e: (self.update_brokerage_state(), self.update_price_preview()))
        row += 1
        
        # Price
        ttk.Label(main_frame, text="Price:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.price_entry = ttk.Entry(main_frame, width=20, font=('Consolas', 10))
        self.price_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        ttk.Label(main_frame, text="(₹ per share)", font=('Consolas', 9), foreground='gray').grid(row=row, column=2, sticky='w', padx=5)
        self.price_entry.bind('<KeyRelease>', lambda _e: (self.update_brokerage_state(), self.update_price_preview()))
        row += 1
        
        # Brokerage
        ttk.Label(main_frame, text="Brokerage:", font=('Consolas', 10)).grid(row=row, column=0, sticky='e', padx=5, pady=8)
        brokerage_frame = ttk.Frame(main_frame)
        brokerage_frame.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.brokerage_entry = ttk.Entry(brokerage_frame, width=12, font=('Consolas', 10))
        self.brokerage_entry.pack(side='left')
        self.brokerage_entry.insert(0, "0")  # Default to 0
        self.override_brokerage_var = tk.BooleanVar(value=False)
        self.override_brokerage_check = ttk.Checkbutton(
            brokerage_frame,
            text="Override",
            variable=self.override_brokerage_var,
            command=self.update_brokerage_state
        )
        self.override_brokerage_check.pack(side='left', padx=(8, 0))
        ttk.Label(main_frame, text="(₹)", font=('Consolas', 9), foreground='gray').grid(row=row, column=2, sticky='w', padx=5)
        self.brokerage_entry.bind('<KeyRelease>', lambda _e: self.update_price_preview())
        row += 1

        # Real-time P/L preview (updates when SELL reference, qty, price or brokerage change)
        self.pnl_preview_label = ttk.Label(main_frame, text="", font=('Consolas', 10), foreground='#34495e')
        self.pnl_preview_label.grid(row=row, column=1, sticky='w', padx=5, pady=(0, 8))
        row += 1

        # MTF amount (BUY only, MTF type)
        self.mtf_amount_label = ttk.Label(main_frame, text="MTF Amount:", font=('Consolas', 10))
        self.mtf_amount_label.grid(row=row, column=0, sticky='e', padx=5, pady=8)
        self.mtf_amount_entry = ttk.Entry(main_frame, width=20, font=('Consolas', 10))
        self.mtf_amount_entry.grid(row=row, column=1, sticky='w', padx=5, pady=8)
        self.mtf_amount_hint = ttk.Label(main_frame, text="(₹, BUY only for MTF)", font=('Consolas', 9), foreground='gray')
        self.mtf_amount_hint.grid(row=row, column=2, sticky='w', padx=5)
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

    def update_derivative_fields(self) -> None:
        """Enable/disable derivative fields based on Type1 selection."""
        type1 = self.type1_var.get().strip().lower()
        is_options = type1 == 'options'
        is_futures = type1 == 'futures'

        def show_option_fields() -> None:
            self.type2_label.grid()
            self.type2_entry.grid()
            self.type2_hint.grid()
            self.strike_label.grid()
            self.strike_entry.grid()
            self.strike_hint.grid()
            self.expiry_label.grid()
            self.expiry_entry.grid()
            self.expiry_hint.grid()

        def show_futures_fields() -> None:
            self.type2_label.grid_remove()
            self.type2_entry.grid_remove()
            self.type2_hint.grid_remove()
            self.strike_label.grid_remove()
            self.strike_entry.grid_remove()
            self.strike_hint.grid_remove()
            self.expiry_label.grid()
            self.expiry_entry.grid()
            self.expiry_hint.grid()

        def hide_all_derivative_fields() -> None:
            self.type2_label.grid_remove()
            self.type2_entry.grid_remove()
            self.type2_hint.grid_remove()
            self.strike_label.grid_remove()
            self.strike_entry.grid_remove()
            self.strike_hint.grid_remove()
            self.expiry_label.grid_remove()
            self.expiry_entry.grid_remove()
            self.expiry_hint.grid_remove()

        if is_options:
            show_option_fields()
        elif is_futures:
            self.type2_var.set('')
            self.strike_entry.delete(0, tk.END)
            show_futures_fields()
        else:
            self.type2_var.set('')
            self.strike_entry.delete(0, tk.END)
            self.expiry_entry.delete(0, tk.END)
            hide_all_derivative_fields()

        self._update_mtf_amount_visibility()
        self.update_brokerage_state()
        self.update_sell_reference_fields()

    def update_sell_reference_fields(self) -> None:
        """Show or hide SELL reference selector and refresh options."""
        if self.trade_type_var.get() != 'SELL':
            self.sell_ref_label.grid_remove()
            self.sell_ref_entry.grid_remove()
            self.sell_ref_hint.grid_remove()
            self.sell_ref_var.set('')
            self._update_mtf_amount_visibility()
            return

        self.sell_ref_label.grid()
        self.sell_ref_entry.grid()
        self.sell_ref_hint.grid()
        self.load_sell_reference_options()
        self.update_brokerage_state()
        self._update_mtf_amount_visibility()

    def _update_mtf_amount_visibility(self) -> None:
        type1 = self.type1_var.get().strip().lower()
        is_mtf_buy = type1 == 'mtf' and self.trade_type_var.get() == 'BUY'
        if is_mtf_buy:
            self.mtf_amount_label.grid()
            self.mtf_amount_entry.grid()
            self.mtf_amount_hint.grid()
        else:
            self.mtf_amount_label.grid_remove()
            self.mtf_amount_entry.grid_remove()
            self.mtf_amount_hint.grid_remove()

    def update_brokerage_state(self) -> None:
        """Update brokerage field based on override and configured rates."""
        type1 = self.type1_var.get().strip().lower()
        trade_type = self.trade_type_var.get().strip().upper()

        if self.override_brokerage_var.get():
            self.brokerage_entry.config(state='normal')
            return

        try:
            qty = int(self.quantity_entry.get().strip() or 0)
            price_paise = int(float(self.price_entry.get().strip() or 0) * 100)
        except Exception:
            qty = 0
            price_paise = 0

        if qty <= 0 or price_paise <= 0:
            self.brokerage_entry.config(state='normal')
            self.brokerage_entry.delete(0, tk.END)
            self.brokerage_entry.insert(0, "0")
            self.brokerage_entry.config(state='disabled')
            return

        try:
            auto_brokerage, _rate_ppm = calculate_brokerage_auto(qty, price_paise, type1, trade_type)
            self.brokerage_entry.config(state='normal')
            self.brokerage_entry.delete(0, tk.END)
            self.brokerage_entry.insert(0, f"{auto_brokerage / 100:.2f}")
            self.brokerage_entry.config(state='disabled')
        except Exception:
            # Require override when rate not configured
            self.override_brokerage_var.set(True)
            self.brokerage_entry.config(state='normal')
            if not self.brokerage_entry.get().strip():
                self.brokerage_entry.insert(0, "0")
            self.update_status(
                f"Auto brokerage not configured for {type1.upper()} {trade_type}. Enable Override to enter manually."
            )

    def get_classification_inputs(self) -> tuple[str, str, str, str]:
        """Collect classification inputs with safe defaults for disabled fields."""
        type1 = self.type1_var.get()
        type1_norm = type1.strip().lower()
        type2 = self.type2_var.get()
        strike = self.strike_entry.get()
        expiry = self.expiry_entry.get()

        if type1_norm not in ('options', 'futures'):
            return type1, '', '', ''
        if type1_norm == 'futures':
            return type1, '', '', expiry
        return type1, type2, strike, expiry

    def load_sell_reference_options(self) -> None:
        """Load open BUY lots for the selected contract (reference only)."""
        self.sell_reference_meta = {}
        self.sell_ref_entry['values'] = []
        self.sell_ref_var.set('')

        equity = self.equity_entry.get().strip().upper()
        if not equity:
            return

        try:
            type1_in, type2_in, strike_in, expiry_in = self.get_classification_inputs()
            type1, type2, strike, expiry = normalize_trade_classification(
                type1_in,
                type2_in,
                strike_in,
                expiry_in,
                require_type1=True
            )
        except ValueError:
            return

        try:
            trades = fetch_active_trades()
            matches = match_fifo(trades) or []
        except FifoMatchError as exc:
            logger.warning(f"Could not load SELL references: {str(exc)}")
            return
        except Exception as exc:
            logger.warning(f"Could not load SELL references: {str(exc)}")
            return

        matched_by_buy: dict[int, int] = defaultdict(int)
        for match in matches:
            matched_by_buy[match['buy_id']] += match['matched_quantity']

        options: list[tuple[str, str]] = []
        for trade in trades:
            (trade_id, trade_date, trade_equity, trade_type, trade_type1,
             trade_type2, trade_strike, trade_expiry, quantity, price_paise,
             _brokerage, _notes, _is_active, _brokerage_auto, _brokerage_override, _mtf_amount) = trade

            if trade_type != 'BUY':
                continue
            if trade_equity.strip().upper() != equity:
                continue
            if trade_type1 != type1 or trade_type2 != type2 or trade_strike != strike or trade_expiry != expiry:
                continue

            matched_qty = matched_by_buy.get(trade_id, 0)
            remaining = quantity - matched_qty
            if remaining <= 0:
                continue

            year, month, day = trade_date.split('-')
            display_date = f"{day}-{month}-{year}"
            price_display = format_money_abs(price_paise)
            option_label = f"BUY #{trade_id} | {display_date} | Rem {remaining} | {price_display}"
            # Store additional metadata for preview calculation
            self.sell_reference_meta[option_label] = {
                'buy_id': trade_id,
                'remaining_qty': remaining,
                'buy_price_paise': price_paise,
                'buy_brokerage_paise': _brokerage,
                'buy_qty': quantity
            }
            options.append((trade_date, option_label))

        options.sort(key=lambda item: item[0])
        self.sell_ref_entry['values'] = [label for _date, label in options]
        # Update preview after loading options
        try:
            self.update_price_preview()
        except Exception:
            pass

    def _get_selected_sell_reference(self) -> dict[str, int] | None:
        """Return selected SELL reference metadata if available."""
        selected = self.sell_ref_var.get().strip()
        if not selected:
            return None
        return self.sell_reference_meta.get(selected)

    def update_price_preview(self) -> None:
        """Update the estimated P/L preview for a SELL trade based on selected reference."""
        try:
            if self.trade_type_var.get() != 'SELL':
                self.pnl_preview_label.config(text="")
                return

            selected = self._get_selected_sell_reference()
            if not selected:
                self.pnl_preview_label.config(text="Select a BUY lot to preview P/L")
                return

            qty_text = self.quantity_entry.get().strip()
            price_text = self.price_entry.get().strip()
            brokerage_text = self.brokerage_entry.get().strip()

            try:
                qty = int(qty_text)
                if qty <= 0:
                    raise ValueError()
            except Exception:
                self.pnl_preview_label.config(text="Enter valid Quantity to preview P/L")
                return

            try:
                sell_price_paise = int(float(price_text) * 100)
            except Exception:
                self.pnl_preview_label.config(text="Enter valid Price to preview P/L")
                return

            try:
                sell_brokerage_paise = int(float(brokerage_text) * 100)
            except Exception:
                sell_brokerage_paise = 0

            # Cap qty at remaining
            remaining = selected.get('remaining_qty', 0)
            use_qty = min(qty, remaining)

            buy_price_paise = selected.get('buy_price_paise', 0)
            buy_brokerage_paise = selected.get('buy_brokerage_paise', 0)
            buy_qty = selected.get('buy_qty', 1)

            # Proportion of buy brokerage attributable to matched quantity
            matched_buy_brokerage = (buy_brokerage_paise * use_qty) // buy_qty if buy_qty else 0

            pnl_paise = (sell_price_paise - buy_price_paise) * use_qty - (sell_brokerage_paise + matched_buy_brokerage)

            # Format
            sign = '-' if pnl_paise < 0 else '+'
            self.pnl_preview_label.config(text=f"Estimated realized P/L for {use_qty} units: {sign} {format_money(abs(pnl_paise))}")

        except Exception:
            self.pnl_preview_label.config(text="Preview unavailable")
    
    def create_recent_trades_table(self, parent: ttk.Frame, row: int) -> None:
        """Create table showing last 5 trades. Display-only, no logic."""
        from ui.widgets import create_treeview
        
        columns = [
            ('Date', 'Date', 100, 'center'),
            ('Stock', 'Stock', 80, 'center'),
            ('Type', 'Type', 60, 'center'),
            ('Qty', 'Qty', 60, 'center'),
            ('Price', 'Price', 100, 'e'),
            ('Total', 'Total', 120, 'e')
        ]
        
        tree_frame, self.recent_tree = create_treeview(parent, columns, height=5)
        tree_frame.grid(row=row, column=0, columnspan=4, sticky='nsew', pady=5)
        
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
        """Load unique equity symbols from database for autocomplete using DB layer."""
        try:
            from core.db_operations import get_unique_equities
            equities = get_unique_equities(config.PRIMARY_PROFILE_ID)
            self.equity_values = equities
            self.equity_entry['values'] = equities
            logger.debug(f"Loaded {len(equities)} unique equities for dropdown")
        except Exception as e:
            logger.error(f"Failed to load equities: {str(e)}")
            self.equity_values = []
            self.equity_entry['values'] = []

    def _filter_equity_suggestions(self, _event: tk.Event) -> None:
        """Filter equity suggestions based on current input."""
        text = self.equity_var.get().strip().upper()
        cursor_pos = self.equity_entry.index(tk.INSERT)
        if not self.equity_values:
            self.equity_entry['values'] = []
            return

        if not text:
            self.equity_entry['values'] = self.equity_values
            return

        filtered = [e for e in self.equity_values if text in e.upper()]
        self.equity_entry['values'] = filtered
        self.equity_entry.focus_set()
        self.equity_entry.icursor(cursor_pos)
    
    def _gather_form_data(self) -> dict:
        if CALENDAR_AVAILABLE:
            try:
                date_str = self.date_entry.get_date().strftime('%d-%m-%Y')
            except:
                date_str = self.date_entry.get().strip()
        else:
            date_str = self.date_entry.get().strip()
            
        type1, type2, strike, expiry = self.get_classification_inputs()
        
        return {
            'date_str': date_str,
            'equity': self.equity_entry.get().strip(),
            'trade_type': self.trade_type_var.get().strip().upper(),
            'quantity': self.quantity_entry.get(),
            'price': self.price_entry.get(),
            'brokerage': self.brokerage_entry.get(),
            'override_brokerage': self.override_brokerage_var.get(),
            'classification': (type1, type2, strike, expiry),
            'mtf_amount': self.mtf_amount_entry.get().strip(),
            'selected_sell_reference': self._get_selected_sell_reference(),
            'sell_reference_meta': self.sell_reference_meta,
            'notes': self.notes_entry.get('1.0', 'end-1c').strip()
        }

    def save_trade(self) -> None:
        """Save trade to database using Trade Manager."""
        from core import trade_manager
        
        data = self._gather_form_data()
        
        is_valid, error_msg = trade_manager.validate_trade_data(data)
        if not is_valid:
            messagebox.showerror("Invalid Input", error_msg)
            return
            
        try:
            profile_id = int(config.PRIMARY_PROFILE_ID) if config.PRIMARY_PROFILE_ID is not None else None
        except Exception:
            profile_id = None
            
        if profile_id is None:
            messagebox.showwarning("Select Profile", "Multiple profiles or Combined Family view selected. Select a single profile first.")
            return
            
        try:
            trade_id = trade_manager.save_trade(data, profile_id)
            trade_type = data['trade_type']
            quantity = data['quantity']
            equity = data['equity'].upper()
            price = data['price']
            
            logger.info(f"✅ Trade saved successfully - ID: {trade_id}")
            self.update_status(f"✅ Trade saved: {trade_type} {quantity} {equity} @ ₹{price}")
            messagebox.showinfo("Success", f"Trade saved successfully!\n\n{trade_type} {quantity} {equity}")
            
            self.refresh_recent_trades()
            self.load_equity_dropdown()
            self.clear_form()
        except Exception as e:
            logger.error(f"❌ Failed to save trade: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to save trade:\n{str(e)}")
            self.update_status(f"❌ Error saving trade")

    def refresh_recent_trades(self) -> None:
        """Load last 5 trades for display using Trade Manager."""
        logger.debug("Refreshing recent trades display")
        
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)
            
        from core import trade_manager
        try:
            trades = trade_manager.get_recent_trades(config.PRIMARY_PROFILE_ID)
            
            for trade in trades:
                trade_date, equity, trade_type, quantity, price_paise, brokerage_paise = trade
                
                if trade_type == 'BUY':
                    total_paise = (quantity * price_paise) + brokerage_paise
                else:  # SELL
                    total_paise = (quantity * price_paise) - brokerage_paise
                    
                year, month, day = trade_date.split('-')
                display_date = f"{day}-{month}-{year}"
                
                from core.utils import format_money
                self.recent_tree.insert('', 'end', values=(
                    display_date, equity, trade_type, quantity,
                    format_money(price_paise), format_money(total_paise)
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
        self.type1_var.set('DELIVERY')
        self.type2_var.set('')
        self.strike_entry.delete(0, tk.END)
        self.expiry_entry.delete(0, tk.END)
        self.update_derivative_fields()
        self.sell_ref_var.set('')
        self.sell_reference_meta = {}
        self.update_sell_reference_fields()
        self.quantity_entry.delete(0, tk.END)
        self.price_entry.delete(0, tk.END)
        self.brokerage_entry.delete(0, tk.END)
        self.brokerage_entry.insert(0, "0")
        self.override_brokerage_var.set(False)
        self.mtf_amount_entry.delete(0, tk.END)
        self.notes_entry.delete('1.0', tk.END)
        self.equity_entry.focus()
        self.update_status("Form cleared")
