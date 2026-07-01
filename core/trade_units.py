"""Trade unit builder.

Builds human-readable trade units from raw trades and FIFO match results.
This is a presentation layer and does not modify FIFO logic.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, TypedDict

from core.fifo_matcher import TradeTuple
from core.position_state_engine import process_trades, EventRole, PositionSide


class TradeUnit(TypedDict):
    contract_key: tuple[str, str, str | None, float | None, str | None]
    trade_label: str
    contract_display: str
    start_date: str | None
    end_date: str | None
    equity: str
    type1: str
    type2: str | None
    strike: float | None
    expiry: str | None
    total_buy_qty: int
    avg_buy_price: float
    total_sell_qty: int
    avg_sell_price: float
    total_buy_cost: int
    total_sell_value: int
    realized_pnl: int
    mtf_interest: int
    net_pnl: int
    remaining_investment: int
    holding_days: int
    status: str
    remaining_qty: int
    buy_trade_ids: list[int]
    sell_trade_ids: list[int]


@dataclass
class UnitAccumulator:
    contract_key: tuple[str, str, str | None, float | None, str | None]
    equity: str
    type1: str
    type2: str | None
    strike: float | None
    expiry: str | None
    total_buy_qty: int = 0
    total_sell_qty: int = 0
    buy_cost_ex_brokerage: int = 0
    sell_value_ex_brokerage: int = 0
    buy_brokerage: int = 0
    sell_brokerage: int = 0
    matched_buy_cost: int = 0
    matched_buy_brokerage: int = 0
    matched_sell_value: int = 0
    matched_sell_brokerage: int = 0
    realized_pnl: int = 0
    mtf_interest: int = 0
    net_pnl: int = 0
    first_opening_date: str | None = None
    last_closing_date: str | None = None
    position_side: str | None = None
    buy_trade_ids: list[int] | None = None
    sell_trade_ids: list[int] | None = None

    def __post_init__(self) -> None:
        if self.buy_trade_ids is None:
            self.buy_trade_ids = []
        if self.sell_trade_ids is None:
            self.sell_trade_ids = []


def _parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def _format_date_display(date_str: str | None) -> str:
    if not date_str:
        return ""
    return _parse_date(date_str).strftime("%d %b %Y")


def _format_date_short(date_str: str | None, include_year: bool = False) -> str:
    if not date_str:
        return ""
    fmt = "%d %b %Y" if include_year else "%d %b"
    return _parse_date(date_str).strftime(fmt)


def format_contract_display(
    equity: str,
    type1: str,
    type2: str | None,
    strike: float | None,
    expiry: str | None
) -> str:
    if type1 == "options":
        expiry_label = _format_date_display(expiry)
        strike_label = f"{int(strike)}" if strike is not None and strike.is_integer() else f"{strike}" if strike is not None else ""
        return f"{equity} {strike_label} {type2} ({expiry_label})"
    if type1 == "futures":
        expiry_label = _format_date_display(expiry)
        return f"{equity} (Expiry: {expiry_label})"
    return f"{equity} ({type1.title()})"


def format_trade_label(
    equity: str,
    start_date: str | None,
    end_date: str | None,
    unit_index: int
) -> str:
    if start_date and end_date:
        start_dt = _parse_date(start_date)
        end_dt = _parse_date(end_date)
        same_year = start_dt.year == end_dt.year
        start_label = _format_date_short(start_date, include_year=not same_year)
        end_label = _format_date_short(end_date, include_year=True)
        return f"{equity} {start_label} → {end_label}"
    if start_date and not end_date:
        start_label = _format_date_short(start_date, include_year=True)
        return f"{equity} {start_label} → Open"
    return f"Trade #{unit_index}"


def _contract_key(trade: TradeTuple) -> tuple[str, str, str | None, float | None, str | None]:
    equity = trade[2]
    type1 = trade[4] or "delivery"
    type2 = trade[5]
    strike = trade[6]
    expiry = trade[7]
    return (equity, type1, type2, strike, expiry)


def _start_unit(contract_key: tuple[str, str, str | None, float | None, str | None]) -> UnitAccumulator:
    equity, type1, type2, strike, expiry = contract_key
    return UnitAccumulator(
        contract_key=contract_key,
        equity=equity,
        type1=type1,
        type2=type2,
        strike=strike,
        expiry=expiry
    )


def build_trade_units(
    trades: Iterable[TradeTuple],
    match_results: Iterable[Mapping[str, Any]],
    *,
    grouping: str = "lifecycle"
) -> list[TradeUnit]:
    """
    Build trade units per contract using FIFO match results.

    Args:
        trades: Raw trades from fetch_active_trades()
        match_results: Results from calculate_match_pnl()
        grouping: "lifecycle" (flat-to-flat) or "sell" (per SELL trade)

    Returns:
        List of trade units. Monetary values are in paise (including avg prices).
    """
    trade_list = list(trades)
    pnl_list = list(match_results)

    if grouping == "sell":
        return _build_sell_units(trade_list, pnl_list)

    return _build_lifecycle_units(trade_list, pnl_list)


def _build_lifecycle_units(
    trades: list[TradeTuple],
    match_results: list[Mapping[str, Any]]
) -> list[TradeUnit]:
    events = process_trades(trades)
    # A single trade_id can produce multiple events (e.g. position flips).
    # Build a lookup that maps trade_id to a list of events.
    events_by_id: defaultdict[int, list] = defaultdict(list)
    for e in events:
        events_by_id[e.trade_id].append(e)
    
    pnl_by_closing: defaultdict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for pnl in match_results:
        sell_id = int(pnl['sell_id'])
        buy_id = int(pnl['buy_id'])
        # Check if the sell_id has a CLOSING event
        sell_events = events_by_id.get(sell_id, [])
        is_sell_closing = any(e.event_role is EventRole.CLOSING for e in sell_events)
        if is_sell_closing:
            pnl_by_closing[sell_id].append(pnl)
        else:
            pnl_by_closing[buy_id].append(pnl)

    events_by_contract: defaultdict[tuple[str, str, str | None, float | None, str | None], list] = defaultdict(list)
    for event in events:
        events_by_contract[event.contract_key].append(event)

    units: list[TradeUnit] = []
    unit_index = 1

    for contract_key, contract_events in events_by_contract.items():
        current: UnitAccumulator | None = None

        for event in contract_events:
            trade_id = event.trade_id
            trade_date = event.trade_date
            trade_type = event.original_direction.value
            quantity = event.quantity
            price = event.price
            brokerage = event.brokerage

            if current is None:
                current = _start_unit(contract_key)
                current.position_side = event.position_side.value

            if trade_type == "BUY":
                current.total_buy_qty += quantity
                current.buy_cost_ex_brokerage += quantity * price
                current.buy_brokerage += brokerage
                current.buy_trade_ids.append(trade_id)
            elif trade_type == "SELL":
                current.total_sell_qty += quantity
                current.sell_value_ex_brokerage += quantity * price
                current.sell_brokerage += brokerage
                current.sell_trade_ids.append(trade_id)
                
            if event.event_role is EventRole.OPENING:
                if current.first_opening_date is None:
                    current.first_opening_date = trade_date
            elif event.event_role is EventRole.CLOSING:
                current.last_closing_date = trade_date
                for pnl in pnl_by_closing.get(trade_id, []):
                    current.realized_pnl += int(pnl['realized_pnl'])
                    current.mtf_interest += int(pnl.get('mtf_interest', 0))
                    current.net_pnl += int(pnl.get('net_pnl', pnl['realized_pnl']))
                    current.matched_buy_cost += int(pnl['buy_cost'])
                    current.matched_buy_brokerage += int(pnl.get('buy_brokerage_alloc', 0))
                    current.matched_sell_value += int(pnl.get('sell_value', 0))
                    current.matched_sell_brokerage += int(pnl.get('sell_brokerage_alloc', 0))

            if current.total_buy_qty == current.total_sell_qty and current.total_sell_qty > 0:
                units.append(_finalize_unit(current, status="Closed", unit_index=unit_index))
                unit_index += 1
                current = None

        if current is not None:
            units.append(_finalize_unit(current, status="Open", unit_index=unit_index))
            unit_index += 1

    return units


def _build_sell_units(
    trades: list[TradeTuple],
    match_results: list[Mapping[str, Any]]
) -> list[TradeUnit]:
    # Despite the name (for UI backward compatibility), this groups by CLOSING trade.
    events = process_trades(trades)
    # A single trade_id can produce multiple events (e.g. position flips).
    events_by_id: defaultdict[int, list] = defaultdict(list)
    for e in events:
        events_by_id[e.trade_id].append(e)
    
    trades_by_id = {trade[0]: trade for trade in trades}
    pnl_by_closing: defaultdict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for pnl in match_results:
        sell_id = int(pnl['sell_id'])
        buy_id = int(pnl['buy_id'])
        sell_events = events_by_id.get(sell_id, [])
        is_sell_closing = any(e.event_role is EventRole.CLOSING for e in sell_events)
        if is_sell_closing:
            pnl_by_closing[sell_id].append(pnl)
        else:
            pnl_by_closing[buy_id].append(pnl)

    closing_keys = []
    for closing_id in pnl_by_closing:
        if closing_id in trades_by_id:
            closing_trade = trades_by_id[closing_id]
            closing_keys.append((closing_trade[1], closing_id))
    closing_keys.sort()

    units: list[TradeUnit] = []
    unit_index = 1

    for _closing_date, closing_id in closing_keys:
        closing_trade = trades_by_id[closing_id]
        # Find the CLOSING event for this trade_id (flip trades have both CLOSING and OPENING)
        closing_event_list = events_by_id.get(closing_id, [])
        closing_event = next((e for e in closing_event_list if e.event_role is EventRole.CLOSING), closing_event_list[0] if closing_event_list else None)
        contract_key = _contract_key(closing_trade)
        equity, type1, type2, strike, expiry = contract_key

        matches = pnl_by_closing[closing_id]
        total_matched_qty = sum(int(p['matched_quantity']) for p in matches)
        total_buy_qty = total_matched_qty
        total_sell_qty = total_matched_qty
        
        buy_cost = sum(int(p['buy_cost']) for p in matches)
        sell_value = sum(int(p.get('sell_value', 0)) for p in matches)
        buy_brokerage = sum(int(p.get('buy_brokerage_alloc', 0)) for p in matches)
        sell_brokerage = sum(int(p.get('sell_brokerage_alloc', 0)) for p in matches)
        realized_pnl = sum(int(p['realized_pnl']) for p in matches)

        avg_buy_price = float(buy_cost / total_buy_qty) if total_buy_qty else 0
        avg_sell_price = float(sell_value / total_sell_qty) if total_sell_qty else 0

        buy_trade_ids = sorted({int(p['buy_id']) for p in matches})
        sell_trade_ids = sorted({int(p['sell_id']) for p in matches})

        if closing_event.position_side is PositionSide.LONG:
            opening_ids = buy_trade_ids
        else:
            opening_ids = sell_trade_ids

        opening_dates = [trades_by_id[tid][1] for tid in opening_ids if tid in trades_by_id]
        holding_days = 0
        if opening_dates:
            holding_days = (_parse_date(closing_trade[1]) - _parse_date(min(opening_dates))).days

        start_date = min(opening_dates) if opening_dates else None
        end_date = closing_trade[1]

        units.append(TradeUnit(
            contract_key=contract_key,
            trade_label=format_trade_label(equity, start_date, end_date, unit_index),
            contract_display=format_contract_display(equity, type1, type2, strike, expiry),
            start_date=start_date,
            end_date=end_date,
            equity=equity,
            type1=type1,
            type2=type2,
            strike=strike,
            expiry=expiry,
            total_buy_qty=total_buy_qty,
            avg_buy_price=avg_buy_price,
            total_sell_qty=total_sell_qty,
            avg_sell_price=avg_sell_price,
            total_buy_cost=buy_cost + buy_brokerage,
            total_sell_value=sell_value - sell_brokerage,
            realized_pnl=realized_pnl,
            mtf_interest=sum(int(p.get('mtf_interest', 0)) for p in matches),
            net_pnl=sum(int(p.get('net_pnl', p['realized_pnl'])) for p in matches),
            remaining_investment=0,
            holding_days=holding_days,
            status="Closed",
            remaining_qty=0,
            buy_trade_ids=buy_trade_ids,
            sell_trade_ids=sell_trade_ids
        ))
        unit_index += 1

    # Open quantities
    matched_qty_per_opening: defaultdict[int, int] = defaultdict(int)
    for pnl in match_results:
        sell_id = int(pnl['sell_id'])
        buy_id = int(pnl['buy_id'])
        sell_events = events_by_id.get(sell_id, [])
        is_sell_opening = any(e.event_role is EventRole.OPENING for e in sell_events)
        if is_sell_opening:
            matched_qty_per_opening[sell_id] += int(pnl['matched_quantity'])
        else:
            matched_qty_per_opening[buy_id] += int(pnl['matched_quantity'])

    # Detect flip trades: trade_ids that have both CLOSING and OPENING events.
    # For these, matched_qty_per_opening over-counts because it includes
    # matches from the CLOSING phase. Subtract the closing event quantity.
    flip_closing_qty: dict[int, int] = {}
    flip_opening_ids: set[int] = set()
    for event in events:
        if event.event_role is EventRole.CLOSING:
            flip_closing_qty[event.trade_id] = flip_closing_qty.get(event.trade_id, 0) + event.quantity
        if event.event_role is EventRole.OPENING:
            flip_opening_ids.add(event.trade_id)

    open_agg: dict[tuple, UnitAccumulator] = {}
    for event in events:
        if event.event_role is not EventRole.OPENING:
            continue
            
        trade_id = event.trade_id
        quantity = event.quantity
        price = event.price
        brokerage = event.brokerage

        total_matched = matched_qty_per_opening.get(trade_id, 0)
        # For flip trades, subtract the closing-phase matches
        if trade_id in flip_closing_qty and trade_id in flip_opening_ids:
            total_matched = max(0, total_matched - flip_closing_qty[trade_id])
        remaining_qty = quantity - total_matched
        if remaining_qty <= 0:
            continue

        contract_key = event.contract_key
        if contract_key not in open_agg:
            unit = _start_unit(contract_key)
            unit.position_side = event.position_side.value
            open_agg[contract_key] = unit

        unit = open_agg[contract_key]
        if event.original_direction.value == "BUY":
            unit.total_buy_qty += remaining_qty
            unit.buy_cost_ex_brokerage += remaining_qty * price
            unit.buy_brokerage += (brokerage * remaining_qty) // quantity
            unit.buy_trade_ids.append(trade_id)
        else:
            unit.total_sell_qty += remaining_qty
            unit.sell_value_ex_brokerage += remaining_qty * price
            unit.sell_brokerage += (brokerage * remaining_qty) // quantity
            unit.sell_trade_ids.append(trade_id)
            
        if unit.first_opening_date is None:
            unit.first_opening_date = event.trade_date

    for unit in open_agg.values():
        units.append(_finalize_unit(unit, status="Open", unit_index=unit_index))
        unit_index += 1

    return units


def _finalize_unit(unit: UnitAccumulator, status: str, unit_index: int) -> TradeUnit:
    total_buy_qty = unit.total_buy_qty
    total_sell_qty = unit.total_sell_qty
    avg_buy_price = float(unit.buy_cost_ex_brokerage / total_buy_qty) if total_buy_qty else 0
    avg_sell_price = float(unit.sell_value_ex_brokerage / total_sell_qty) if total_sell_qty else 0

    total_buy_cost = unit.buy_cost_ex_brokerage + unit.buy_brokerage
    total_sell_value = unit.sell_value_ex_brokerage - unit.sell_brokerage

    holding_days = 0
    if unit.first_opening_date and unit.last_closing_date:
        holding_days = (_parse_date(unit.last_closing_date) - _parse_date(unit.first_opening_date)).days
    elif unit.first_opening_date and status == "Open":
        holding_days = (datetime.today().date() - _parse_date(unit.first_opening_date).date()).days

    remaining_qty = abs(unit.total_buy_qty - unit.total_sell_qty)
    remaining_investment = 0
    
    if remaining_qty > 0:
        if unit.position_side == "LONG":
            if unit.matched_buy_cost or unit.matched_buy_brokerage:
                remaining_investment = total_buy_cost - unit.matched_buy_cost - unit.matched_buy_brokerage
            elif total_buy_qty > 0:
                remaining_investment = (total_buy_cost * remaining_qty) // total_buy_qty
        elif unit.position_side == "SHORT":
            if unit.matched_sell_value or unit.matched_sell_brokerage:
                remaining_investment = total_sell_value - unit.matched_sell_value + unit.matched_sell_brokerage
            elif total_sell_qty > 0:
                remaining_investment = (total_sell_value * remaining_qty) // total_sell_qty

    return TradeUnit(
        contract_key=unit.contract_key,
        trade_label=format_trade_label(unit.equity, unit.first_opening_date, unit.last_closing_date, unit_index),
        contract_display=format_contract_display(unit.equity, unit.type1, unit.type2, unit.strike, unit.expiry),
        start_date=unit.first_opening_date,
        end_date=unit.last_closing_date,
        equity=unit.equity,
        type1=unit.type1,
        type2=unit.type2,
        strike=unit.strike,
        expiry=unit.expiry,
        total_buy_qty=total_buy_qty,
        avg_buy_price=avg_buy_price,
        total_sell_qty=total_sell_qty,
        avg_sell_price=avg_sell_price,
        total_buy_cost=total_buy_cost,
        total_sell_value=total_sell_value,
        realized_pnl=unit.realized_pnl,
        mtf_interest=unit.mtf_interest,
        net_pnl=unit.net_pnl if unit.net_pnl else unit.realized_pnl,
        remaining_investment=remaining_investment,
        holding_days=holding_days,
        status=status,
        remaining_qty=remaining_qty,
        buy_trade_ids=list(unit.buy_trade_ids or []),
        sell_trade_ids=list(unit.sell_trade_ids or [])
    )
