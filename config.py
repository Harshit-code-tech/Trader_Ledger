"""
Configuration file for Trader Ledger application.

Centralized settings for database, UI, and application behavior.
"""

import os
import sys
from pathlib import Path

# Application info
APP_NAME = "Trader Ledger - Baba's Trading App"
APP_VERSION = "1.6.1"
APP_AUTHOR = "Built for Baba"

def get_data_directory():
    """
    Get the appropriate data directory based on environment.
    
    - For packaged app (frozen): Uses AppData/Roaming/TraderLedger
    - For development: Uses local data/ folder
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        appdata = os.environ.get('APPDATA')
        if appdata:
            data_dir = Path(appdata) / "TraderLedger"
        else:
            # Fallback to home directory if APPDATA not available
            data_dir = Path.home() / ".traderleger"
    else:
        # Running in development
        data_dir = Path(__file__).parent / "data"
    
    return data_dir

# Paths
BASE_DIR = Path(__file__).parent if not getattr(sys, 'frozen', False) else Path(sys.executable).parent
DATA_DIR = get_data_directory()
LOGS_DIR = DATA_DIR / "logs"
EXPORTS_DIR = DATA_DIR / "exports"
ONBOARDING_STATE_FILE = DATA_DIR / "onboarding_seen.txt"
PROFILE_STATE_FILE = DATA_DIR / "profile_state.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

# Database
DB_PATH = DATA_DIR / "trades.db"
DB_BACKUP_DIR = DATA_DIR / "backups"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
DB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# UI Settings
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 800
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 600

# Fonts
HEADER_FONT = ('Consolas', 16, 'bold')
SUBHEADER_FONT = ('Consolas', 12, 'bold')
NORMAL_FONT = ('Consolas', 10)
SMALL_FONT = ('Arial', 9)

# Colors
COLOR_PROFIT = '#27ae60'
COLOR_LOSS = '#e74c3c'
COLOR_NEUTRAL = '#34495e'
COLOR_WARNING = '#e74c3c'
COLOR_SUCCESS = '#27ae60'

# Logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = LOGS_DIR / "trader_ledger.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

# CSV Import/Export
CSV_DATE_FORMAT = "DD-MM-YYYY"
CSV_ENCODING = "utf-8"
SAMPLE_CSV_PATH = DATA_DIR / "sample_import.csv"

# Calendar picker
try:
    from tkcalendar import DateEntry  # type: ignore
    CALENDAR_AVAILABLE = True
    _ = DateEntry  # Mark as used
except ImportError:
    CALENDAR_AVAILABLE = False

# Feature flags
ENABLE_DEBUG_MODE = False
ENABLE_AUTO_BACKUP = True
AUTO_BACKUP_ON_STARTUP = False

# Current profile state (set at runtime by UI)
# PRIMARY_PROFILE_ID: Integer profile id for adding trades. None if multiple/combined.
PRIMARY_PROFILE_ID: int | None = None
# ACTIVE_PROFILE_IDS: List of profile IDs to display. Empty list [] means Combined Family View (all profiles).
ACTIVE_PROFILE_IDS: list[int] = []
CURRENT_PROFILE_NAME: str | None = None

