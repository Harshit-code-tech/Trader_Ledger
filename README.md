# Trader Ledger 📊

A reliable, offline-first stock trade recording and accounting system with accurate FIFO (First-In-First-Out) profit/loss calculation for personal trading portfolio management.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.4.4-brightgreen.svg)](docs/COMPREHENSIVE_DOCUMENTATION.md)

## 🎯 Overview

Trader Ledger is a desktop application that helps individual retail traders maintain accurate records of their stock trades and automatically calculates profit/loss using FIFO accounting principles. No more error-prone spreadsheets or manual calculations!

### Key Features

- ✅ **Accurate FIFO Calculations** - Automatically matches sell orders with buy orders using First-In-First-Out logic
- ✅ **Trade Management** - Record, edit, and delete BUY/SELL transactions with validation
- ✅ **Comprehensive Reports** - View P/L summaries by Day/Week/Month/Year with running totals
- 🆕 **Equity-wise Filtering (v1.1)** - Analyze P/L for individual stocks
- 🆕 **Date Range Filtering (v1.1)** - View performance for specific time periods
- 🆕 **Open Positions Tracking (v1.1)** - See stocks you're still holding with average prices and holding days
- 🆕 **Restore Deleted Trades (v1.2)** - Soft-deleted trades can be restored from View Records
- 🆕 **Onboarding Walkthrough (v1.2)** - Reopen the guided walkthrough anytime from the top-right button
- 🆕 **Stock Symbol Suggestions (v1.2)** - Type-ahead suggestions in the Add Trade tab
- 🆕 **Auto Brokerage + MTF Interest (v1.2)** - Auto brokerage where configured, manual override where needed, and post-FIFO MTF interest support
- 🆕 **Audit CSV Export (v1.2)** - Match-level export with allocation remainder tracing and timestamp auditability
- ✅ **CSV Import/Export** - Bulk import trades and export reports in CSV or Excel format
- ✅ **Database Backup/Restore** - Protect your trade history with automated backups
- ✅ **Offline First** - Works completely offline with all data stored locally
- ✅ **Clean UI** - User-friendly Tkinter interface with calendar date picker and data validation

## 🆕 What's New in v1.4.3

Version 1.4.3 brings multi-profile filtering, native Intraday (MIS) short-selling support, blazing fast lazy-loading, and a seamless background updater.

- **Multi-Profile Selection**: Select multiple profiles at once in Reports and Trade Views to get a combined dashboard of their trades.
- **Intraday Short-Selling**: The FIFO engine now elegantly handles Intraday `BUY` and `SELL` matching natively, allowing you to short-sell (Sell first, Buy later) without triggering Oversell errors as long as trades occur on the same day.
- **Blazing Fast Startup**: Heavy data grids and report logic are now lazy-loaded in the background. The app opens instantly.
- **Seamless Background Updates**: `updater.py` automatically checks GitHub for updates and silently installs them in the background using Inno Setup's silent flags, completely invisible to the user!
- **Integrated Tracing (v1.3)**: Added optional `blackbox_recorder` tracing and saved trace reports to `logs/` for easier debugging and auditability.

👉 **[Read the Quick Start](QUICKSTART.md)** for day-to-day use  
👉 **[Full Documentation](docs/COMPREHENSIVE_DOCUMENTATION.md)** for technical details

## 📸 Screenshots

The application includes three main tabs:
- **Add Trade** - Record new trades with validation
- **View Records** - Browse, filter, edit, import/export trades
- **Reports** - Analyze profit/loss across different timeframes with filters, holdings, and trade value summaries

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher ([Download](https://www.python.org/downloads/))
- Windows OS (Linux/Mac support with minor modifications)

### Installation

1. **Clone or download this repository**
   ```bash
   git clone https://github.com/Harshit-code-tech/Trader_Ledger.git
   cd Trader_Ledger
   ```

2. **Run the setup script** (ONE TIME ONLY)
   ```bash
   setup.bat
   ```
   This will:
   - Create a virtual environment
   - Install all dependencies
   - Initialize the database

3. **Launch the application**
   ```bash
   run.bat
   ```

That's it! The Trader Ledger application window will open.

## 📖 Usage

### Adding Trades

1. Navigate to the **Add Trade** tab
2. Select date using the calendar picker
3. Enter stock symbol (e.g., RELIANCE, TCS)
4. Choose transaction type (BUY/SELL)
5. Enter quantity, price, and brokerage
6. Optionally add notes
7. Click **Add Trade**

### Importing from CSV

1. Go to **View Records** tab
2. Click **📁 Import CSV**
3. Select your CSV file with format:
   ```csv
   Date,Stock,Type,Qty,Price,Brokerage,BrokerageOverride,MtfAmount,TradeTS,Notes,Type1,Type2,Strike,Expiry
   22-01-2026,TCS,BUY,10,350.50,10.00,,0,2026-01-22 09:30:00,Initial purchase,delivery,,,
   23-01-2026,TCS,SELL,5,355.00,,12.00,0,2026-01-23 14:15:00,Partial exit,delivery,,,
   ```

A sample template is available at `data/sample_import.csv`

### Viewing Reports

1. Navigate to the **Reports** tab
2. Select timeframe filter (Daily/Weekly/Monthly/Yearly)
3. Review profit/loss summaries with running totals
4. Click **🖨️ Print** to generate an HTML report
5. Click **🔄 Recalculate** to refresh calculations

### Managing Data

- **Export CSV** - Export filtered trades to CSV
- **Export Excel** - Export to Excel format
- **Backup DB** - Create a timestamped backup of your database
- **Restore DB** - Restore from a previous backup
- **Restore Trade** - Restore a deleted trade back to active status

## 📁 Project Structure

```
Trader_Ledger/
├── app.py                 # Application entry point
├── config.py              # Configuration and path management
├── requirements.txt       # Python dependencies
├── setup.bat             # One-time setup script
├── run.bat               # Application launcher
├── core/                 # Core business logic
│   ├── db_init.py        # Database initialization
│   ├── fifo_matcher.py   # FIFO matching algorithm
│   ├── pnl_calculator.py # Profit/loss calculations
│   ├── pnl_aggregator.py # Report aggregations
│   ├── trade_engine.py   # Trade CRUD operations
│   └── logger.py         # Logging configuration
├── ui/                   # User interface
│   ├── main_window.py    # Main application window
│   ├── add_trade_tab.py  # Add trade interface
│   ├── view_records_tab.py # View/edit trades
│   └── reports_tab.py    # P/L reports
├── data/                 # Data directory
│   ├── trades.db         # SQLite database
│   ├── backups/          # Database backups
│   ├── exports/          # Exported files
│   └── sample_import.csv # CSV import template
├── logs/                 # Application logs
│   └── trader_ledger.log
└── docs/                 # Documentation
```

## 🛠️ Technical Details

### Technology Stack

- **Language:** Python 3.10+
- **GUI Framework:** Tkinter (standard library)
- **Database:** SQLite3
- **Dependencies:**
  - `tkcalendar` - Calendar date picker widget
  - `pyinstaller` - Executable builder (optional)
  - `pillow` - Image processing (optional, for icon)

### FIFO Algorithm

The application uses a rigorous FIFO (First-In-First-Out) algorithm:
1. All BUY transactions are stored chronologically
2. When a SELL occurs, it matches against the oldest unexhausted BUY
3. Partial quantity matching is supported
4. Profit/loss = (Sell Price - Buy Price) × Quantity - Total Brokerage
5. Independent FIFO queues per stock symbol

### Data Storage

- **Database:** SQLite database at `data/trades.db`
- **Schema:** Single `trade_events` table with trade date/time, brokerage auto/override, MTF amount, and soft-delete support
- **Backups:** Automatic timestamped backups before imports/restores
- **Logs:** Rotating logs at `logs/trader_ledger.log`

## 🔧 Building Executable

To create a standalone Windows executable:

1. Run the build script:
   ```bash
   build_installer.bat
   ```

2. The executable will be created in `dist/TraderLedger/`

3. To create an installer, use Inno Setup with `installer.iss`

See [BUILD_INSTRUCTIONS.md](docs/BUILD_INSTRUCTIONS.md) for detailed instructions.

## 📚 Documentation

- [QUICKSTART.md](QUICKSTART.md) - Quick start guide for end users
- [COMPREHENSIVE_DOCUMENTATION.md](docs/COMPREHENSIVE_DOCUMENTATION.md) - Full project documentation
- [BUILD_INSTRUCTIONS.md](docs/BUILD_INSTRUCTIONS.md) - Build and deployment guide
- [DATA_LOCATION_GUIDE.md](docs/DATA_LOCATION_GUIDE.md) - Data storage locations
- [UPDATE_GUIDE.md](docs/UPDATE_GUIDE.md) - How to update the application

## 🐛 Troubleshooting

### Application won't start
- Ensure Python 3.10+ is installed
- Run `setup.bat` to reinstall dependencies
- Check `logs/trader_ledger.log` for errors

### "Virtual environment not found"
- Run `setup.bat` first before `run.bat`

### Import CSV fails
- Verify CSV format matches the template
- Check that dates are in DD-MM-YYYY format
- Ensure no invalid characters in stock symbols

### Validation Error in Reports
- You have an oversell (selling more than bought)
- Review trades in View Records tab
- Fix the data and click **Recalculate**

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Harshit**
- GitHub: [@Harshit-code-tech](https://github.com/Harshit-code-tech)

## 🙏 Acknowledgments

- Thanks to the Python community for excellent libraries
- Inspired by the need for accurate personal trade accounting
- Built for traders who value precision and simplicity

## 📮 Support

For issues, questions, or suggestions:
- Open an issue on [GitHub Issues](https://github.com/Harshit-code-tech/Trader_Ledger/issues)
- Check existing documentation in the `docs/` folder
- Review log files at `logs/trader_ledger.log`

---

**Note:** This is an offline accounting tool for post-trade record-keeping. It does NOT provide live trading, market data, broker integration, or investment advice.
