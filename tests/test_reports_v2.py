"""Tests for core/pnl_aggregator.py and core/analytics_engine.py — Phase 7 verification.

These tests prove that:
1. Long lifecycles aggregate PnL to the SELL date (which is the closing date).
2. Short lifecycles aggregate PnL to the BUY date (which is the closing date).
3. Analytics correctly compute holding days natively using abs().
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from core.pnl_aggregator import aggregate_pnl_by_date, aggregate_pnl_by_closing_trade, filter_matches_by_date_range
from core.analytics_engine import calculate_advanced_metrics

def test_long_aggregation():
    # BUY on Jan 1, SELL on Jan 5
    trades_by_id = {
        1: {'id': 1, 'trade_date': '2026-01-01', 'equity': 'TCS', 'trade_type': 'BUY'},
        2: {'id': 2, 'trade_date': '2026-01-05', 'equity': 'TCS', 'trade_type': 'SELL'}
    }
    match_results = [{
        'sell_id': 2, 'buy_id': 1, 'matched_quantity': 10, 'realized_pnl': 500,
        'buy_cost': 1000, 'sell_value': 1500
    }]
    
    date_totals = aggregate_pnl_by_date(match_results, trades_by_id)
    assert date_totals == {'2026-01-05': 500}
    
    closing_totals = aggregate_pnl_by_closing_trade(match_results, trades_by_id)
    assert closing_totals == {2: 500}

def test_short_aggregation():
    # SELL on Jan 1, BUY on Jan 10
    trades_by_id = {
        1: {'id': 1, 'trade_date': '2026-01-01', 'equity': 'SBIN', 'trade_type': 'SELL'},
        2: {'id': 2, 'trade_date': '2026-01-10', 'equity': 'SBIN', 'trade_type': 'BUY'}
    }
    match_results = [{
        'sell_id': 1, 'buy_id': 2, 'matched_quantity': 10, 'realized_pnl': 200,
        'buy_cost': 800, 'sell_value': 1000
    }]
    
    date_totals = aggregate_pnl_by_date(match_results, trades_by_id)
    # PnL realized on Jan 10 (closing date)
    assert date_totals == {'2026-01-10': 200}
    
    closing_totals = aggregate_pnl_by_closing_trade(match_results, trades_by_id)
    assert closing_totals == {2: 200}
    
    # Check date filtering
    assert len(filter_matches_by_date_range(match_results, trades_by_id, from_date='2026-01-05')) == 1
    assert len(filter_matches_by_date_range(match_results, trades_by_id, to_date='2026-01-05')) == 0

def test_analytics_engine():
    trades_by_id = {
        1: {'id': 1, 'trade_date': '2026-01-01', 'equity': 'RELIANCE', 'trade_type': 'SELL'},
        2: {'id': 2, 'trade_date': '2026-01-11', 'equity': 'RELIANCE', 'trade_type': 'BUY'}
    }
    match_results = [{
        'sell_id': 1, 'buy_id': 2, 'matched_quantity': 100, 'realized_pnl': 1000,
        'buy_cost': 9000, 'sell_value': 10000
    }]
    sell_totals = aggregate_pnl_by_closing_trade(match_results, trades_by_id)
    daily_pnl_totals = aggregate_pnl_by_date(match_results, trades_by_id)
    
    metrics = calculate_advanced_metrics(match_results, trades_by_id, sell_totals, daily_pnl_totals)
    assert metrics['win_rate'] == 100.0
    assert metrics['avg_holding_days'] == 10.0  # abs(11 days diff)

if __name__ == "__main__":
    pytest.main([__file__])
