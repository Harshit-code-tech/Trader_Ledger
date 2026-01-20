"""
Main Window - Trader Ledger Application

Creates the main window with notebook tabs.
Phase 1: Only Add Trade tab is functional.
"""

import tkinter as tk
from tkinter import ttk
from ui.add_trade_tab import AddTradeTab
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
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tabs
        self.create_tabs()
        logger.info("Main window initialized successfully")
        
        # Status bar at bottom
        self.status_bar = tk.Label(
            self.root,
            text="Ready",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=('Arial', 9)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_tabs(self) -> None:
        """Create all tabs. Phase 1: Only Add Trade is functional."""
        
        # Tab 1: Add Trade (Phase 1 - functional)
        add_trade_frame = ttk.Frame(self.notebook)
        self.notebook.add(add_trade_frame, text="  Add Trade  ")
        self.add_trade_tab = AddTradeTab(add_trade_frame, self.update_status)
        
        # Tab 2: View Records (Phase 2 - placeholder)
        view_records_frame = ttk.Frame(self.notebook)
        self.notebook.add(view_records_frame, text="  View Records  ")
        placeholder2 = ttk.Label(
            view_records_frame,
            text="View Records\n\n(Coming in Phase 2)",
            font=('Arial', 14),
            justify='center'
        )
        placeholder2.pack(expand=True)
        
        # Tab 3: Reports (Phase 3 - placeholder)
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text="  Reports  ")
        placeholder3 = ttk.Label(
            reports_frame,
            text="Profit/Loss Reports\n\n(Coming in Phase 3)",
            font=('Arial', 14),
            justify='center'
        )
        placeholder3.pack(expand=True)
    
    def update_status(self, message: str) -> None:
        """Update status bar message."""
        logger.debug(f"Status update: {message}")
        self.status_bar.config(text=message)
        self.root.update_idletasks()
