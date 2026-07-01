"""Tests for core/position_state_engine.py — Phase 2 verification.

These tests prove that the Position State Engine correctly:
1. Classifies trades as OPENING/CLOSING based on position state.
2. Tracks net positions per contract independently.
3. Rejects invalid transitions (e.g. Delivery SELL on flat position).
4. Produces NormalizedTradeEvents that preserve all passthrough data.
5. For LONG-ONLY products (Delivery, MTF), behavior is identical to V1.

NO existing module is modified — only the new position_state_engine.py
and trading_rules.py are exercised.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest

from core.trading_rules import (
    TradeDirection,
    EventRole,
    PositionSide,
)
from core.position_state_engine import (
    NormalizedTradeEvent,
    PositionStateError,
    process_trades,
    get_net_positions,
)


# ---------------------------------------------------------------------------
# Helper to build TradeTuples from minimal data
# ---------------------------------------------------------------------------

def _make_trade(
    trade_id: int,
    trade_date: str,
    equity: str,
    trade_type: str,
    type1: str,
    quantity: int,
    price: int = 10000,
    type2=None,
    strike=None,
    expiry=None,
    brokerage=0,
    notes="",
    is_active=1,
    brokerage_auto=0,
    brokerage_override=None,
    mtf_amount=0,
    mtf_rate_ppm=None,
):
    """Build a TradeTuple matching the 17-field format."""
    return (
        trade_id, trade_date, equity, trade_type, type1, type2,
        strike, expiry, quantity, price, brokerage, notes, is_active,
        brokerage_auto, brokerage_override, mtf_amount, mtf_rate_ppm,
    )


# ===================================================================
# SECTION 1 — Delivery (long-only, V1 identical behaviour)
# ===================================================================

class TestDeliveryLongOnly:
    """Delivery: BUY opens, SELL closes.  Short selling prohibited."""

    def test_buy_opens_long(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
        ]
        events = process_trades(trades)
        assert len(events) == 1
        assert events[0].event_role is EventRole.OPENING
        assert events[0].position_side is PositionSide.LONG

    def test_sell_closes_long(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-10", "TCS", "SELL", "delivery", 100),
        ]
        events = process_trades(trades)
        assert events[0].event_role is EventRole.OPENING
        assert events[1].event_role is EventRole.CLOSING
        assert events[1].position_side is PositionSide.LONG

    def test_sell_on_flat_raises(self):
        """Delivery SELL with no prior BUY must be rejected."""
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "SELL", "delivery", 100),
        ]
        with pytest.raises(PositionStateError, match="INVALID TRADE TRANSITION"):
            process_trades(trades)

    def test_partial_sell(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-05", "TCS", "SELL", "delivery", 40),
        ]
        events = process_trades(trades)
        assert events[0].event_role is EventRole.OPENING
        assert events[1].event_role is EventRole.CLOSING
        assert events[1].quantity == 40

    def test_multiple_buys_then_sell(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-02", "TCS", "BUY", "delivery", 50),
            _make_trade(3, "2026-01-10", "TCS", "SELL", "delivery", 120),
        ]
        events = process_trades(trades)
        assert events[0].event_role is EventRole.OPENING
        assert events[1].event_role is EventRole.OPENING  # adding to long
        assert events[2].event_role is EventRole.CLOSING


# ===================================================================
# SECTION 2 — MTF (long-only, V1 identical behaviour)
# ===================================================================

class TestMtfLongOnly:
    """MTF: BUY opens, SELL closes.  Short selling prohibited."""

    def test_buy_opens(self):
        trades = [
            _make_trade(1, "2026-01-01", "INFY", "BUY", "mtf", 200,
                        mtf_amount=500000, mtf_rate_ppm=96500),
        ]
        events = process_trades(trades)
        assert events[0].event_role is EventRole.OPENING
        assert events[0].position_side is PositionSide.LONG

    def test_sell_closes(self):
        trades = [
            _make_trade(1, "2026-01-01", "INFY", "BUY", "mtf", 200,
                        mtf_amount=500000, mtf_rate_ppm=96500),
            _make_trade(2, "2026-01-15", "INFY", "SELL", "mtf", 200),
        ]
        events = process_trades(trades)
        assert events[1].event_role is EventRole.CLOSING
        assert events[1].position_side is PositionSide.LONG

    def test_sell_on_flat_raises(self):
        trades = [
            _make_trade(1, "2026-01-01", "INFY", "SELL", "mtf", 100),
        ]
        with pytest.raises(PositionStateError):
            process_trades(trades)

    def test_passthrough_mtf_fields(self):
        """Ensure MTF-specific fields are carried through to the event."""
        trades = [
            _make_trade(1, "2026-01-01", "INFY", "BUY", "mtf", 200,
                        mtf_amount=500000, mtf_rate_ppm=96500),
        ]
        events = process_trades(trades)
        assert events[0].mtf_amount == 500000
        assert events[0].mtf_rate_ppm == 96500


# ===================================================================
# SECTION 3 — Intraday (short selling allowed)
# ===================================================================

class TestIntradayShortSelling:
    """Intraday: BUY or SELL may open.  Opposite trade closes."""

    def test_sell_opens_short(self):
        trades = [
            _make_trade(1, "2026-01-01", "SBIN", "SELL", "intraday", 100),
        ]
        events = process_trades(trades)
        assert events[0].event_role is EventRole.OPENING
        assert events[0].position_side is PositionSide.SHORT

    def test_buy_closes_short(self):
        trades = [
            _make_trade(1, "2026-01-01", "SBIN", "SELL", "intraday", 100),
            _make_trade(2, "2026-01-01", "SBIN", "BUY", "intraday", 100),
        ]
        events = process_trades(trades)
        assert events[0].event_role is EventRole.OPENING
        assert events[0].position_side is PositionSide.SHORT
        assert events[1].event_role is EventRole.CLOSING
        assert events[1].position_side is PositionSide.SHORT

    def test_buy_opens_long(self):
        trades = [
            _make_trade(1, "2026-01-01", "SBIN", "BUY", "intraday", 50),
        ]
        events = process_trades(trades)
        assert events[0].event_role is EventRole.OPENING
        assert events[0].position_side is PositionSide.LONG

    def test_sell_closes_long(self):
        trades = [
            _make_trade(1, "2026-01-01", "SBIN", "BUY", "intraday", 50),
            _make_trade(2, "2026-01-01", "SBIN", "SELL", "intraday", 50),
        ]
        events = process_trades(trades)
        assert events[1].event_role is EventRole.CLOSING
        assert events[1].position_side is PositionSide.LONG


# ===================================================================
# SECTION 4 — Futures (short selling allowed, overnight)
# ===================================================================

class TestFuturesShortSelling:

    def test_sell_opens_short(self):
        trades = [
            _make_trade(1, "2026-01-01", "NIFTY", "SELL", "futures", 75,
                        expiry="2026-01-30"),
        ]
        events = process_trades(trades)
        assert events[0].event_role is EventRole.OPENING
        assert events[0].position_side is PositionSide.SHORT

    def test_buy_closes_short(self):
        trades = [
            _make_trade(1, "2026-01-01", "NIFTY", "SELL", "futures", 75,
                        expiry="2026-01-30"),
            _make_trade(2, "2026-01-15", "NIFTY", "BUY", "futures", 75,
                        expiry="2026-01-30"),
        ]
        events = process_trades(trades)
        assert events[1].event_role is EventRole.CLOSING

    def test_sell_adds_to_short(self):
        trades = [
            _make_trade(1, "2026-01-01", "NIFTY", "SELL", "futures", 75,
                        expiry="2026-01-30"),
            _make_trade(2, "2026-01-05", "NIFTY", "SELL", "futures", 25,
                        expiry="2026-01-30"),
        ]
        events = process_trades(trades)
        assert events[0].event_role is EventRole.OPENING
        assert events[1].event_role is EventRole.OPENING  # adds to short


# ===================================================================
# SECTION 5 — Options (short selling allowed)
# ===================================================================

class TestOptionsShortSelling:

    def test_sell_opens_short(self):
        trades = [
            _make_trade(1, "2026-01-01", "NIFTY", "SELL", "options", 50,
                        type2="CE", strike=22000.0, expiry="2026-01-30"),
        ]
        events = process_trades(trades)
        assert events[0].event_role is EventRole.OPENING
        assert events[0].position_side is PositionSide.SHORT

    def test_buy_closes_short_option(self):
        trades = [
            _make_trade(1, "2026-01-01", "NIFTY", "SELL", "options", 50,
                        type2="CE", strike=22000.0, expiry="2026-01-30"),
            _make_trade(2, "2026-01-10", "NIFTY", "BUY", "options", 50,
                        type2="CE", strike=22000.0, expiry="2026-01-30"),
        ]
        events = process_trades(trades)
        assert events[1].event_role is EventRole.CLOSING
        assert events[1].position_side is PositionSide.SHORT


# ===================================================================
# SECTION 6 — Position lifecycle (from Specification §8)
# ===================================================================

class TestPositionLifecycle:
    """Confirmed example: SELL100 → BUY40 → SELL20 → BUY80
    All belong to one position lifecycle."""

    def test_lifecycle_sell_100_buy_40_sell_20_buy_80(self):
        trades = [
            _make_trade(1, "2026-01-01", "NIFTY", "SELL", "futures", 100,
                        expiry="2026-01-30"),
            _make_trade(2, "2026-01-05", "NIFTY", "BUY", "futures", 40,
                        expiry="2026-01-30"),
            _make_trade(3, "2026-01-10", "NIFTY", "SELL", "futures", 20,
                        expiry="2026-01-30"),
            _make_trade(4, "2026-01-15", "NIFTY", "BUY", "futures", 80,
                        expiry="2026-01-30"),
        ]
        events = process_trades(trades)

        assert events[0].event_role is EventRole.OPENING   # SELL 100 opens short
        assert events[0].position_side is PositionSide.SHORT

        assert events[1].event_role is EventRole.CLOSING    # BUY 40 closes (partial)
        assert events[1].position_side is PositionSide.SHORT

        assert events[2].event_role is EventRole.OPENING    # SELL 20 adds to short
        assert events[2].position_side is PositionSide.SHORT

        assert events[3].event_role is EventRole.CLOSING    # BUY 80 closes fully
        assert events[3].position_side is PositionSide.SHORT

    def test_net_position_is_flat_after_lifecycle(self):
        trades = [
            _make_trade(1, "2026-01-01", "NIFTY", "SELL", "futures", 100,
                        expiry="2026-01-30"),
            _make_trade(2, "2026-01-05", "NIFTY", "BUY", "futures", 40,
                        expiry="2026-01-30"),
            _make_trade(3, "2026-01-10", "NIFTY", "SELL", "futures", 20,
                        expiry="2026-01-30"),
            _make_trade(4, "2026-01-15", "NIFTY", "BUY", "futures", 80,
                        expiry="2026-01-30"),
        ]
        net = get_net_positions(trades)
        assert net[("NIFTY", "futures", None, None, "2026-01-30")] == 0


# ===================================================================
# SECTION 7 — Contract isolation
# ===================================================================

class TestContractIsolation:
    """Different contracts must maintain independent position state."""

    def test_two_equities_independent(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-01", "INFY", "BUY", "delivery", 200),
            _make_trade(3, "2026-01-05", "TCS", "SELL", "delivery", 50),
        ]
        events = process_trades(trades)
        # TCS: BUY(open), SELL(close)
        assert events[0].event_role is EventRole.OPENING
        assert events[2].event_role is EventRole.CLOSING
        assert events[2].equity == "TCS"
        # INFY untouched, stays open
        assert events[1].event_role is EventRole.OPENING
        assert events[1].equity == "INFY"

    def test_options_different_strikes_independent(self):
        trades = [
            _make_trade(1, "2026-01-01", "NIFTY", "BUY", "options", 50,
                        type2="CE", strike=22000.0, expiry="2026-01-30"),
            _make_trade(2, "2026-01-01", "NIFTY", "SELL", "options", 50,
                        type2="CE", strike=23000.0, expiry="2026-01-30"),
        ]
        events = process_trades(trades)
        # Strike 22000 → LONG OPENING
        assert events[0].event_role is EventRole.OPENING
        assert events[0].position_side is PositionSide.LONG
        # Strike 23000 → SHORT OPENING (different contract!)
        assert events[1].event_role is EventRole.OPENING
        assert events[1].position_side is PositionSide.SHORT


# ===================================================================
# SECTION 8 — Passthrough data integrity
# ===================================================================

class TestPassthroughData:
    """Ensure all original trade fields survive the normalization."""

    def test_all_fields_preserved(self):
        trades = [
            _make_trade(
                trade_id=42,
                trade_date="2026-03-15",
                equity="RELIANCE",
                trade_type="BUY",
                type1="delivery",
                quantity=500,
                price=250000,
                brokerage=593,
                notes="test note",
                brokerage_auto=593,
                brokerage_override=None,
                mtf_amount=0,
                mtf_rate_ppm=None,
            ),
        ]
        events = process_trades(trades)
        e = events[0]

        assert e.trade_id == 42
        assert e.trade_date == "2026-03-15"
        assert e.equity == "RELIANCE"
        assert e.original_direction is TradeDirection.BUY
        assert e.type1 == "delivery"
        assert e.quantity == 500
        assert e.price == 250000
        assert e.brokerage == 593
        assert e.notes == "test note"
        assert e.brokerage_auto == 593
        assert e.brokerage_override is None
        assert e.mtf_amount == 0
        assert e.mtf_rate_ppm is None

    def test_event_is_immutable(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
        ]
        events = process_trades(trades)
        with pytest.raises(AttributeError):
            events[0].quantity = 999  # type: ignore[misc]


# ===================================================================
# SECTION 9 — Delivery backward compatibility guarantee
# ===================================================================

class TestDeliveryBackwardCompatibility:
    """For Delivery, every BUY is OPENING (LONG) and every SELL is
    CLOSING (LONG).  This must be byte-for-byte identical to V1 behavior
    where BUY -> buy_queue and SELL -> matching against buy_queue."""

    def test_buy100_buy50_sell120(self):
        """Classic FIFO example from the specification."""
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-02", "TCS", "BUY", "delivery", 50),
            _make_trade(3, "2026-01-10", "TCS", "SELL", "delivery", 120),
        ]
        events = process_trades(trades)

        # All BUYs → OPENING LONG
        assert events[0].event_role is EventRole.OPENING
        assert events[0].position_side is PositionSide.LONG
        assert events[1].event_role is EventRole.OPENING
        assert events[1].position_side is PositionSide.LONG

        # SELL → CLOSING LONG
        assert events[2].event_role is EventRole.CLOSING
        assert events[2].position_side is PositionSide.LONG

    def test_net_position_after_partial_sell(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-02", "TCS", "BUY", "delivery", 50),
            _make_trade(3, "2026-01-10", "TCS", "SELL", "delivery", 120),
        ]
        net = get_net_positions(trades)
        assert net[("TCS", "delivery", None, None, None)] == 30


# ===================================================================
# SECTION 10 — get_net_positions utility
# ===================================================================

class TestGetNetPositions:

    def test_empty_trades(self):
        assert get_net_positions([]) == {}

    def test_long_position(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
        ]
        net = get_net_positions(trades)
        assert net[("TCS", "delivery", None, None, None)] == 100

    def test_short_position(self):
        trades = [
            _make_trade(1, "2026-01-01", "SBIN", "SELL", "intraday", 200),
        ]
        net = get_net_positions(trades)
        assert net[("SBIN", "intraday", None, None, None)] == -200

    def test_flat_after_roundtrip(self):
        trades = [
            _make_trade(1, "2026-01-01", "SBIN", "SELL", "intraday", 200),
            _make_trade(2, "2026-01-01", "SBIN", "BUY", "intraday", 200),
        ]
        net = get_net_positions(trades)
        assert net[("SBIN", "intraday", None, None, None)] == 0


if __name__ == "__main__":
    pytest.main([__file__])
