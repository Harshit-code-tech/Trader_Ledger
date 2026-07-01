"""Quick test for position flip logic in the Position State Engine."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.position_state_engine import process_trades, PositionStateError, NormalizedTradeEvent
from core.trading_rules import EventRole, PositionSide

# TradeTuple is a plain tuple:
# (id, trade_date, equity, trade_type, type1, type2, strike, expiry,
#  quantity, price, brokerage, notes, is_active, brokerage_auto,
#  brokerage_override, mtf_amount, mtf_rate_ppm)

def make_trade(id, date, equity, trade_type, type1, qty, price=10000):
    return (id, date, equity, trade_type, type1, None, None, None,
            qty, price, 0, '', 1, 0, None, 0, None)

def test_intraday_flip():
    """LONG 78, SELL 32532 -> should split into CLOSING(78) + OPENING(32454)"""
    trades = [
        make_trade(1, '2026-07-01', 'FAGA', 'BUY', 'intraday', 33),
        make_trade(2, '2026-07-01', 'FAGA', 'BUY', 'intraday', 23),
        make_trade(3, '2026-07-01', 'FAGA', 'BUY', 'intraday', 32),
        make_trade(4, '2026-07-01', 'FAGA', 'SELL', 'intraday', 33),
        make_trade(5, '2026-07-01', 'FAGA', 'BUY', 'intraday', 23),
        make_trade(6, '2026-07-01', 'FAGA', 'SELL', 'intraday', 32532),
        make_trade(7, '2026-07-01', 'FAGA', 'BUY', 'intraday', 31242),
        make_trade(8, '2026-07-01', 'FAGA', 'BUY', 'intraday', 1233),
        make_trade(9, '2026-07-01', 'FAGA', 'BUY', 'intraday', 1231),
    ]
    
    events = process_trades(trades)
    
    trade6_events = [e for e in events if e.trade_id == 6]
    assert len(trade6_events) == 2, f"Expected 2 events for trade 6, got {len(trade6_events)}"
    
    closing_event = trade6_events[0]
    opening_event = trade6_events[1]
    
    assert closing_event.event_role == EventRole.CLOSING
    assert closing_event.quantity == 78, f"CLOSING qty should be 78, got {closing_event.quantity}"
    assert closing_event.position_side == PositionSide.LONG
    
    assert opening_event.event_role == EventRole.OPENING
    assert opening_event.quantity == 32454, f"OPENING qty should be 32454, got {opening_event.quantity}"
    assert opening_event.position_side == PositionSide.SHORT
    
    print("PASS test_intraday_flip")

def test_delivery_flip_blocked():
    """Delivery: LONG 10, SELL 20 -> should FAIL"""
    trades = [
        make_trade(1, '2026-01-01', 'TCS', 'BUY', 'delivery', 10),
        make_trade(2, '2026-01-02', 'TCS', 'SELL', 'delivery', 20),
    ]
    try:
        process_trades(trades)
        print("FAIL test_delivery_flip_blocked - should have raised")
    except PositionStateError:
        print("PASS test_delivery_flip_blocked")

def test_short_flip():
    """SHORT 50, BUY 200 -> split into CLOSING(50) + OPENING(150) LONG"""
    trades = [
        make_trade(1, '2026-01-01', 'NIFTY', 'SELL', 'intraday', 50),
        make_trade(2, '2026-01-01', 'NIFTY', 'BUY', 'intraday', 200),
    ]
    events = process_trades(trades)
    
    trade2_events = [e for e in events if e.trade_id == 2]
    assert len(trade2_events) == 2, f"Expected 2, got {len(trade2_events)}"
    assert trade2_events[0].event_role == EventRole.CLOSING
    assert trade2_events[0].quantity == 50
    assert trade2_events[1].event_role == EventRole.OPENING
    assert trade2_events[1].quantity == 150
    
    print("PASS test_short_flip")

def test_existing_delivery_unchanged():
    """Delivery BUY then SELL - no flip, should work identically."""
    trades = [
        make_trade(1, '2026-01-01', 'TCS', 'BUY', 'delivery', 100),
        make_trade(2, '2026-01-15', 'TCS', 'SELL', 'delivery', 60),
    ]
    events = process_trades(trades)
    assert len(events) == 2
    assert events[0].event_role == EventRole.OPENING
    assert events[0].quantity == 100
    assert events[1].event_role == EventRole.CLOSING
    assert events[1].quantity == 60
    
    print("PASS test_existing_delivery_unchanged")

def test_exact_close_no_flip():
    """LONG 100, SELL 100 -> exact close, no flip."""
    trades = [
        make_trade(1, '2026-01-01', 'TCS', 'BUY', 'intraday', 100),
        make_trade(2, '2026-01-01', 'TCS', 'SELL', 'intraday', 100),
    ]
    events = process_trades(trades)
    trade2_events = [e for e in events if e.trade_id == 2]
    assert len(trade2_events) == 1, f"Exact close should be 1 event, got {len(trade2_events)}"
    assert trade2_events[0].event_role == EventRole.CLOSING
    assert trade2_events[0].quantity == 100
    
    print("PASS test_exact_close_no_flip")

if __name__ == '__main__':
    test_intraday_flip()
    test_delivery_flip_blocked()
    test_short_flip()
    test_existing_delivery_unchanged()
    test_exact_close_no_flip()
    print("\nAll position flip tests passed!")
