"""
Configuration file for Trader Ledger application.

Centralized settings for database, UI, and application behavior.
"""

from pathlib import Path

# Application info
APP_NAME = "Trader Ledger - Baba's Trading App"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Built for Baba"

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = DATA_DIR / "exports"

# Database
DB_PATH = DATA_DIR / "trades.db"
DB_BACKUP_DIR = DATA_DIR / "backups"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)
DB_BACKUP_DIR.mkdir(exist_ok=True)

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
