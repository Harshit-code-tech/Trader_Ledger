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
from collections import defaultdict


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
    quantity: int
    price: int
    brokerage: int
    notes: str
    is_active: int


class OpenPosition(TypedDict):
    equity: str
    status: str  # "OPEN" or "CLOSED"
    remaining_qty: int
    avg_price: float  # In rupees (price/100)
    total_cost: int  # In paise
    unrealized_pnl: int  # In paise (will be 0 for now, needs market price)


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
    # Track matched quantities per buy trade
    matched_qty_per_buy: defaultdict[int, int] = defaultdict(int)
    
    for match in matches:
        buy_id = match['buy_id']
        matched_qty_per_buy[buy_id] += match['matched_quantity']
    
    # Calculate remaining quantities for all BUY trades
    open_positions_by_equity: defaultdict[str, list[dict]] = defaultdict(list)
    
    for trade_id, trade in trades_by_id.items():
        if trade['trade_type'] != 'BUY':
            continue
        
        original_qty = trade['quantity']
        matched_qty = matched_qty_per_buy.get(trade_id, 0)
        remaining_qty = original_qty - matched_qty
        
        if remaining_qty > 0:
            equity = trade['equity']
            open_positions_by_equity[equity].append({
                'trade_id': trade_id,
                'remaining_qty': remaining_qty,
                'price': trade['price'],  # In paise
                'brokerage': trade['brokerage'],
                'trade_date': trade['trade_date']
            })
    
    # Aggregate open positions per equity
    results: list[OpenPosition] = []
    
    for equity, positions in open_positions_by_equity.items():
        total_qty = sum(p['remaining_qty'] for p in positions)
        total_cost = sum(p['remaining_qty'] * p['price'] for p in positions)
        total_brokerage = sum(
            (p['brokerage'] * p['remaining_qty']) // trades_by_id[p['trade_id']]['quantity']
            for p in positions
        )
        
        # Calculate average price (in rupees)
        avg_price_paise = total_cost / total_qty if total_qty > 0 else 0
        avg_price_rupees = avg_price_paise / 100
        
        # Calculate unrealized P/L if market prices provided
        unrealized_pnl = 0
        if market_prices and equity in market_prices:
            market_price = market_prices[equity]  # In paise
            current_value = total_qty * market_price
            cost_with_brokerage = total_cost + total_brokerage
            unrealized_pnl = current_value - cost_with_brokerage
        
        results.append(OpenPosition(
            equity=equity,
            status="OPEN",
            remaining_qty=total_qty,
            avg_price=round(avg_price_rupees, 2),
            total_cost=total_cost,
            unrealized_pnl=unrealized_pnl
        ))
    
    # Sort by equity name
    results.sort(key=lambda x: x['equity'])
    
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
