"""Trade unit builder.

Builds human-readable trade units from raw trades and FIFO match results.
This is a presentation layer and does not modify FIFO logic.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, TypedDict

from core.fifo_matcher import TradeTuple
from core.pnl_calculator import PnlResult


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
    realized_pnl: int = 0
    first_buy_date: str | None = None
    last_sell_date: str | None = None
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
    match_results: Iterable[PnlResult],
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
    match_results: list[PnlResult]
) -> list[TradeUnit]:
    pnl_by_sell: defaultdict[int, list[PnlResult]] = defaultdict(list)
    for pnl in match_results:
        pnl_by_sell[pnl['sell_id']].append(pnl)

    trades_by_contract: defaultdict[tuple[str, str, str | None, float | None, str | None], list[TradeTuple]] = defaultdict(list)
    for trade in trades:
        trades_by_contract[_contract_key(trade)].append(trade)

    units: list[TradeUnit] = []
    unit_index = 1

    for contract_key, contract_trades in trades_by_contract.items():
        contract_trades.sort(key=lambda t: (t[1], t[0]))
        current: UnitAccumulator | None = None

        for trade in contract_trades:
            trade_id = trade[0]
            trade_date = trade[1]
            trade_type = trade[3]
            quantity = trade[8]
            price = trade[9]
            brokerage = trade[10]

            if current is None:
                current = _start_unit(contract_key)

            if trade_type == "BUY":
                current.total_buy_qty += quantity
                current.buy_cost_ex_brokerage += quantity * price
                current.buy_brokerage += brokerage
                current.buy_trade_ids.append(trade_id)
                if current.first_buy_date is None:
                    current.first_buy_date = trade_date
            elif trade_type == "SELL":
                current.total_sell_qty += quantity
                current.sell_value_ex_brokerage += quantity * price
                current.sell_brokerage += brokerage
                current.sell_trade_ids.append(trade_id)
                current.last_sell_date = trade_date
                for pnl in pnl_by_sell.get(trade_id, []):
                    current.realized_pnl += pnl['realized_pnl']
                    current.matched_buy_cost += pnl['buy_cost']
                    current.matched_buy_brokerage += pnl['buy_brokerage_alloc']

            net_qty = current.total_buy_qty - current.total_sell_qty
            if net_qty == 0 and current.total_sell_qty > 0:
                units.append(_finalize_unit(current, status="Closed", unit_index=unit_index))
                unit_index += 1
                current = None

        if current is not None:
            units.append(_finalize_unit(current, status="Open", unit_index=unit_index))
            unit_index += 1

    return units


def _build_sell_units(
    trades: list[TradeTuple],
    match_results: list[PnlResult]
) -> list[TradeUnit]:
    trades_by_id = {trade[0]: trade for trade in trades}
    pnl_by_sell: defaultdict[int, list[PnlResult]] = defaultdict(list)
    for pnl in match_results:
        pnl_by_sell[pnl['sell_id']].append(pnl)

    sell_keys = []
    for sell_id in pnl_by_sell:
        if sell_id in trades_by_id:
            sell_trade = trades_by_id[sell_id]
            sell_keys.append((sell_trade[1], sell_id))
    sell_keys.sort()

    units: list[TradeUnit] = []
    unit_index = 1

    for _sell_date, sell_id in sell_keys:
        sell_trade = trades_by_id[sell_id]
        contract_key = _contract_key(sell_trade)
        equity, type1, type2, strike, expiry = contract_key

        sell_matches = pnl_by_sell[sell_id]
        total_buy_qty = sum(p['matched_quantity'] for p in sell_matches)
        total_sell_qty = total_buy_qty
        buy_cost = sum(p['buy_cost'] for p in sell_matches)
        sell_value = sum(p['sell_value'] for p in sell_matches)
        buy_brokerage = sum(p['buy_brokerage_alloc'] for p in sell_matches)
        sell_brokerage = sum(p['sell_brokerage_alloc'] for p in sell_matches)
        realized_pnl = sum(p['realized_pnl'] for p in sell_matches)

        avg_buy_price = float(buy_cost / total_buy_qty) if total_buy_qty else 0
        avg_sell_price = float(sell_value / total_sell_qty) if total_sell_qty else 0

        buy_trade_ids = sorted({p['buy_id'] for p in sell_matches})
        sell_trade_ids = [sell_id]

        buy_dates = [trades_by_id[bid][1] for bid in buy_trade_ids if bid in trades_by_id]
        holding_days = 0
        if buy_dates:
            holding_days = (_parse_date(sell_trade[1]) - _parse_date(min(buy_dates))).days

        start_date = min(buy_dates) if buy_dates else None
        end_date = sell_trade[1]

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
            remaining_investment=0,
            holding_days=holding_days,
            status="Closed",
            remaining_qty=0,
            buy_trade_ids=buy_trade_ids,
            sell_trade_ids=sell_trade_ids
        ))
        unit_index += 1

    matched_qty_per_buy: defaultdict[int, int] = defaultdict(int)
    for pnl in match_results:
        matched_qty_per_buy[pnl['buy_id']] += pnl['matched_quantity']

    open_agg: dict[tuple[str, str, str | None, float | None, str | None], UnitAccumulator] = {}
    for trade in trades:
        trade_id = trade[0]
        trade_type = trade[3]
        if trade_type != "BUY":
            continue
        quantity = trade[8]
        price = trade[9]
        brokerage = trade[10]

        matched_qty = matched_qty_per_buy.get(trade_id, 0)
        remaining_qty = quantity - matched_qty
        if remaining_qty <= 0:
            continue

        contract_key = _contract_key(trade)
        if contract_key not in open_agg:
            open_agg[contract_key] = _start_unit(contract_key)

        unit = open_agg[contract_key]
        unit.total_buy_qty += remaining_qty
        unit.buy_cost_ex_brokerage += remaining_qty * price
        unit.buy_brokerage += (brokerage * remaining_qty) // quantity
        unit.buy_trade_ids.append(trade_id)
        if unit.first_buy_date is None:
            unit.first_buy_date = trade[1]

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
    if unit.first_buy_date and unit.last_sell_date:
        holding_days = (_parse_date(unit.last_sell_date) - _parse_date(unit.first_buy_date)).days

    remaining_qty = max(unit.total_buy_qty - unit.total_sell_qty, 0)
    remaining_investment = 0
    if remaining_qty > 0:
        if unit.matched_buy_cost or unit.matched_buy_brokerage:
            # FIFO-based remaining cost (includes proportional brokerage).
            remaining_investment = total_buy_cost - unit.matched_buy_cost - unit.matched_buy_brokerage
        elif total_buy_qty > 0:
            remaining_investment = (total_buy_cost * remaining_qty) // total_buy_qty

    return TradeUnit(
        contract_key=unit.contract_key,
        trade_label=format_trade_label(unit.equity, unit.first_buy_date, unit.last_sell_date, unit_index),
        contract_display=format_contract_display(unit.equity, unit.type1, unit.type2, unit.strike, unit.expiry),
        start_date=unit.first_buy_date,
        end_date=unit.last_sell_date,
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
        remaining_investment=remaining_investment,
        holding_days=holding_days,
        status=status,
        remaining_qty=remaining_qty,
        buy_trade_ids=list(unit.buy_trade_ids or []),
        sell_trade_ids=list(unit.sell_trade_ids or [])
    )
