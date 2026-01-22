"""
Database Initialization Module
Automatically creates database schema on first run
"""

import sqlite3
from pathlib import Path
from core.logger import setup_logger
import config

logger = setup_logger()


def init_database(db_path: str = None) -> bool:
    """Initialize database. If db_path is None, uses config.DB_PATH."""
    if db_path is None:
        db_path = str(config.DB_PATH)
    """
    Initialize database with required schema.
    Creates trade_events table if it doesn't exist.
    
    Args:
        db_path: Path to the database file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Connect and create schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create trade_events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date DATE NOT NULL,
                equity TEXT NOT NULL,
                trade_type TEXT NOT NULL CHECK (trade_type IN ("BUY", "SELL")),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                price NUMERIC NOT NULL CHECK (price > 0),
                brokerage NUMERIC NOT NULL DEFAULT 0 CHECK (brokerage >= 0),
                notes TEXT,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
            )
        ''')
        
        conn.commit()
        
        # Check if table was created successfully
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_events'")
        table_exists = cursor.fetchone() is not None
        
        conn.close()
        
        if table_exists:
            logger.info(f"Database initialized successfully: {db_path}")
            return True
        else:
            logger.error("Failed to create trade_events table")
            return False
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


def check_database_exists(db_path: str = 'data/trades.db') -> bool:
    """
    Check if database exists and has the required schema.
    
    Args:
        db_path: Path to the database file
        
    Returns:
        bool: True if database and schema exist, False otherwise
    """
    try:
        db_file = Path(db_path)
        if not db_file.exists():
            return False
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if trade_events table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_events'")
        table_exists = cursor.fetchone() is not None
        
        conn.close()
        return table_exists
        
    except Exception:
        return False
