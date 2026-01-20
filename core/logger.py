"""
Centralized Logging System for Trader Ledger

Creates log files in logs/ folder:
- trader_ledger.log (main log, rotates daily)
- Separate files for different modules if needed

Log Levels:
- DEBUG: Detailed information for debugging
- INFO: General informational messages
- WARNING: Warning messages
- ERROR: Error messages
- CRITICAL: Critical errors
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(name: str = 'trader_ledger') -> logging.Logger:
    """
    Set up and return a logger instance.
    
    Args:
        name: Logger name (default: 'trader_ledger')
    
    Returns:
        Configured logger instance
    """
    
    # Create logs directory if it doesn't exist
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if logger already exists
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # File handler with rotation (max 5MB, keep 5 backups)
    log_file = log_dir / 'trader_ledger.log'
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Format: [2026-01-20 14:30:45] [INFO] [ui.add_trade_tab] Trade saved: BUY 10 TCS
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    
    return logger


def get_logger(module_name: str) -> logging.Logger:
    """
    Get a logger for a specific module.
    
    Args:
        module_name: Name of the module (e.g., 'ui.add_trade_tab')
    
    Returns:
        Logger instance
    """
    return logging.getLogger(f'trader_ledger.{module_name}')


# Initialize main logger at import time
main_logger = setup_logger()
