"""
Open Positions Calculator - v1.1

Computes open (unmatched) positions after FIFO matching.

Definitions:
- Closed position: Quantity fully squared off (remaining_qty = 0)
- Open position: Remaining unmatched buy quantity (remaining_qty > 0)

Logic:
- After FIFO matching, track remaining quantities per buy trade
- If remaining_qty > 0 → OPEN
- Else → CLOSED

This is computed dynamically to avoid state bugs.
"""

from typing import TypedDict
from datetime import datetime, date
from collections import defaultdict

from core.position_state_engine import process_trades, EventRole, PositionSide
from core.fifo_matcher import TradeTuple


class OpenPositionError(Exception):
    pass


class MatchRecord(TypedDict):
    sell_id: int
    buy_id: int
    matched_quantity: int
    equity: str


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


class OpenPosition(TypedDict):
    equity: str
    type1: str | None
    type2: str | None
    strike: float | None
    expiry: str | None
    status: str  # "OPEN" or "CLOSED"
    position_side: str # "LONG" or "SHORT"
    remaining_qty: int
    avg_price: float  # In rupees (price/100)
    total_cost: int  # In paise
    unrealized_pnl: int  # In paise (will be 0 for now, needs market price)
    holding_days: int  # Calendar days since first open


def calculate_open_positions(
    matches: list[MatchRecord],
    trades_by_id: dict[int, TradeDict],
    market_prices: dict[str, int] | None = None
) -> list[OpenPosition]:
    """
    Calculate open (unmatched) positions after FIFO matching.
    
    Args:
        matches: List of FIFO match records
        trades_by_id: Dict of trade_id -> trade data
        market_prices: Optional dict of equity -> current market price (in paise)
                      Used to calculate unrealized P/L for open positions
    
    Returns:
        List of open positions with equity, status, qty, avg price, unrealized P/L
    """
    # Track matched quantities for both sides of the match
    matched_qty_per_trade: defaultdict[int, int] = defaultdict(int)
    
    for match in matches:
        matched_qty_per_trade[match['buy_id']] += match['matched_quantity']
        matched_qty_per_trade[match['sell_id']] += match['matched_quantity']
    
    # 1. Convert TradeDicts to TradeTuples chronologically
    trades_list = sorted(trades_by_id.values(), key=lambda t: (t['trade_date'], t['id']))
    trade_tuples: list[TradeTuple] = []
    for t in trades_list:
        trade_tuples.append((
            t['id'], t['trade_date'], t['equity'], t['trade_type'],
            t.get('type1') or 'delivery', t.get('type2'), t.get('strike'), t.get('expiry'),
            t['quantity'], t['price'], t['brokerage'], t.get('notes', ''),
            t.get('is_active', 1), t.get('brokerage_auto', 0),
            t.get('brokerage_override'), t.get('mtf_amount', 0), t.get('mtf_rate_ppm')
        ))
        
    # 2. Run through Position State Engine
    events = process_trades(trade_tuples)

    # Detect flip trades: trade_ids that produce both CLOSING and OPENING events
    # For these, the closing event's quantity must be excluded from the opening event's matched calc.
    closing_qty_per_trade: dict[int, int] = {}
    opening_event_exists: set[int] = set()
    for event in events:
        if event.event_role is EventRole.CLOSING:
            closing_qty_per_trade[event.trade_id] = closing_qty_per_trade.get(event.trade_id, 0) + event.quantity
        if event.event_role is EventRole.OPENING:
            opening_event_exists.add(event.trade_id)
    # A flip trade has both a CLOSING and an OPENING event for the same trade_id
    flip_trade_closing_qty: dict[int, int] = {
        tid: qty for tid, qty in closing_qty_per_trade.items()
        if tid in opening_event_exists
    }

    # 3. Calculate remaining quantities for all OPENING trades
    open_positions_by_contract: defaultdict[tuple[str, str, str | None, float | None, str | None], list[dict]] = defaultdict(list)
    
    for event in events:
        if event.event_role is EventRole.OPENING:
            total_matched = matched_qty_per_trade[event.trade_id]
            # For flip trades, subtract only the opening-phase matches
            # total_matched includes both closing-phase matches and opening-phase matches
            # closing-phase matches = flip_trade_closing_qty[trade_id]
            # opening-phase matches = total_matched - flip_trade_closing_qty[trade_id]
            flip_close = flip_trade_closing_qty.get(event.trade_id, 0)
            opening_matched = total_matched - flip_close
            remaining_qty = event.quantity - opening_matched
            
            if remaining_qty > 0:
                open_positions_by_contract[event.contract_key].append({
                    'trade_id': event.trade_id,
                    'remaining_qty': remaining_qty,
                    'price': event.price,  # In paise
                    'brokerage': event.brokerage,
                    'trade_date': event.trade_date,
                    'position_side': event.position_side
                })
    
    # Aggregate open positions per contract
    results: list[OpenPosition] = []
    
    for contract, positions in open_positions_by_contract.items():
        equity, type1, type2, strike, expiry = contract
        total_qty = sum(p['remaining_qty'] for p in positions)
        total_cost = sum(p['remaining_qty'] * p['price'] for p in positions)
        total_brokerage = sum(
            (p['brokerage'] * p['remaining_qty']) // trades_by_id[p['trade_id']]['quantity']
            for p in positions
        )

        first_date = min(p['trade_date'] for p in positions)
        holding_days = (date.today() - datetime.strptime(first_date, "%Y-%m-%d").date()).days
        if holding_days < 0:
            holding_days = 0
            
        position_side = positions[0]['position_side']
        
        # Calculate average price (in rupees)
        avg_price_paise = total_cost / total_qty if total_qty > 0 else 0
        avg_price_rupees = avg_price_paise / 100
        
        # Calculate unrealized P/L if market prices provided
        unrealized_pnl = 0
        if market_prices and equity in market_prices:
            market_price = market_prices[equity]  # In paise
            current_value = total_qty * market_price
            
            if position_side is PositionSide.LONG:
                cost_with_brokerage = total_cost + total_brokerage
                unrealized_pnl = current_value - cost_with_brokerage
            else:
                # SHORT: total_cost is our credit from selling. Brokerage is a debit.
                unrealized_pnl = total_cost - current_value - total_brokerage
        
        results.append(OpenPosition(
            equity=equity,
            type1=type1,
            type2=type2,
            strike=strike,
            expiry=expiry,
            status="OPEN",
            position_side=position_side.value,
            remaining_qty=total_qty,
            avg_price=round(avg_price_rupees, 2),
            total_cost=total_cost,
            unrealized_pnl=unrealized_pnl,
            holding_days=holding_days
        ))
    
    # Sort by equity name
    results.sort(key=lambda x: (x['equity'], x.get('type1') or "", x.get('expiry') or ""))
    
    return results


def get_unique_equities(trades_by_id: dict[int, TradeDict]) -> list[str]:
    """
    Get list of unique equity symbols from trades.
    Useful for populating equity dropdown filter.
    
    Args:
        trades_by_id: Dict of trade_id -> trade data
    
    Returns:
        Sorted list of unique equity symbols
    """
    equities = set()
    for trade in trades_by_id.values():
        if 'equity' in trade:
            equities.add(trade['equity'])
    
    return sorted(list(equities))


def get_unique_type1s(trades_by_id: dict[int, TradeDict]) -> list[str]:
    """
    Get list of unique type1 values from trades.
    Useful for populating type1 dropdown filter.
    
    Args:
        trades_by_id: Dict of trade_id -> trade data
    
    Returns:
        Sorted list of unique type1 values
    """
    type1s = set()
    for trade in trades_by_id.values():
        val = trade.get('type1')
        if val:
            type1s.add(val.strip().lower())
    
    return sorted(list(type1s))
