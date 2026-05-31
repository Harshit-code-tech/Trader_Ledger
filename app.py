"""
Trader Ledger Application
Entry point for the UI
"""

import tkinter as tk
import sys
from datetime import datetime
import config  # Import config first to set up directories

from ui.main_window import TraderLedgerApp
from core.logger import setup_logger
from core.db_init import init_database

# Initialize logger
logger = setup_logger()

# Create sample CSV if it doesn't exist (for both dev and production)
if not config.SAMPLE_CSV_PATH.exists():
    config.SAMPLE_CSV_PATH.write_text(
        "Date,Stock,Type,Qty,Price,Brokerage,Notes,Type1,Type2,Strike,Expiry\n"
        "20-01-2026,RELIANCE,BUY,10,250.50,10.00,First trade,delivery,,,\n",
        encoding='utf-8'
    )
    logger.info(f"Created sample CSV at: {config.SAMPLE_CSV_PATH}")


def main():
    """Launch the Trader Ledger application."""
    recorder_state = _start_blackbox_recorder()
    try:
        logger.info("="*60)
        logger.info("Starting Trader Ledger Application")
        logger.info(f"Data directory: {config.DATA_DIR}")
        logger.info(f"Database path: {config.DB_PATH}")
        logger.info("="*60)

        # Initialize database schema if needed
        logger.info("Checking database...")
        if not init_database():
            logger.error("Failed to initialize database. Please check logs.")
            import tkinter.messagebox as mb
            mb.showerror(
                "Database Error",
                "Failed to initialize database.\nPlease check logs for details."
            )
            return
        logger.info("Database ready")

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
    finally:
        _stop_blackbox_recorder(recorder_state)


def _start_blackbox_recorder():
    try:
        import blackbox_recorder as blackbox
    except Exception:
        return None

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = config.LOGS_DIR / f"blackbox_report_{timestamp}.txt"
        json_path = config.LOGS_DIR / f"blackbox_trace_{timestamp}.json"
        blackbox.configure(
            include=["__main__", "config", "core", "ui"],
            exclude=["blackbox_recorder"],
            persistence_path=str(json_path)
        )
        blackbox.start()
        logger.info(f"Blackbox recorder started; trace path: {json_path}")
        return blackbox, report_path
    except Exception as exc:
        logger.warning(f"Blackbox recorder failed to start: {exc}", exc_info=True)
        return None


def _stop_blackbox_recorder(state) -> None:
    if not state:
        return

    blackbox, report_path = state
    try:
        blackbox.stop()
        blackbox.save_report(str(report_path))
        logger.info(f"Blackbox report saved: {report_path}")
    except Exception as exc:
        logger.warning(f"Blackbox recorder failed to save report: {exc}", exc_info=True)


if __name__ == '__main__':
    main()
