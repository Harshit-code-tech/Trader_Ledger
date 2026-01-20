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




