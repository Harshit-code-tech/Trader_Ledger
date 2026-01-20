"""
Trader Ledger Application
Entry point for the UI

Phase 1: Add Trade tab only
Phase 2: View Records (coming soon)
Phase 3: Reports (coming soon)
"""

import tkinter as tk
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
        app = TraderLedgerApp(root)
    
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
