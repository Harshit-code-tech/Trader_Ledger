# Trader Ledger v1.6.0 - Quick Start Guide

## For First-Time Use

### Step 1: Setup (ONE TIME ONLY)
Double-click: **`setup.bat`**

This will:
- Create virtual environment
- Install all dependencies
- Initialize database

**Wait for "Setup Complete!" message**

### Step 2: Run Application
Double-click: **`run.bat`**

The application window will open.

If this is your first launch, a walkthrough dialog opens automatically. You can reopen it later from the **Walkthrough** button at the top-right of the main window.

## Daily Usage

Just double-click **`run.bat`** to start the application.

## Features Available

### Add Trade Tab
- Add new BUY/SELL trades
- Calendar date picker
- Auto-validates inputs

### View Records Tab
- Filter trades by date/stock/type
- Edit existing trades
- Delete trades
- Restore deleted trades
- **📁 Import CSV** - Import trades from CSV file. If no `Profile` column is present in your CSV, you will be prompted to pick a profile to import into.
- **💾 Export CSV** - Export filtered trades. In Combined view, you can pick which profiles to export. Files are saved in profile-specific subfolders.
- **📄 Export Excel** - Export to Excel format (same profile-aware folder structure).
- **💾 Backup DB** - Backup database
- **📥 Restore DB** - Restore from backup

### Reports Tab
- View profit/loss summary
- Daily/Weekly/Monthly/Yearly breakdowns
- Running accumulated totals
- Open positions with holding days
- Total trade value and average day trade value
- **🖨️ Print** - Generate printable HTML report
- **🔄 Recalculate** - Refresh P/L calculations

### Trade View Tab
- Group by lifecycle or sell transaction
- See gross P/L, MTF interest, and net P/L
- Filter to show **Open Only** positions
- Sort by Date, Profit/Loss, Holding Days, or Status
- Expand a trade unit to view audit details

### Onboarding
- First run shows a walkthrough automatically
- Use the top-right **Walkthrough** button to open it again anytime

## CSV Import Format

To import trades, create a CSV file with these columns:

```csv
Date,Stock,Type,Qty,Price,Profile,Type1
20-01-2026,TCS,BUY,10,350.50,Baba,delivery
21-01-2026,RELIANCE,BUY,5,280.00,Didi,intraday
```

**Column Details:**
- **Date**: DD-MM-YYYY format (e.g., 22-01-2026)
- **Stock**: Stock symbol (e.g., TCS, RELIANCE)
- **Type**: BUY or SELL
- **Qty**: Number of shares (positive integer)
- **Price**: Price per share in rupees (e.g., 350.50)
- **Profile**: Profile name to auto-assign trades to (optional. If omitted, you will be asked to choose a profile during import).
- **Brokerage**: Brokerage charges in rupees (optional, use 0 if none)
- **BrokerageOverride**: Manual brokerage override in rupees when auto brokerage is not configured
- **MtfAmount**: Required for MTF BUY trades
- **TradeTS**: Optional IST timestamp in `YYYY-MM-DD HH:MM:SS` format
- **Notes**: Any notes about the trade (optional)

A blank template is available at: `data/sample_import.csv`

## Troubleshooting

### "Python not found"
Install Python 3.10 or higher from [python.org](https://python.org)

### "Virtual environment not found"
Run `setup.bat` first

### Application won't start
1. Close any running instances
2. Check `logs/trader_ledger.log` for errors
3. Try running `setup.bat` again

## Data Location

- **Database**: `data/trades.db`
- **Backups**: `data/backups/`
- **Exports**: `data/exports/`
- **Logs**: `logs/trader_ledger.log`

## Validation Alerts

If you see a **⚠️ VALIDATION ERROR** banner in Reports:
- You have an oversell (selling more than you bought)
- Check your trades for errors
- Fix the trade data
- Click **Recalculate**

Reports and exports are disabled until validation passes.

## Need Help?

Check the log file: `logs/trader_ledger.log`

---

**Version 1.6.0** - Ready for daily use
