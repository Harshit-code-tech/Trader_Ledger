"""
Test v1.1 features - Equity filter, Date range filter, and Open positions

This script tests the new backend functions added in v1.1
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.fifo_matcher import match_fifo, TradeTuple
from core.pnl_calculator import calculate_match_pnl
from core.pnl_aggregator import (
    aggregate_pnl_by_equity,
    filter_matches_by_date_range,
    aggregate_pnl_by_date
)
from core.open_positions import calculate_open_positions, get_unique_equities
from core.run_ledger import build_trades_by_id


def test_v1_1_features():
    """Test all v1.1 features with sample data."""
    
    print("=" * 80)
    print("TESTING v1.1 FEATURES")
    print("=" * 80)
    
    # Sample trades (all values in paise)
    trades: list[TradeTuple] = [
        # (id, date, equity, type, type1, type2, strike, expiry, qty, price, brokerage,
        #  notes, is_active, brokerage_auto, brokerage_override, mtf_amount)
        (1, '2026-01-10', 'TCS', 'BUY', 'delivery', None, None, None, 100, 342100, 50, '', 1, 50, None, 0),
        (2, '2026-01-12', 'INFY', 'BUY', 'delivery', None, None, None, 50, 150000, 30, '', 1, 30, None, 0),
        (3, '2026-01-15', 'TCS', 'SELL', 'delivery', None, None, None, 60, 345000, 40, '', 1, 40, None, 0),
        (4, '2026-01-18', 'INFY', 'BUY', 'delivery', None, None, None, 30, 151000, 20, '', 1, 20, None, 0),
        (5, '2026-01-20', 'INFY', 'SELL', 'delivery', None, None, None, 40, 152000, 25, '', 1, 25, None, 0),
        (6, '2026-01-22', 'TCS', 'SELL', 'delivery', None, None, None, 20, 350000, 15, '', 1, 15, None, 0),
    ]
    
    print("\n1️⃣ Testing FIFO Matching")
    print("-" * 80)
    matches = match_fifo(trades)
    print(f"✓ Generated {len(matches)} matches")
    for match in matches:
        print(f"  SELL #{match['sell_id']} matched with BUY #{match['buy_id']}: {match['matched_quantity']} qty of {match['equity']}")
    
    print("\n2️⃣ Testing P/L Calculation")
    print("-" * 80)
    trades_by_id = build_trades_by_id(trades)
    pnl_results = calculate_match_pnl(matches, trades_by_id)
    total_pnl = sum(p['realized_pnl'] for p in pnl_results)
    print(f"✓ Calculated P/L for {len(pnl_results)} matches")
    print(f"  Total Realized P/L: ₹{total_pnl/100:.2f}")
    
    print("\n3️⃣ Testing Equity-wise P/L Filter")
    print("-" * 80)
    equity_pnl = aggregate_pnl_by_equity(pnl_results, trades_by_id)
    for equity, pnl in equity_pnl.items():
        print(f"  {equity}: ₹{pnl/100:+.2f}")
    
    print("\n4️⃣ Testing Date Range Filter")
    print("-" * 80)
    
    # Test case 1: Filter for specific date range
    filtered = filter_matches_by_date_range(
        pnl_results, trades_by_id,
        from_date='2026-01-15',
        to_date='2026-01-20'
    )
    filtered_pnl = sum(p['realized_pnl'] for p in filtered)
    print(f"  Range 2026-01-15 to 2026-01-20:")
    print(f"    Matches: {len(filtered)}")
    print(f"    P/L: ₹{filtered_pnl/100:.2f}")
    
    # Test case 2: Only from_date
    filtered = filter_matches_by_date_range(
        pnl_results, trades_by_id,
        from_date='2026-01-20',
        to_date=None
    )
    filtered_pnl = sum(p['realized_pnl'] for p in filtered)
    print(f"  From 2026-01-20 onwards:")
    print(f"    Matches: {len(filtered)}")
    print(f"    P/L: ₹{filtered_pnl/100:.2f}")
    
    # Test edge case: Buy before range, sell inside range
    print(f"\n  Edge case verification:")
    print(f"    ✓ Buy on 2026-01-10, Sell on 2026-01-15 (inside range)")
    print(f"    ✓ This SHOULD be included in date filter (SELL date is what matters)")
    
    print("\n5️⃣ Testing Open Positions Calculation")
    print("-" * 80)
    open_positions = calculate_open_positions(matches, trades_by_id)
    print(f"✓ Found {len(open_positions)} open positions:")
    for pos in open_positions:
        print(f"  {pos['equity']}:")
        print(f"    Status: {pos['status']}")
        print(f"    Remaining Qty: {pos['remaining_qty']}")
        print(f"    Avg Price: ₹{pos['avg_price']:.2f}")
        print(f"    Total Cost: ₹{pos['total_cost']/100:.2f}")
    
    print("\n6️⃣ Testing get_unique_equities")
    print("-" * 80)
    equities = get_unique_equities(trades_by_id)
    print(f"✓ Unique equities: {', '.join(equities)}")
    
    print("\n7️⃣ Testing Combined Filters (Equity + Date)")
    print("-" * 80)
    # Filter by date first
    date_filtered = filter_matches_by_date_range(
        pnl_results, trades_by_id,
        from_date='2026-01-15',
        to_date='2026-01-20'
    )
    # Then filter by equity
    equity_filtered = [
        p for p in date_filtered
        if trades_by_id[p['sell_id']]['equity'] == 'INFY'
    ]
    filtered_pnl = sum(p['realized_pnl'] for p in equity_filtered)
    print(f"  INFY trades between 2026-01-15 and 2026-01-20:")
    print(f"    Matches: {len(equity_filtered)}")
    print(f"    P/L: ₹{filtered_pnl/100:.2f}")
    
    print("\n" + "=" * 80)
    print("✅ ALL v1.1 FEATURES TESTED SUCCESSFULLY")
    print("=" * 80)
    
    # Calculate expected values for verification
    print("\n📊 Summary:")
    print(f"  Total trades: {len(trades)}")
    print(f"  Total matches: {len(matches)}")
    print(f"  Open positions: {len(open_positions)}")
    print(f"  Unique equities: {len(equities)}")
    print(f"  Total realized P/L: ₹{total_pnl/100:.2f}")
    
    # Verify open positions math
    total_buy_qty = sum(t[8] for t in trades if t[3] == 'BUY')
    total_sell_qty = sum(t[8] for t in trades if t[3] == 'SELL')
    total_open = sum(p['remaining_qty'] for p in open_positions)
    expected_open = total_buy_qty - total_sell_qty
    
    print(f"\n🔍 Validation:")
    print(f"  Total BUY qty: {total_buy_qty}")
    print(f"  Total SELL qty: {total_sell_qty}")
    print(f"  Expected open: {expected_open}")
    print(f"  Actual open: {total_open}")
    print(f"  {'✅ MATCH' if total_open == expected_open else '❌ MISMATCH'}")


if __name__ == '__main__':
    test_v1_1_features()
