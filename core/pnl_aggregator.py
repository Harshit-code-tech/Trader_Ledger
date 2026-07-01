from collections import defaultdict
from typing import Any, Mapping, Sequence, TypedDict


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
    matched_buy_total: int
    matched_sell_total: int
    gross_pnl: int
    mtf_interest: int
    net_pnl: int


class TradeDict(TypedDict):
    id: int
    trade_date: str
    equity: str
    trade_type: str
    type1: str | None
    type2: str | None
    strike: float | None
    expiry: str | None
    quantity: int
    price: int
    brokerage: int
    brokerage_auto: int
    brokerage_override: int | None
    mtf_amount: int
    notes: str
    is_active: int


def _get_closing_trade(match: Mapping[str, Any], trades_by_id: dict[int, TradeDict]) -> tuple[int, str, TradeDict]:
    """Helper to determine the closing trade (and its date) from a match."""
    sell_id = int(match['sell_id'])
    buy_id = int(match['buy_id'])
    
    if sell_id not in trades_by_id:
        raise PnlCalculationError(f"SELL trade_id {sell_id} not found")
    if buy_id not in trades_by_id:
        raise PnlCalculationError(f"BUY trade_id {buy_id} not found")
        
    sell_trade = trades_by_id[sell_id]
    buy_trade = trades_by_id[buy_id]
    
    sell_date = sell_trade.get('trade_date')
    buy_date = buy_trade.get('trade_date')
    
    if not sell_date or not buy_date:
        raise PnlCalculationError("Missing trade_date")
        
    if sell_date > buy_date:
        return sell_id, sell_date, sell_trade
    elif buy_date > sell_date:
        return buy_id, buy_date, buy_trade
    else:
        # Same date (intraday). Use the higher ID assuming it was inserted later chronologically.
        if sell_id > buy_id:
            return sell_id, sell_date, sell_trade
        else:
            return buy_id, buy_date, buy_trade


def aggregate_pnl_by_closing_trade(match_results: Sequence[Mapping[str, Any]], trades_by_id: dict[int, TradeDict], pnl_field: str = "realized_pnl") -> dict[int, int]:
    """
    Aggregates realized P/L per closing trade.
    Input: list of match dicts and trades_by_id.
    Output: dict of closing_trade_id -> total realized P/L.
    """
    closing_totals: defaultdict[int, int] = defaultdict(int)
    for match in match_results:
        assert 'sell_id' in match and pnl_field in match, "Missing required fields in match record."
        closing_id, _, _ = _get_closing_trade(match, trades_by_id)
        closing_totals[closing_id] += int(match[pnl_field])
    return dict(closing_totals)

def aggregate_pnl_by_date(
    match_results: Sequence[Mapping[str, Any]],
    trades_by_id: dict[int, TradeDict],
    pnl_field: str = "realized_pnl"
) -> dict[str, int]:
    """
    Aggregates realized P/L per closing date.
    Input: match_results, trades_by_id
    Output: dict of trade_date -> total realized P/L for that date
    """
    date_totals: defaultdict[str, int] = defaultdict(int)
    for match in match_results:
        assert pnl_field in match, "Missing required fields in match record."
        _, closing_date, _ = _get_closing_trade(match, trades_by_id)
        date_totals[closing_date] += int(match[pnl_field])
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


def aggregate_pnl_by_equity(
    match_results: Sequence[Mapping[str, Any]],
    trades_by_id: dict[int, TradeDict],
    pnl_field: str = "realized_pnl"
) -> dict[str, int]:
    """
    Aggregates realized P/L per equity (stock symbol).
    """
    equity_totals: defaultdict[str, int] = defaultdict(int)
    for match in match_results:
        assert pnl_field in match, "Missing required fields in match record."
        _, _, closing_trade = _get_closing_trade(match, trades_by_id)
        equity: str = closing_trade['equity']
        equity_totals[equity] += int(match[pnl_field])
    return dict(equity_totals)


def aggregate_pnl_by_type1(
    match_results: Sequence[Mapping[str, Any]],
    trades_by_id: dict[int, TradeDict],
    pnl_field: str = "realized_pnl"
) -> dict[str, int]:
    """
    Aggregates realized P/L per type1 (e.g. delivery, intraday).
    """
    type1_totals: defaultdict[str, int] = defaultdict(int)
    for match in match_results:
        assert pnl_field in match, "Missing required fields in match record."
        _, _, closing_trade = _get_closing_trade(match, trades_by_id)
        type1: str = closing_trade.get('type1') or "unknown"
        type1_totals[type1.strip().lower()] += int(match[pnl_field])
    return dict(type1_totals)


def filter_matches_by_date_range(
    match_results: Sequence[Mapping[str, Any]], 
    trades_by_id: dict[int, TradeDict],
    from_date: str | None = None,
    to_date: str | None = None
) -> list[dict[str, Any]]:
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
        return list(match_results)
    
    filtered: list[dict[str, Any]] = []
    for match in match_results:
        _, closing_date, _ = _get_closing_trade(match, trades_by_id)
        
        include = True
        if from_date is not None and closing_date < from_date:
            include = False
        if to_date is not None and closing_date > to_date:
            include = False
        
        if include:
            filtered.append(dict(match))
    
    return filtered


def aggregate_trade_value_by_date(
    match_results: Sequence[Mapping[str, Any]],
    trades_by_id: dict[int, TradeDict]
) -> dict[str, int]:
    """
    Aggregates trade value per SELL date.
    day_trade_value = buy_amount + sell_amount (brokerage excluded).
    """
    date_totals: defaultdict[str, int] = defaultdict(int)
    for match in match_results:
        _, closing_date, _ = _get_closing_trade(match, trades_by_id)
        day_trade_value = int(match['buy_cost']) + int(match['sell_value'])
        date_totals[closing_date] += day_trade_value
    return dict(date_totals)
