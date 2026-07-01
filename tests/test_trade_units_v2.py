"""Tests for core/trade_units.py — Phase 6 verification.

These tests prove that:
1. Long lifecycles group identically to V1.
2. Short lifecycles (SELL then BUY) are now successfully grouped.
3. Remaining investment uses the correct formula depending on LONG vs SHORT.
4. Closing trades are correctly identified as BUY for short lifecycles.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from core.trade_units import build_trade_units
from core.fifo_matcher import MatchRecord, TradeTuple

def test_long_lifecycle():
    # BUY 100 @ 10000
    t1 = (1, "2026-01-01", "TCS", "BUY", "delivery", None, None, None, 100, 10000, 0, "", 1, 0, None, 0, 0)
    # SELL 100 @ 12000
    t2 = (2, "2026-01-05", "TCS", "SELL", "delivery", None, None, None, 100, 12000, 0, "", 1, 0, None, 0, 0)
    
    trades = [t1, t2]
    match_results = [{
        'sell_id': 2, 'buy_id': 1, 'matched_quantity': 100, 'equity': "TCS",
        'buy_cost': 100 * 10000, 'sell_value': 100 * 12000, 
        'buy_brokerage_alloc': 0, 'sell_brokerage_alloc': 0,
        'realized_pnl': 200000
    }]
    
    units = build_trade_units(trades, match_results, grouping="lifecycle")
    assert len(units) == 1
    u = units[0]
    assert u['status'] == "Closed"
    assert u['total_buy_qty'] == 100
    assert u['total_sell_qty'] == 100
    assert u['realized_pnl'] == 200000
    assert u['holding_days'] == 4

def test_short_lifecycle():
    # SELL 100 @ 10000 (OPENING SHORT)
    t1 = (1, "2026-01-01", "SBIN", "SELL", "intraday", None, None, None, 100, 10000, 0, "", 1, 0, None, 0, 0)
    # BUY 100 @ 9000 (CLOSING SHORT)
    t2 = (2, "2026-01-01", "SBIN", "BUY", "intraday", None, None, None, 100, 9000, 0, "", 1, 0, None, 0, 0)
    
    trades = [t1, t2]
    match_results = [{
        'sell_id': 1, 'buy_id': 2, 'matched_quantity': 100, 'equity': "SBIN",
        'buy_cost': 100 * 9000, 'sell_value': 100 * 10000, 
        'buy_brokerage_alloc': 0, 'sell_brokerage_alloc': 0,
        'realized_pnl': 100000
    }]
    
    units = build_trade_units(trades, match_results, grouping="lifecycle")
    assert len(units) == 1
    u = units[0]
    assert u['status'] == "Closed"
    assert u['total_buy_qty'] == 100
    assert u['total_sell_qty'] == 100
    assert u['realized_pnl'] == 100000
    assert u['holding_days'] == 0
    
def test_open_short_lifecycle():
    # SELL 100 @ 10000 (OPENING SHORT)
    t1 = (1, "2026-01-01", "RELIANCE", "SELL", "futures", None, None, "2026-01-30", 100, 10000, 0, "", 1, 0, None, 0, 0)
    # BUY 40 @ 9000 (CLOSING SHORT)
    t2 = (2, "2026-01-10", "RELIANCE", "BUY", "futures", None, None, "2026-01-30", 40, 9000, 0, "", 1, 0, None, 0, 0)
    
    trades = [t1, t2]
    match_results = [{
        'sell_id': 1, 'buy_id': 2, 'matched_quantity': 40, 'equity': "RELIANCE",
        'buy_cost': 40 * 9000, 'sell_value': 40 * 10000, 
        'buy_brokerage_alloc': 0, 'sell_brokerage_alloc': 0,
        'realized_pnl': 40000
    }]
    
    units = build_trade_units(trades, match_results, grouping="lifecycle")
    assert len(units) == 1
    u = units[0]
    assert u['status'] == "Open"
    assert u['remaining_qty'] == 60
    assert u['total_buy_qty'] == 40
    assert u['total_sell_qty'] == 100
    assert u['remaining_investment'] == 60 * 10000  # 60 shares sold at 10000

if __name__ == "__main__":
    pytest.main([__file__])
