"""Tests for core/open_positions.py — Phase 5 verification.

These tests prove that:
1. LONG open positions are calculated correctly (identical to V1).
2. SHORT open positions are now calculated correctly.
3. Unrealized PnL handles both LONG and SHORT formulas properly.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from core.open_positions import calculate_open_positions
from core.fifo_matcher import MatchRecord

def test_long_open_position():
    trades_by_id = {
        1: {
            'id': 1, 'trade_date': "2026-01-01", 'equity': "TCS", 'trade_type': "BUY",
            'type1': "delivery", 'type2': None, 'strike': None, 'expiry': None,
            'quantity': 100, 'price': 10000, 'brokerage': 0, 'brokerage_auto': 0,
            'brokerage_override': None, 'mtf_amount': 0, 'notes': "", 'is_active': 1
        }
    }
    matches = []
    market_prices = {"TCS": 12000}

    results = calculate_open_positions(matches, trades_by_id, market_prices)
    assert len(results) == 1
    pos = results[0]
    assert pos['equity'] == "TCS"
    assert pos['status'] == "OPEN"
    assert pos['position_side'] == "LONG"
    assert pos['remaining_qty'] == 100
    assert pos['avg_price'] == 100.0
    assert pos['unrealized_pnl'] == (100 * 12000) - (100 * 10000)  # +20000

def test_short_open_position():
    trades_by_id = {
        1: {
            'id': 1, 'trade_date': "2026-01-01", 'equity': "SBIN", 'trade_type': "SELL",
            'type1': "intraday", 'type2': None, 'strike': None, 'expiry': None,
            'quantity': 100, 'price': 10000, 'brokerage': 0, 'brokerage_auto': 0,
            'brokerage_override': None, 'mtf_amount': 0, 'notes': "", 'is_active': 1
        }
    }
    matches = []
    market_prices = {"SBIN": 9000}

    results = calculate_open_positions(matches, trades_by_id, market_prices)
    assert len(results) == 1
    pos = results[0]
    assert pos['equity'] == "SBIN"
    assert pos['position_side'] == "SHORT"
    assert pos['remaining_qty'] == 100
    assert pos['avg_price'] == 100.0
    # Sold at 10000, current price is 9000. Profit = 1000 * 100 = 100,000 paise
    assert pos['unrealized_pnl'] == (100 * 10000) - (100 * 9000)  # +100000

def test_partial_match_long():
    trades_by_id = {
        1: {
            'id': 1, 'trade_date': "2026-01-01", 'equity': "TCS", 'trade_type': "BUY",
            'type1': "delivery", 'type2': None, 'strike': None, 'expiry': None,
            'quantity': 100, 'price': 10000, 'brokerage': 0, 'brokerage_auto': 0,
            'brokerage_override': None, 'mtf_amount': 0, 'notes': "", 'is_active': 1
        },
        2: {
            'id': 2, 'trade_date': "2026-01-10", 'equity': "TCS", 'trade_type': "SELL",
            'type1': "delivery", 'type2': None, 'strike': None, 'expiry': None,
            'quantity': 40, 'price': 12000, 'brokerage': 0, 'brokerage_auto': 0,
            'brokerage_override': None, 'mtf_amount': 0, 'notes': "", 'is_active': 1
        }
    }
    matches = [MatchRecord(sell_id=2, buy_id=1, matched_quantity=40, equity="TCS")]
    
    results = calculate_open_positions(matches, trades_by_id)
    assert len(results) == 1
    pos = results[0]
    assert pos['position_side'] == "LONG"
    assert pos['remaining_qty'] == 60
    assert pos['total_cost'] == 60 * 10000

def test_partial_match_short():
    trades_by_id = {
        1: {
            'id': 1, 'trade_date': "2026-01-01", 'equity': "SBIN", 'trade_type': "SELL",
            'type1': "intraday", 'type2': None, 'strike': None, 'expiry': None,
            'quantity': 100, 'price': 10000, 'brokerage': 0, 'brokerage_auto': 0,
            'brokerage_override': None, 'mtf_amount': 0, 'notes': "", 'is_active': 1
        },
        2: {
            'id': 2, 'trade_date': "2026-01-01", 'equity': "SBIN", 'trade_type': "BUY",
            'type1': "intraday", 'type2': None, 'strike': None, 'expiry': None,
            'quantity': 40, 'price': 9000, 'brokerage': 0, 'brokerage_auto': 0,
            'brokerage_override': None, 'mtf_amount': 0, 'notes': "", 'is_active': 1
        }
    }
    matches = [MatchRecord(sell_id=1, buy_id=2, matched_quantity=40, equity="SBIN")]
    
    results = calculate_open_positions(matches, trades_by_id)
    assert len(results) == 1
    pos = results[0]
    assert pos['position_side'] == "SHORT"
    assert pos['remaining_qty'] == 60
    assert pos['total_cost'] == 60 * 10000

if __name__ == "__main__":
    pytest.main([__file__])
