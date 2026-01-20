from fifo_matcher import fetch_active_trades, match_fifo, TradeTuple
from pnl_calculator import calculate_match_pnl, TradeDict, PnlResult
from pnl_aggregator import aggregate_pnl_by_date, aggregate_pnl_by_month

DB_PATH = 'data/trades.db'

def build_trades_by_id(trades: list[TradeTuple]) -> dict[int, TradeDict]:
    return {t[0]: TradeDict(
        id=t[0],
        trade_date=t[1],
        trade_type=t[2],
        quantity=t[3],
        price=t[4],
        brokerage=t[5],
        notes=t[6],
        is_active=t[7]
    ) for t in trades}

def main() -> None:
    # 1. Fetch trades from DB
    trades: list[TradeTuple] = fetch_active_trades()
    trades_by_id: dict[int, TradeDict] = build_trades_by_id(trades)

    # 2. Run FIFO matcher
    matches = match_fifo(trades)
    
    # Guard: matches can be None if collect_matches=False
    if matches is None:
        print("No matches generated.")
        return

    # 3. Run Phase-3 PnL calculator
    match_results: list[PnlResult] = calculate_match_pnl(matches, trades_by_id)

    # Defensive: If no SELLs, inform user and exit
    if not match_results:
        print("No realized P/L yet (no SELL trades).")
        return

    # 4. Run Phase-4 aggregators
    daily_pnl: dict[str, int] = aggregate_pnl_by_date(match_results, trades_by_id)
    monthly_pnl: dict[str, int] = aggregate_pnl_by_month(daily_pnl)
    total_pnl: int = sum(m['realized_pnl'] for m in match_results)

    # 5. Print results
    print("===== DAILY P/L =====")
    for d in sorted(daily_pnl):
        print(f"{d} : {daily_pnl[d]:+}")
    print("\n===== MONTHLY P/L =====")
    for m in sorted(monthly_pnl):
        print(f"{m} : {monthly_pnl[m]:+}")
    print("\n===== TOTAL P/L =====")
    print(f"{total_pnl:+}")

if __name__ == '__main__':
    main()
