from core.fifo_matcher import fetch_active_trades, match_fifo, TradeTuple, FifoMatchError
from core.pnl_calculator import calculate_match_pnl, TradeDict, PnlResult, PnlCalculationError
from core.pnl_aggregator import aggregate_pnl_by_date, aggregate_pnl_by_month
import sqlite3
import sys
import config

DB_PATH = str(config.DB_PATH)

def get_equities(trades_by_id: dict[int, TradeDict]) -> list[str]:
    """
    Extract unique equity symbols from trades, sorted alphabetically.
    Useful for UI dropdowns and report filters.
    
    Args:
        trades_by_id: Dictionary of trade ID to TradeDict
        
    Returns:
        Sorted list of unique equity symbols
    """
    return sorted({t['equity'] for t in trades_by_id.values()})

def build_trades_by_id(trades: list[TradeTuple]) -> dict[int, TradeDict]:
    return {t[0]: TradeDict(
        id=t[0],
        trade_date=t[1],
        equity=t[2],
        trade_type=t[3],
        type1=t[4] or "delivery",
        type2=t[5],
        strike=t[6],
        expiry=t[7],
        quantity=t[8],
        price=t[9],
        brokerage=t[10],
        notes=t[11],
        is_active=t[12]
    ) for t in trades}

def main() -> None:
    try:
        # 1. Fetch trades from DB
        try:
            trades: list[TradeTuple] = fetch_active_trades()
        except sqlite3.Error as e:
            print(f"\n❌ DATABASE ERROR")
            print(f"{'='*60}")
            print(f"Failed to connect or read from database: {DB_PATH}")
            print(f"Error: {e}")
            print(f"\n💡 Suggestions:")
            print(f"  1. Verify database file exists at {DB_PATH}")
            print(f"  2. Check database file permissions")
            print(f"  3. Run db_init.py to create the database")
            print(f"{'='*60}")
            sys.exit(1)
        
        if not trades:
            print("\n📊 No trades found in database.")
            print("Add some trades first before running the ledger.")
            return
        
        trades_by_id: dict[int, TradeDict] = build_trades_by_id(trades)

        # 2. Run FIFO matcher
        try:
            matches = match_fifo(trades)
        except FifoMatchError as e:
            print(f"\n❌ FIFO MATCHING ERROR")
            print(str(e))
            print(f"\nLedger processing stopped. Fix the issue and try again.")
            sys.exit(1)
        
        # Guard: matches can be None if collect_matches=False
        if matches is None:
            print("No matches generated.")
            return

        # 3. Run Phase-3 PnL calculator
        try:
            match_results: list[PnlResult] = calculate_match_pnl(matches, trades_by_id)
        except PnlCalculationError as e:
            print(f"\n❌ P/L CALCULATION ERROR")
            print(f"{'='*60}")
            print(str(e))
            print(f"{'='*60}")
            print(f"\n💡 This is likely a data integrity issue.")
            print(f"Verify all trade IDs in the database are valid.")
            sys.exit(1)

        # Defensive: If no SELLs, inform user and exit
        if not match_results:
            print("\n📊 No realized P/L yet (no SELL trades).")
            print("Add SELL trades to see profit/loss calculations.")
            return

        # 4. Run Phase-4 aggregators
        daily_pnl: dict[str, int] = aggregate_pnl_by_date(match_results, trades_by_id)
        monthly_pnl: dict[str, int] = aggregate_pnl_by_month(daily_pnl)
        total_pnl: int = sum(m['realized_pnl'] for m in match_results)

        # 5. Print results
        print("\n" + "="*60)
        print("✅ LEDGER SUCCESSFULLY PROCESSED")
        print("="*60)
        print("\n===== DAILY P/L =====")
        for d in sorted(daily_pnl):
            print(f"{d} : {daily_pnl[d]:+}")
        print("\n===== MONTHLY P/L =====")
        for m in sorted(monthly_pnl):
            print(f"{m} : {monthly_pnl[m]:+}")
        print("\n===== TOTAL P/L =====")
        print(f"{total_pnl:+}")
        print("="*60)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR")
        print(f"{'='*60}")
        print(f"An unexpected error occurred: {type(e).__name__}")
        print(f"Error message: {e}")
        print(f"{'='*60}")
        print(f"\n💡 Please report this error if it persists.")
        sys.exit(1)

if __name__ == '__main__':
    main()
