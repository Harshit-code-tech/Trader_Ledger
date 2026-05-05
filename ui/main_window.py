"""
Main Window - Trader Ledger Application

Creates the main window with notebook tabs.
Phase 1: Only Add Trade tab is functional.
"""

import tkinter as tk
from tkinter import ttk
from ui.add_trade_tab import AddTradeTab
from ui.view_records_tab import ViewRecordsTab
from ui.reports_tab import ReportsTab
from ui.trade_view_tab import TradeViewTab
from core.logger import get_logger

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
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Bind tab selection event
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Create tabs
        self.create_tabs()
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
