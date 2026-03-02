from collections import defaultdict
from typing import TypedDict


class PnlCalculationError(Exception):
    pass


class PnlResult(TypedDict):
    sell_id: int
    buy_id: int
    matched_quantity: int
    buy_cost: int
    sell_value: int
    buy_brokerage_alloc: int
    sell_brokerage_alloc: int
    realized_pnl: int


class TradeDict(TypedDict):
    id: int
    trade_date: str
    equity: str
    trade_type: str
    quantity: int
    price: int
    brokerage: int
    notes: str
    is_active: int


def aggregate_pnl_by_sell(match_results: list[PnlResult]) -> dict[int, int]:
    """
    Aggregates realized P/L per SELL trade.
    Input: list of match dicts (from Phase-3), each with 'sell_id' and 'realized_pnl'.
    Output: dict of sell_id -> total realized P/L for that SELL.
    """
    sell_totals: defaultdict[int, int] = defaultdict(int)
    for match in match_results:
        assert 'sell_id' in match and 'realized_pnl' in match, "Missing required fields in match record."
        sell_totals[match['sell_id']] += match['realized_pnl']
    return dict(sell_totals)

def aggregate_pnl_by_date(match_results: list[PnlResult], trades_by_id: dict[int, TradeDict]) -> dict[str, int]:
    """
    Aggregates realized P/L per SELL date.
    Input: match_results (from Phase-3), trades_by_id (to get SELL trade_date)
    Output: dict of trade_date -> total realized P/L for that date (from SELL trade)
    """
    date_totals: defaultdict[str, int] = defaultdict(int)
    for match in match_results:
        assert 'sell_id' in match and 'realized_pnl' in match, "Missing required fields in match record."
        sell_id: int = match['sell_id']
        if sell_id not in trades_by_id:
            raise PnlCalculationError(f"SELL trade_id {sell_id} not found for date aggregation")
        sell_trade: TradeDict = trades_by_id[sell_id]
        if 'trade_date' not in sell_trade:
            raise PnlCalculationError(f"SELL trade_id {sell_id} missing 'trade_date' field")
        sell_date: str = sell_trade['trade_date']
        date_totals[sell_date] += match['realized_pnl']
    return dict(date_totals)



def aggregate_pnl_by_week(date_totals: dict[str, int]) -> dict[str, int]:
    """
    Input: dict of 'YYYY-MM-DD' -> P/L
    Output: dict of 'YYYY-Www' -> total P/L for that week (ISO week number)
    """
    from datetime import datetime
    week_totals: defaultdict[str, int] = defaultdict(int)
    for date_str, pnl in date_totals.items():
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        # ISO week: year + week number
        iso_year, iso_week, _ = dt.isocalendar()
        week_key: str = f"{iso_year}-W{iso_week:02d}"
        week_totals[week_key] += pnl
    return dict(week_totals)


def aggregate_pnl_by_month(date_totals: dict[str, int]) -> dict[str, int]:
    """
    Input: dict of 'YYYY-MM-DD' -> P/L
    Output: dict of 'YYYY-MM' -> total P/L for that month
    """
    month_totals: defaultdict[str, int] = defaultdict(int)
    for date_str, pnl in date_totals.items():
        month_key: str = date_str[:7]  # 'YYYY-MM'
        month_totals[month_key] += pnl
    return dict(month_totals)


def aggregate_pnl_by_year(month_totals: dict[str, int]) -> dict[str, int]:
    """
    Input: dict of 'YYYY-MM' -> P/L
    Output: dict of 'YYYY' -> total P/L for that year
    """
    year_totals: defaultdict[str, int] = defaultdict(int)
    for month_str, pnl in month_totals.items():
        year_key: str = month_str[:4]  # 'YYYY'
        year_totals[year_key] += pnl
    return dict(year_totals)


def aggregate_pnl_by_equity(match_results: list[PnlResult], trades_by_id: dict[int, TradeDict]) -> dict[str, int]:
    """
    Aggregates realized P/L per equity (stock symbol).
    Input: match_results (from Phase-3), trades_by_id (to get equity from SELL trade)
    Output: dict of equity -> total realized P/L for that equity
    
    This enables the "Show me P/L for this stock only" feature.
    FIFO matching stays the same, only aggregation changes.
    """
    equity_totals: defaultdict[str, int] = defaultdict(int)
    for match in match_results:
        assert 'sell_id' in match and 'realized_pnl' in match, "Missing required fields in match record."
        sell_id: int = match['sell_id']
        if sell_id not in trades_by_id:
            raise PnlCalculationError(f"SELL trade_id {sell_id} not found for equity aggregation")
        sell_trade: TradeDict = trades_by_id[sell_id]
        if 'equity' not in sell_trade:
            raise PnlCalculationError(f"SELL trade_id {sell_id} missing 'equity' field")
        equity: str = sell_trade['equity']
        equity_totals[equity] += match['realized_pnl']
    return dict(equity_totals)


def filter_matches_by_date_range(
    match_results: list[PnlResult], 
    trades_by_id: dict[int, TradeDict],
    from_date: str | None = None,
    to_date: str | None = None
) -> list[PnlResult]:
    """
    Filters match results by SELL trade date range.
    
    Rules:
    - Filter by SELL trade_date (when P/L was realized)
    - FIFO matching respects global order (no re-matching)
    - Only includes P/L that was realized in the date range
    
    Edge cases:
    - Buy before range, sell inside range → ✔ include P/L
    - Buy inside range, sell after → ❌ not closed yet (exclude)
    
    Args:
        match_results: List of match results from FIFO
        trades_by_id: Dict of trade_id -> trade data
        from_date: Start date (inclusive) in 'YYYY-MM-DD' format, or None for no lower bound
        to_date: End date (inclusive) in 'YYYY-MM-DD' format, or None for no upper bound
    
    Returns:
        Filtered list of match results
    """
    if from_date is None and to_date is None:
        return match_results  # No filtering needed
    
    filtered: list[PnlResult] = []
    for match in match_results:
        sell_id: int = match['sell_id']
        if sell_id not in trades_by_id:
            raise PnlCalculationError(f"SELL trade_id {sell_id} not found for date filtering")
        
        sell_trade: TradeDict = trades_by_id[sell_id]
        if 'trade_date' not in sell_trade:
            raise PnlCalculationError(f"SELL trade_id {sell_id} missing 'trade_date' field")
        
        sell_date: str = sell_trade['trade_date']
        
        # Check date range
        include = True
        if from_date is not None and sell_date < from_date:
            include = False
        if to_date is not None and sell_date > to_date:
            include = False
        
        if include:
            filtered.append(match)
    
    return filtered
