"""
Main Window - Trader Ledger Application

Creates the main window with notebook tabs.
Phase 1: Only Add Trade tab is functional.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from ui.add_trade_tab import AddTradeTab
from ui.view_records_tab import ViewRecordsTab
from ui.reports_tab import ReportsTab
from ui.trade_view_tab import TradeViewTab
from core.logger import get_logger
import config

logger = get_logger('ui.main_window')


class TraderLedgerApp:
    """Main application window with tabbed interface."""
    
    def __init__(self, root: tk.Tk) -> None:
        logger.info("Initializing main window")
        self.root = root
        self.root.title("📊 Trader Ledger - Baba's Trading App")
        self.root.geometry("900x650")
        
        # Set minimum window size
        self.root.minsize(800, 600)
        logger.debug("Window size set: 900x650, minimum: 800x600")
        
        # Status bar at bottom (create before tabs so callbacks work)
        self.status_bar = tk.Label(
            self.root,
            text="Ready",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=('Arial', 9)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Create notebook (tabs)
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(fill='x', padx=10, pady=(10, 0))

        self.walkthrough_button = ttk.Button(
            self.toolbar,
            text="Walkthrough",
            command=self.show_walkthrough,
            width=14
        )
        self.walkthrough_button.pack(side='right')

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Bind tab selection event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Create tabs
        self.create_tabs()
        self.root.after(400, self.show_onboarding_if_needed)
        logger.info("Main window initialized successfully")
    
    def create_tabs(self) -> None:
        """Create all tabs. Phase 3: All tabs functional."""
        
        # Tab 1: Add Trade (Phase 1 - functional)
        add_trade_frame = ttk.Frame(self.notebook)
        self.notebook.add(add_trade_frame, text="  Add Trade  ")
        self.add_trade_tab = AddTradeTab(add_trade_frame, self.update_status)
        
        # Tab 2: View Records (Phase 2 - functional)
        view_records_frame = ttk.Frame(self.notebook)
        self.notebook.add(view_records_frame, text="  View Records  ")
        self.view_records_tab = ViewRecordsTab(view_records_frame, self.update_status)
        
        # Tab 3: Reports (Phase 3 - functional)
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text="  Reports  ")
        self.reports_tab = ReportsTab(reports_frame, self.update_status)

        # Tab 4: Trade View (Grouped trade units)
        trade_view_frame = ttk.Frame(self.notebook)
        self.notebook.add(trade_view_frame, text="  Trade View  ")
        self.trade_view_tab = TradeViewTab(trade_view_frame, self.update_status)
    
    def on_tab_changed(self, event: tk.Event) -> None:  # type: ignore
        """Handle tab selection changes."""
        selected_tab = self.notebook.select()
        tab_index = self.notebook.index(selected_tab)
        
        # If Reports tab is selected, trigger recalculation
        if tab_index == 2:  # Reports is the 3rd tab (index 2)
            logger.debug("Reports tab selected - triggering recalculation")
            self.reports_tab.on_tab_selected()
        if tab_index == 3:  # Trade View
            logger.debug("Trade View tab selected - refreshing units")
            self.trade_view_tab.refresh_units()
    
    def update_status(self, message: str) -> None:
        """Update status bar message."""
        logger.debug(f"Status update: {message}")
        self.status_bar.config(text=message)
        self.root.update_idletasks()

    def show_onboarding_if_needed(self) -> None:
        """Show first-run walkthrough unless user has dismissed it."""
        state_path = Path(config.ONBOARDING_STATE_FILE)
        if state_path.exists():
            return

        self._show_onboarding_dialog(state_path, persist_state=True)

    def show_walkthrough(self) -> None:
        """Show the onboarding walkthrough on demand."""
        self._show_onboarding_dialog(Path(config.ONBOARDING_STATE_FILE), persist_state=False)

    def _show_onboarding_dialog(self, state_path: Path, persist_state: bool) -> None:
        """Show walkthrough dialog, optionally persisting dismissal state."""
        if hasattr(self, '_onboarding_dialog') and self._onboarding_dialog.winfo_exists():
            self._onboarding_dialog.lift()
            self._onboarding_dialog.focus_force()
            return

        dialog = tk.Toplevel(self.root)
        self._onboarding_dialog = dialog
        dialog.title("Welcome to Trader Ledger")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.geometry("620x380")

        steps = [
            ("Add Trade", "Enter BUY or SELL trades, choose the stock symbol, and the app fills brokerage automatically when supported."),
            ("View Records", "Review all trades, restore deleted rows, and filter by stock, type, or date."),
            ("Reports", "See realized P/L, holding days, open positions, and trade value summaries."),
            ("Trade View", "Get grouped, human-friendly trade units with gross/net P/L and audit details."),
        ]

        index_var = tk.IntVar(value=0)
        show_again_var = tk.BooleanVar(value=True)

        container = ttk.Frame(dialog, padding=20)
        container.pack(fill='both', expand=True)

        title_label = ttk.Label(container, text="Welcome", font=('Consolas', 16, 'bold'))
        title_label.pack(anchor='w')

        step_title = ttk.Label(container, text="", font=('Consolas', 12, 'bold'))
        step_title.pack(anchor='w', pady=(14, 4))

        step_text = ttk.Label(container, text="", wraplength=560, justify='left', font=('Arial', 10))
        step_text.pack(anchor='w', pady=(0, 16))

        footer_frame = ttk.Frame(container)
        footer_frame.pack(fill='x', side='bottom')

        show_again = ttk.Checkbutton(footer_frame, text="Show this walkthrough on startup", variable=show_again_var)
        show_again.pack(side='left')

        def render_step() -> None:
            idx = index_var.get()
            title, text = steps[idx]
            step_title.config(text=f"Step {idx + 1} of {len(steps)}: {title}")
            step_text.config(text=text)
            back_btn.config(state='normal' if idx > 0 else 'disabled')
            next_btn.config(text='Finish' if idx == len(steps) - 1 else 'Next')

        def close_dialog() -> None:
            if persist_state:
                if show_again_var.get():
                    try:
                        state_path.write_text("seen\n", encoding='utf-8')
                    except Exception as exc:
                        logger.warning(f"Could not persist onboarding state: {exc}")
                else:
                    try:
                        if state_path.exists():
                            state_path.unlink()
                        state_path.write_text("disabled\n", encoding='utf-8')
                    except Exception as exc:
                        logger.warning(f"Could not persist onboarding preference: {exc}")
            dialog.destroy()

        def next_step() -> None:
            if index_var.get() >= len(steps) - 1:
                close_dialog()
                return
            index_var.set(index_var.get() + 1)
            render_step()

        def prev_step() -> None:
            if index_var.get() > 0:
                index_var.set(index_var.get() - 1)
                render_step()

        button_frame = ttk.Frame(footer_frame)
        button_frame.pack(side='right')

        back_btn = ttk.Button(button_frame, text="Back", command=prev_step, width=10)
        back_btn.pack(side='left', padx=(0, 8))
        next_btn = ttk.Button(button_frame, text="Next", command=next_step, width=10)
        next_btn.pack(side='left')

        render_step()
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.bind("<Destroy>", lambda _e: setattr(self, '_onboarding_dialog', None))
