"""
Trader Ledger Application
Entry point for the UI

Phase 1: Add Trade tab only
Phase 2: View Records (coming soon)
Phase 3: Reports (coming soon)
"""

import tkinter as tk
import sys
from pathlib import Path

# Ensure data directory exists in user's AppData for installed .exe
if getattr(sys, 'frozen', False):
    # Running as compiled .exe
    import os
    APPDATA = Path(os.environ.get('APPDATA', '.'))
    APP_DIR = APPDATA / "TraderLedger"
    APP_DIR.mkdir(exist_ok=True)
    (APP_DIR / "data").mkdir(exist_ok=True)
    (APP_DIR / "logs").mkdir(exist_ok=True)
    (APP_DIR / "data" / "exports").mkdir(exist_ok=True)
    (APP_DIR / "data" / "backups").mkdir(exist_ok=True)
    
    # Change working directory to AppData location
    os.chdir(APP_DIR)
    
    # Create sample CSV if it doesn't exist
    sample_csv = APP_DIR / "data" / "sample_import.csv"
    if not sample_csv.exists():
        sample_csv.write_text("Date,Stock,Type,Qty,Price,Brokerage,Notes\n", encoding='utf-8')

from ui.main_window import TraderLedgerApp
from core.logger import setup_logger

# Initialize logger
logger = setup_logger()


def main():
    """Launch the Trader Ledger application."""
    logger.info("="*60)
    logger.info("Starting Trader Ledger Application")
    logger.info("="*60)
    
    try:
        root = tk.Tk()
        _ = TraderLedgerApp(root)  # Keep reference to prevent garbage collection
    
        # Center window on screen
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')
        
        logger.info("Application window initialized successfully")
        root.mainloop()
        
        logger.info("Application closed normally")
        logger.info("="*60)
    
    except Exception as e:
        logger.critical(f"Application crashed: {str(e)}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
