"""MTF interest calculation layer (post-FIFO)."""

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable, Mapping

from core.allocations import allocate_proportional_amount, round_divide


ANNUAL_RATE_PPM = 96500  # 9.65%


def _calendar_holding_days(buy_date: str, sell_date: str) -> int:
    buy = datetime.strptime(buy_date, "%Y-%m-%d").date()
    sell = datetime.strptime(sell_date, "%Y-%m-%d").date()
    days = (sell - buy).days
    return days if days > 0 else 0


def apply_mtf_interest(
    match_results: Iterable[Mapping[str, Any]],
    trades_by_id: Mapping[int, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """
    Enrich match results with MTF interest and net P/L.

    Allocation order rule (deterministic):
    - matched quantities are consumed in FIFO match order
    - remainder paise is assigned to the LAST match for the BUY trade

    Returns a new list of dicts with fields:
    - matched_mtf_amount
    - holding_days
    - mtf_interest
    - mtf_rate_ppm
    - net_pnl
    """
    match_list = list(match_results)

    # Group matched quantities by buy_id for mtf allocation
    qty_by_buy: defaultdict[int, list[int]] = defaultdict(list)
    for match in match_list:
        qty_by_buy[match['buy_id']].append(match['matched_quantity'])

    mtf_allocs_by_buy: dict[int, list[int]] = {}
    for buy_id, qtys in qty_by_buy.items():
        trade = trades_by_id[buy_id]
        if (trade.get('type1') or '').lower() != 'mtf':
            continue
        mtf_amount = int(trade.get('mtf_amount') or 0)
        if mtf_amount <= 0:
            continue
        allocs, _allocated_total = allocate_proportional_amount(
            mtf_amount,
            int(trade['quantity']),
            qtys
        )
        mtf_allocs_by_buy[buy_id] = allocs

    mtf_alloc_idx: defaultdict[int, int] = defaultdict(int)
    results: list[dict[str, Any]] = []

    for match in match_list:
        buy_id = match['buy_id']
        sell_id = match['sell_id']
        buy_trade = trades_by_id[buy_id]
        sell_trade = trades_by_id[sell_id]

        holding_days = _calendar_holding_days(buy_trade['trade_date'], sell_trade['trade_date'])

        matched_mtf_amount = 0
        if buy_id in mtf_allocs_by_buy:
            idx = mtf_alloc_idx[buy_id]
            matched_mtf_amount = mtf_allocs_by_buy[buy_id][idx]
            mtf_alloc_idx[buy_id] += 1

        interest = 0
        raw_rate_ppm = buy_trade.get('mtf_rate_ppm')
        if raw_rate_ppm is None:
            rate_ppm = 96500
        else:
            try:
                rate_ppm = float(raw_rate_ppm)
            except (ValueError, TypeError):
                rate_ppm = 96500

        if matched_mtf_amount > 0 and holding_days > 0:
            interest = round_divide(matched_mtf_amount * rate_ppm * holding_days, 365 * 1_000_000)

        gross_pnl = match.get('gross_pnl')
        if gross_pnl is None:
            matched_buy_total = match['buy_cost'] + match['buy_brokerage_alloc']
            matched_sell_total = match['sell_value'] - match['sell_brokerage_alloc']
            gross_pnl = matched_sell_total - matched_buy_total

        enriched = dict(match)
        enriched['matched_mtf_amount'] = matched_mtf_amount
        enriched['holding_days'] = holding_days
        enriched['mtf_interest'] = interest
        enriched['mtf_rate_ppm'] = rate_ppm if matched_mtf_amount > 0 else 0
        enriched['net_pnl'] = gross_pnl - interest
        results.append(enriched)

    return results
