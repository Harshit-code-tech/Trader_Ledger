from collections import defaultdict

class PnlCalculationError(Exception):
    pass

def aggregate_pnl_by_sell(match_results):
    """
    Aggregates realized P/L per SELL trade.
    Input: list of match dicts (from Phase-3), each with 'sell_id' and 'realized_pnl'.
    Output: dict of sell_id -> total realized P/L for that SELL.
    """
    sell_totals = defaultdict(int)
    for match in match_results:
        assert 'sell_id' in match and 'realized_pnl' in match, "Missing required fields in match record."
        sell_totals[match['sell_id']] += match['realized_pnl']
    return dict(sell_totals)

def aggregate_pnl_by_date(match_results, trades_by_id):
    """
    Aggregates realized P/L per SELL date.
    Input: match_results (from Phase-3), trades_by_id (to get SELL trade_date)
    Output: dict of trade_date -> total realized P/L for that date (from SELL trade)
    """
    date_totals = defaultdict(int)
    for match in match_results:
        assert 'sell_id' in match and 'realized_pnl' in match, "Missing required fields in match record."
        sell_id = match['sell_id']
        if sell_id not in trades_by_id:
            raise PnlCalculationError(f"SELL trade_id {sell_id} not found for date aggregation")
        sell_trade = trades_by_id[sell_id]
        if 'trade_date' not in sell_trade:
            raise PnlCalculationError(f"SELL trade_id {sell_id} missing 'trade_date' field")
        sell_date = sell_trade['trade_date']
        date_totals[sell_date] += match['realized_pnl']
    return dict(date_totals)



def aggregate_pnl_by_month(date_totals):
    """
    Input: dict of 'YYYY-MM-DD' -> P/L
    Output: dict of 'YYYY-MM' -> total P/L for that month
    """
    month_totals=defaultdict(int)
    for date_str,pnl in date_totals.items():
        month_key=date_str[:7]  # 'YYYY-MM'
        month_totals[month_key]+=pnl
    return dict(month_totals)




