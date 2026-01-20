class PnlCalculationError(Exception):
    pass

def allocate_brokerage(total_brokerage, total_quantity, match_quantities):
    """
    Allocate total_brokerage (int, paise) across match_quantities (list of int),
    using explicit proportional allocation:
        allocation = (total_brokerage * qty) // total_quantity
    Any remainder paise is assigned to the last match (FIFO order).
    Asserts sum(match_quantities) == total_quantity.
    Returns a list of allocated brokerage (int, paise) for each match.
    """
    if sum(match_quantities) != total_quantity:
        raise PnlCalculationError(f"Sum of match quantities ({sum(match_quantities)}) does not equal trade quantity ({total_quantity})")
    allocations = [
        (total_brokerage * qty) // total_quantity
        for qty in match_quantities
    ]
    allocated = sum(allocations)
    remainder = total_brokerage - allocated
    if allocations:
        allocations[-1] += remainder  # Assign remainder to last match (FIFO order)
    return allocations

def calculate_match_pnl(matches, trades_by_id):
    """
    For each match, compute cost basis, sell value, allocated brokerages, and realized P/L.
    matches: list of dicts {sell_id, buy_id, matched_quantity}
    trades_by_id: dict of trade_id -> trade dict (with price, brokerage, quantity, etc., all in paise)
    Returns: list of dicts with detailed P&L breakdown per match
    Raises PnlCalculationError if any buy_id or sell_id is missing from trades_by_id.
    """
    from collections import defaultdict
    # Check all buy_id and sell_id exist in trades_by_id
    for match in matches:
        if match['buy_id'] not in trades_by_id:
            raise PnlCalculationError(f"BUY trade_id {match['buy_id']} not found in trades_by_id.")
        if match['sell_id'] not in trades_by_id:
            raise PnlCalculationError(f"SELL trade_id {match['sell_id']} not found in trades_by_id.")
    # Group matches by buy_id and sell_id for brokerage allocation
    buy_matches = defaultdict(list)
    sell_matches = defaultdict(list)
    for match in matches:
        buy_matches[match['buy_id']].append(match['matched_quantity'])
        sell_matches[match['sell_id']].append(match['matched_quantity'])
    # Precompute brokerage allocations for all matches
    buy_brokerage_allocs = {}
    for buy_id, qtys in buy_matches.items():
        trade = trades_by_id[buy_id]
        allocs = allocate_brokerage(trade['brokerage'], sum(qtys), qtys)  # Only allocate to matched portion
        buy_brokerage_allocs[buy_id] = allocs
    sell_brokerage_allocs = {}
    for sell_id, qtys in sell_matches.items():
        trade = trades_by_id[sell_id]
        allocs = allocate_brokerage(trade['brokerage'], trade['quantity'], qtys)  # Allocate full SELL brokerage
        sell_brokerage_allocs[sell_id] = allocs
    # Now build per-match P&L
    buy_alloc_idx = defaultdict(int)
    sell_alloc_idx = defaultdict(int)
    results = []
    for match in matches:
        sell_id = match['sell_id']
        buy_id = match['buy_id']
        qty = match['matched_quantity']
        buy = trades_by_id[buy_id]
        sell = trades_by_id[sell_id]
        buy_cost = qty * buy['price']
        sell_value = qty * sell['price']
        # Get correct allocation for this match
        buy_alloc = buy_brokerage_allocs[buy_id][buy_alloc_idx[buy_id]]
        sell_alloc = sell_brokerage_allocs[sell_id][sell_alloc_idx[sell_id]]
        buy_alloc_idx[buy_id] += 1
        sell_alloc_idx[sell_id] += 1
        realized_pnl = sell_value - buy_cost - buy_alloc - sell_alloc
        results.append({
            'sell_id': sell_id,
            'buy_id': buy_id,
            'matched_quantity': qty,
            'buy_cost': buy_cost,
            'sell_value': sell_value,
            'buy_brokerage_alloc': buy_alloc,
            'sell_brokerage_alloc': sell_alloc,
            'realized_pnl': realized_pnl
        })
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
    trades_by_id = {
        1: {'id': 1, 'price': 1000, 'brokerage': 10, 'quantity': 10},  # BUY
        2: {'id': 2, 'price': 1200, 'brokerage': 6, 'quantity': 6},    # SELL
    }
    # SELL 2 matches BUY 1 in two lots: 4 and 2
    matches = [
        {'sell_id': 2, 'buy_id': 1, 'matched_quantity': 4},
        {'sell_id': 2, 'buy_id': 1, 'matched_quantity': 2},
    ]
    # Calculate per-match P/L
    match_results = calculate_match_pnl(matches, trades_by_id)
    # Sum realized_pnl for SELL 2
    total_realized_pnl = sum(m['realized_pnl'] for m in match_results if m['sell_id'] == 2)
    # Direct calculation for SELL 2 (all 6 shares)
    buy_cost = 6 * trades_by_id[1]['price']
    sell_value = 6 * trades_by_id[2]['price']
    buy_brokerage = trades_by_id[1]['brokerage']
    sell_brokerage = trades_by_id[2]['brokerage']
    direct_realized_pnl = sell_value - buy_cost - buy_brokerage - sell_brokerage
    print(f"Sum of realized_pnl for SELL 2: {total_realized_pnl}")
    print(f"Direct realized P/L for SELL 2: {direct_realized_pnl}")
    assert total_realized_pnl == direct_realized_pnl, "Invariant failed: per-match sum != direct SELL P/L"
    print("Invariant holds: per-match sum equals direct SELL realized P/L.")
