"""
Database Initialization Module
Automatically creates database schema on first run
"""

import sqlite3
from pathlib import Path
from core.logger import setup_logger
import config

logger = setup_logger()


def init_database(db_path: str | None = None) -> bool:
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
                brokerage_auto NUMERIC NOT NULL DEFAULT 0 CHECK (brokerage_auto >= 0),
                brokerage_override NUMERIC CHECK (brokerage_override >= 0),
                mtf_amount NUMERIC NOT NULL DEFAULT 0 CHECK (mtf_amount >= 0),
                trade_ts TEXT,
                notes TEXT,
                type1 TEXT CHECK (type1 IN ("intraday", "delivery", "mtf", "futures", "options") OR type1 IS NULL),
                type2 TEXT CHECK (type2 IN ("CE", "PE") OR type2 IS NULL),
                strike REAL CHECK (strike > 0 OR strike IS NULL),
                expiry DATE,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
            )
        ''')

        # Create profiles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name TEXT NOT NULL UNIQUE,
                mobile TEXT,
                email TEXT,
                notes TEXT,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
            )
        ''')

        # Ensure default profile 'Baba' exists for backward compatibility
        cursor.execute("SELECT id FROM profiles WHERE profile_name = ?", ("Baba",))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO profiles (profile_name, is_active) VALUES (?, 1)", ("Baba",))
            logger.info("Created default profile 'Baba'")
            default_profile_id = cursor.lastrowid
        else:
            default_profile_id = row[0]

        # Add profile_id column (migrate existing trade_events rows into new table with FK)
        cursor.execute("PRAGMA table_info(trade_events)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        if "profile_id" not in existing_columns:
            # Recreate table with profile_id and FK
            cursor.execute('PRAGMA foreign_keys = OFF')
            # Create a new table with the same schema plus profile_id
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS trade_events_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date DATE NOT NULL,
                    equity TEXT NOT NULL,
                    trade_type TEXT NOT NULL CHECK (trade_type IN ("BUY", "SELL")),
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    price NUMERIC NOT NULL CHECK (price > 0),
                    brokerage NUMERIC NOT NULL DEFAULT 0 CHECK (brokerage >= 0),
                    brokerage_auto NUMERIC NOT NULL DEFAULT 0 CHECK (brokerage_auto >= 0),
                    brokerage_override NUMERIC CHECK (brokerage_override >= 0),
                    mtf_amount NUMERIC NOT NULL DEFAULT 0 CHECK (mtf_amount >= 0),
                    trade_ts TEXT,
                    notes TEXT,
                    type1 TEXT CHECK (type1 IN ("intraday", "delivery", "mtf", "futures", "options") OR type1 IS NULL),
                    type2 TEXT CHECK (type2 IN ("CE", "PE") OR type2 IS NULL),
                    strike REAL CHECK (strike > 0 OR strike IS NULL),
                    expiry DATE,
                    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                    profile_id INTEGER NOT NULL,
                    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT
                )
            ''')

            # Copy existing rows into new table, assigning default profile_id
            cursor.execute(f"SELECT id, trade_date, equity, trade_type, quantity, price, brokerage, brokerage_auto, brokerage_override, mtf_amount, trade_ts, notes, type1, type2, strike, expiry, is_active FROM trade_events")
            rows = cursor.fetchall()
            for r in rows:
                cursor.execute('''
                    INSERT INTO trade_events_new (
                        id, trade_date, equity, trade_type, quantity, price, brokerage,
                        brokerage_auto, brokerage_override, mtf_amount, trade_ts, notes,
                        type1, type2, strike, expiry, is_active, profile_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11],
                    r[12], r[13], r[14], r[15], r[16], default_profile_id
                ))

            # Drop old table and rename new
            cursor.execute('DROP TABLE trade_events')
            cursor.execute('ALTER TABLE trade_events_new RENAME TO trade_events')
            cursor.execute('PRAGMA foreign_keys = ON')
            logger.info("Migrated trade_events to include profile_id and backfilled existing rows to 'Baba'")

            # Refresh existing_columns set
            cursor.execute("PRAGMA table_info(trade_events)")
            existing_columns = {row[1] for row in cursor.fetchall()}

        # Ensure new columns exist for older databases
        cursor.execute("PRAGMA table_info(trade_events)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        columns_to_add = {
            "type1": "type1 TEXT CHECK (type1 IN (\"intraday\", \"delivery\", \"mtf\", \"futures\", \"options\") OR type1 IS NULL)",
            "type2": "type2 TEXT CHECK (type2 IN (\"CE\", \"PE\") OR type2 IS NULL)",
            "strike": "strike REAL CHECK (strike > 0 OR strike IS NULL)",
            "expiry": "expiry DATE",
            "brokerage_auto": "brokerage_auto NUMERIC NOT NULL DEFAULT 0 CHECK (brokerage_auto >= 0)",
            "brokerage_override": "brokerage_override NUMERIC CHECK (brokerage_override >= 0)",
            "mtf_amount": "mtf_amount NUMERIC NOT NULL DEFAULT 0 CHECK (mtf_amount >= 0)",
            "trade_ts": "trade_ts TEXT"
        }
        for column_name, column_def in columns_to_add.items():
            if column_name not in existing_columns:
                cursor.execute(f"ALTER TABLE trade_events ADD COLUMN {column_def}")
                logger.info(f"Added column '{column_name}' to trade_events")
                existing_columns.add(column_name)

        if "trade_ts" in existing_columns:
            cursor.execute(
                "UPDATE trade_events SET trade_ts = trade_date || ' 09:15:00' "
                "WHERE trade_ts IS NULL OR trade_ts = ''"
            )
        
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


def backfill_type1_delivery(db_path: str | None = None) -> int:
    """
    Backfill NULL type1 values to 'delivery'.

    Returns:
        Number of rows updated.
    """
    if db_path is None:
        db_path = str(config.DB_PATH)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE trade_events SET type1 = 'delivery' WHERE type1 IS NULL")
    conn.commit()
    updated = cursor.rowcount
    conn.close()
    return updated
