from typing import TypedDict


class PnlCalculationError(Exception):
    pass


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
    notes: str
    is_active: int


class MatchRecord(TypedDict):
    sell_id: int
    buy_id: int
    matched_quantity: int
    equity: str


class PnlResult(TypedDict):
    sell_id: int
    buy_id: int
    matched_quantity: int
    buy_cost: int
    sell_value: int
    buy_brokerage_alloc: int
    sell_brokerage_alloc: int
    realized_pnl: int


def allocate_brokerage(total_brokerage: int, total_quantity: int, match_quantities: list[int]) -> list[int]:
    """
    Allocate total_brokerage (int, paise) across match_quantities (list of int),
    using explicit proportional allocation:
        allocation = (total_brokerage * qty) // total_quantity
    Any remainder paise is assigned to the last match (FIFO order).
    Asserts sum(match_quantities) == total_quantity.
    Returns a list of allocated brokerage (int, paise) for each match.
    """
    match_sum = sum(match_quantities)
    if match_sum != total_quantity:
        raise PnlCalculationError(
            f"\n{'='*60}\n"
            f"BROKERAGE ALLOCATION ERROR\n"
            f"{'='*60}\n"
            f"Sum of match quantities: {match_sum}\n"
            f"Expected trade quantity: {total_quantity}\n"
            f"Difference: {abs(match_sum - total_quantity)}\n"
            f"\n💡 This indicates a mismatch in FIFO matching logic.\n"
            f"The matched quantities don't add up to the trade quantity.\n"
            f"{'='*60}"
        )
    
    if total_quantity <= 0:
        raise PnlCalculationError(
            f"Invalid trade quantity: {total_quantity}. Quantity must be positive."
        )
    
    allocations: list[int] = [
        (total_brokerage * qty) // total_quantity
        for qty in match_quantities
    ]
    allocated: int = sum(allocations)
    remainder: int = total_brokerage - allocated
    if allocations:
        allocations[-1] += remainder  # Assign remainder to last match (FIFO order)
    return allocations

def calculate_match_pnl(matches: list[MatchRecord], trades_by_id: dict[int, TradeDict]) -> list[PnlResult]:
    """
    For each match, compute cost basis, sell value, allocated brokerages, and realized P/L.
    matches: list of dicts {sell_id, buy_id, matched_quantity}
    trades_by_id: dict of trade_id -> trade dict (with price, brokerage, quantity, etc., all in paise)
    Returns: list of dicts with detailed P&L breakdown per match
    Raises PnlCalculationError if any buy_id or sell_id is missing from trades_by_id.
    """
    from collections import defaultdict
    
    # Validate all trade IDs exist
    missing_buys: list[int] = []
    missing_sells: list[int] = []
    
    for match in matches:
        if match['buy_id'] not in trades_by_id:
            missing_buys.append(match['buy_id'])
        if match['sell_id'] not in trades_by_id:
            missing_sells.append(match['sell_id'])
    
    if missing_buys or missing_sells:
        error_msg = f"\n{'='*60}\nMISSING TRADE DATA\n{'='*60}\n"
        if missing_buys:
            error_msg += f"Missing BUY trade IDs: {', '.join(map(str, set(missing_buys)))}\n"
        if missing_sells:
            error_msg += f"Missing SELL trade IDs: {', '.join(map(str, set(missing_sells)))}\n"
        error_msg += (
            f"\n💡 Suggestions:\n"
            f"  1. Verify all trades exist in the database\n"
            f"  2. Check if trades were deleted or marked inactive\n"
            f"  3. Ensure FIFO matcher returned valid trade IDs\n"
            f"{'='*60}"
        )
        raise PnlCalculationError(error_msg)
    
    # Group matches by buy_id and sell_id for brokerage allocation
    buy_matches: defaultdict[int, list[int]] = defaultdict(list)
    sell_matches: defaultdict[int, list[int]] = defaultdict(list)
    for match in matches:
        buy_matches[match['buy_id']].append(match['matched_quantity'])
        sell_matches[match['sell_id']].append(match['matched_quantity'])
    # Precompute brokerage allocations for all matches
    buy_brokerage_allocs: dict[int, list[int]] = {}
    for buy_id, qtys in buy_matches.items():
        trade: TradeDict = trades_by_id[buy_id]
        allocs: list[int] = allocate_brokerage(trade['brokerage'], sum(qtys), qtys)  # Only allocate to matched portion
        buy_brokerage_allocs[buy_id] = allocs
    sell_brokerage_allocs: dict[int, list[int]] = {}
    for sell_id, qtys in sell_matches.items():
        trade: TradeDict = trades_by_id[sell_id]
        allocs: list[int] = allocate_brokerage(trade['brokerage'], trade['quantity'], qtys)  # Allocate full SELL brokerage
        sell_brokerage_allocs[sell_id] = allocs
    # Now build per-match P&L
    buy_alloc_idx: defaultdict[int, int] = defaultdict(int)
    sell_alloc_idx: defaultdict[int, int] = defaultdict(int)
    results: list[PnlResult] = []
    for match in matches:
        sell_id: int = match['sell_id']
        buy_id: int = match['buy_id']
        qty: int = match['matched_quantity']
        buy: TradeDict = trades_by_id[buy_id]
        sell: TradeDict = trades_by_id[sell_id]
        buy_cost: int = qty * buy['price']
        sell_value: int = qty * sell['price']
        # Get correct allocation for this match
        buy_alloc: int = buy_brokerage_allocs[buy_id][buy_alloc_idx[buy_id]]
        sell_alloc: int = sell_brokerage_allocs[sell_id][sell_alloc_idx[sell_id]]
        buy_alloc_idx[buy_id] += 1
        sell_alloc_idx[sell_id] += 1
        realized_pnl: int = sell_value - buy_cost - buy_alloc - sell_alloc
        results.append(PnlResult(
            sell_id=sell_id,
            buy_id=buy_id,
            matched_quantity=qty,
            buy_cost=buy_cost,
            sell_value=sell_value,
            buy_brokerage_alloc=buy_alloc,
            sell_brokerage_alloc=sell_alloc,
            realized_pnl=realized_pnl
        ))
    return results

# Manual unit tests for allocate_brokerage
if __name__ == '__main__':
    print("Testing allocate_brokerage...")
    # Test 1: Even split
    print(allocate_brokerage(100, 10, [5, 5]))  # [50, 50]
    # Test 2: Uneven split
    print(allocate_brokerage(10, 3, [1, 1, 1]))  # [3, 3, 4]
    # Test 3: Single match
    print(allocate_brokerage(7, 7, [7]))  # [7]
    # Test 4: Remainder to last
    print(allocate_brokerage(11, 3, [1, 2]))  # [3, 8]
    # Test 5: Assertion error
    try:
        print(allocate_brokerage(10, 3, [1, 1]))  # Should raise
    except PnlCalculationError as e:
        print("Assertion caught as expected:", e)

    print("\nTesting realized P/L sum invariant...")
    # Example trades and matches
    # All values in paise
    trades_by_id: dict[int, TradeDict] = {
        1: TradeDict(
            id=1, trade_date='2026-01-15', equity='TCS', trade_type='BUY',
            type1='delivery', type2=None, strike=None, expiry=None,
            quantity=10, price=1000, brokerage=10, notes='', is_active=1
        ),
        2: TradeDict(
            id=2, trade_date='2026-01-15', equity='TCS', trade_type='SELL',
            type1='delivery', type2=None, strike=None, expiry=None,
            quantity=6, price=1200, brokerage=6, notes='', is_active=1
        ),
    }
    # SELL 2 matches BUY 1 in two lots: 4 and 2
    matches: list[MatchRecord] = [
        MatchRecord(sell_id=2, buy_id=1, matched_quantity=4, equity='TCS'),
        MatchRecord(sell_id=2, buy_id=1, matched_quantity=2, equity='TCS'),
    ]
    # Calculate per-match P/L
    match_results: list[PnlResult] = calculate_match_pnl(matches, trades_by_id)
    # Sum realized_pnl for SELL 2
    total_realized_pnl: int = sum(m['realized_pnl'] for m in match_results if m['sell_id'] == 2)
    # Direct calculation for SELL 2 (all 6 shares)
    buy_cost: int = 6 * trades_by_id[1]['price']
    sell_value: int = 6 * trades_by_id[2]['price']
    buy_brokerage: int = trades_by_id[1]['brokerage']
    sell_brokerage: int = trades_by_id[2]['brokerage']
    direct_realized_pnl: int = sell_value - buy_cost - buy_brokerage - sell_brokerage
    print(f"Sum of realized_pnl for SELL 2: {total_realized_pnl}")
    print(f"Direct realized P/L for SELL 2: {direct_realized_pnl}")
    assert total_realized_pnl == direct_realized_pnl, "Invariant failed: per-match sum != direct SELL P/L"
    print("Invariant holds: per-match sum equals direct SELL realized P/L.")
