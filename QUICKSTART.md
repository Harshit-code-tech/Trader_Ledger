# Trader Ledger v1.4.6 - Quick Start Guide

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
- **📁 Import CSV** - Import trades from CSV file
- **💾 Export CSV** - Export filtered trades
- **📄 Export Excel** - Export to Excel format
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
- Expand a trade unit to view audit details

### Onboarding
- First run shows a walkthrough automatically
- Use the top-right **Walkthrough** button to open it again anytime

## CSV Import Format

To import trades, create a CSV file with these columns:

```
Date,Stock,Type,Qty,Price,Brokerage,BrokerageOverride,MtfAmount,TradeTS,Notes,Type1,Type2,Strike,Expiry
22-01-2026,TCS,BUY,10,350.50,10.00,,0,2026-01-22 09:30:00,Optional note,delivery,,,
```

**Column Details:**
- **Date**: DD-MM-YYYY format (e.g., 22-01-2026)
- **Stock**: Stock symbol (e.g., TCS, RELIANCE)
- **Type**: BUY or SELL
- **Qty**: Number of shares (positive integer)
- **Price**: Price per share in rupees (e.g., 350.50)
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

**Version 1.4.6** - Ready for daily use
