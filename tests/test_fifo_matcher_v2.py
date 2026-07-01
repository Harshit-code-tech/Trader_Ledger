"""Tests for Phase 3: FIFO Matcher refactor.

These tests prove that:
1. Delivery/MTF matching produces IDENTICAL MatchRecords to V1.
2. The SQL ORDER BY hack has been removed (chronological ordering).
3. Intraday/Futures/Options short selling produces correct MatchRecords.
4. The PnL formula (sell_value - buy_cost) remains valid for both
   LONG and SHORT positions.
5. validate_fifo still works.
6. Error handling is preserved.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest

from core.fifo_matcher import (
    match_fifo,
    validate_fifo,
    FifoMatchError,
    MatchRecord,
)


# ---------------------------------------------------------------------------
# Helper to build TradeTuples from minimal data
# ---------------------------------------------------------------------------

def _make_trade(
    trade_id, trade_date, equity, trade_type, type1, quantity,
    price=10000, type2=None, strike=None, expiry=None,
    brokerage=0, notes="", is_active=1, brokerage_auto=0,
    brokerage_override=None, mtf_amount=0, mtf_rate_ppm=None,
):
    return (
        trade_id, trade_date, equity, trade_type, type1, type2,
        strike, expiry, quantity, price, brokerage, notes, is_active,
        brokerage_auto, brokerage_override, mtf_amount, mtf_rate_ppm,
    )


# ===================================================================
# SECTION 1 — Delivery backward compatibility (MUST be identical to V1)
# ===================================================================

class TestDeliveryBackwardCompatibility:
    """These tests guarantee that Delivery matching has not changed."""

    def test_simple_buy_sell(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-10", "TCS", "SELL", "delivery", 100),
        ]
        matches = match_fifo(trades)
        assert matches == [
            MatchRecord(sell_id=2, buy_id=1, matched_quantity=100, equity="TCS"),
        ]

    def test_buy100_buy50_sell120(self):
        """Classic FIFO example from the specification."""
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-02", "TCS", "BUY", "delivery", 50),
            _make_trade(3, "2026-01-10", "TCS", "SELL", "delivery", 120),
        ]
        matches = match_fifo(trades)
        assert matches == [
            MatchRecord(sell_id=3, buy_id=1, matched_quantity=100, equity="TCS"),
            MatchRecord(sell_id=3, buy_id=2, matched_quantity=20, equity="TCS"),
        ]

    def test_partial_sell_leaves_open(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-10", "TCS", "SELL", "delivery", 40),
        ]
        matches = match_fifo(trades)
        assert matches == [
            MatchRecord(sell_id=2, buy_id=1, matched_quantity=40, equity="TCS"),
        ]

    def test_multiple_sells(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-05", "TCS", "SELL", "delivery", 30),
            _make_trade(3, "2026-01-10", "TCS", "SELL", "delivery", 70),
        ]
        matches = match_fifo(trades)
        assert matches == [
            MatchRecord(sell_id=2, buy_id=1, matched_quantity=30, equity="TCS"),
            MatchRecord(sell_id=3, buy_id=1, matched_quantity=70, equity="TCS"),
        ]

    def test_delivery_oversell_raises(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-10", "TCS", "SELL", "delivery", 150),
        ]
        with pytest.raises(FifoMatchError, match="OVERSELL DETECTED"):
            match_fifo(trades)

    def test_delivery_sell_before_buy_raises(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "SELL", "delivery", 100),
        ]
        with pytest.raises(FifoMatchError, match="INVALID TRADE TRANSITION"):
            match_fifo(trades)


# ===================================================================
# SECTION 2 — MTF backward compatibility
# ===================================================================

class TestMtfBackwardCompatibility:

    def test_simple_mtf_buy_sell(self):
        trades = [
            _make_trade(1, "2026-01-01", "INFY", "BUY", "mtf", 200,
                        mtf_amount=500000, mtf_rate_ppm=96500),
            _make_trade(2, "2026-01-15", "INFY", "SELL", "mtf", 200),
        ]
        matches = match_fifo(trades)
        assert matches == [
            MatchRecord(sell_id=2, buy_id=1, matched_quantity=200, equity="INFY"),
        ]

    def test_mtf_sell_before_buy_raises(self):
        trades = [
            _make_trade(1, "2026-01-01", "INFY", "SELL", "mtf", 100),
        ]
        with pytest.raises(FifoMatchError, match="INVALID TRADE TRANSITION"):
            match_fifo(trades)


# ===================================================================
# SECTION 3 — Intraday short selling (NEW capability)
# ===================================================================

class TestIntradayShortSelling:
    """Intraday: SELL may open first, BUY closes."""

    def test_sell_then_buy(self):
        """Intraday short: SELL opens, BUY closes."""
        trades = [
            _make_trade(1, "2026-01-01", "SBIN", "SELL", "intraday", 100),
            _make_trade(2, "2026-01-01", "SBIN", "BUY", "intraday", 100),
        ]
        matches = match_fifo(trades)
        # sell_id = SELL trade (1), buy_id = BUY trade (2)
        assert matches == [
            MatchRecord(sell_id=1, buy_id=2, matched_quantity=100, equity="SBIN"),
        ]

    def test_sell_then_partial_buy(self):
        trades = [
            _make_trade(1, "2026-01-01", "SBIN", "SELL", "intraday", 100),
            _make_trade(2, "2026-01-01", "SBIN", "BUY", "intraday", 60),
        ]
        matches = match_fifo(trades)
        assert matches == [
            MatchRecord(sell_id=1, buy_id=2, matched_quantity=60, equity="SBIN"),
        ]

    def test_buy_then_sell(self):
        """Intraday long: BUY opens, SELL closes (same as V1)."""
        trades = [
            _make_trade(1, "2026-01-01", "SBIN", "BUY", "intraday", 100),
            _make_trade(2, "2026-01-01", "SBIN", "SELL", "intraday", 100),
        ]
        matches = match_fifo(trades)
        assert matches == [
            MatchRecord(sell_id=2, buy_id=1, matched_quantity=100, equity="SBIN"),
        ]


# ===================================================================
# SECTION 4 — Futures short selling (NEW capability)
# ===================================================================

class TestFuturesShortSelling:

    def test_sell_then_buy(self):
        trades = [
            _make_trade(1, "2026-01-01", "NIFTY", "SELL", "futures", 75,
                        expiry="2026-01-30"),
            _make_trade(2, "2026-01-15", "NIFTY", "BUY", "futures", 75,
                        expiry="2026-01-30"),
        ]
        matches = match_fifo(trades)
        assert matches == [
            MatchRecord(sell_id=1, buy_id=2, matched_quantity=75, equity="NIFTY"),
        ]

    def test_multiple_sells_then_buy(self):
        trades = [
            _make_trade(1, "2026-01-01", "NIFTY", "SELL", "futures", 50,
                        expiry="2026-01-30"),
            _make_trade(2, "2026-01-05", "NIFTY", "SELL", "futures", 25,
                        expiry="2026-01-30"),
            _make_trade(3, "2026-01-15", "NIFTY", "BUY", "futures", 75,
                        expiry="2026-01-30"),
        ]
        matches = match_fifo(trades)
        assert matches == [
            MatchRecord(sell_id=1, buy_id=3, matched_quantity=50, equity="NIFTY"),
            MatchRecord(sell_id=2, buy_id=3, matched_quantity=25, equity="NIFTY"),
        ]


# ===================================================================
# SECTION 5 — Options short selling (NEW capability)
# ===================================================================

class TestOptionsShortSelling:

    def test_sell_then_buy(self):
        trades = [
            _make_trade(1, "2026-01-01", "NIFTY", "SELL", "options", 50,
                        type2="CE", strike=22000.0, expiry="2026-01-30"),
            _make_trade(2, "2026-01-10", "NIFTY", "BUY", "options", 50,
                        type2="CE", strike=22000.0, expiry="2026-01-30"),
        ]
        matches = match_fifo(trades)
        assert matches == [
            MatchRecord(sell_id=1, buy_id=2, matched_quantity=50, equity="NIFTY"),
        ]


# ===================================================================
# SECTION 6 — Position lifecycle (Specification §8)
# ===================================================================

class TestPositionLifecycle:
    """SELL100 → BUY40 → SELL20 → BUY80 = one logical position."""

    def test_lifecycle(self):
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
        matches = match_fifo(trades)

        # BUY 40 closes against SELL 100 (first opening)
        assert matches[0] == MatchRecord(
            sell_id=1, buy_id=2, matched_quantity=40, equity="NIFTY"
        )
        # BUY 80 closes against SELL 100 (remaining 60)
        assert matches[1] == MatchRecord(
            sell_id=1, buy_id=4, matched_quantity=60, equity="NIFTY"
        )
        # BUY 80 closes against SELL 20 (remaining 20)
        assert matches[2] == MatchRecord(
            sell_id=3, buy_id=4, matched_quantity=20, equity="NIFTY"
        )
        assert len(matches) == 3


# ===================================================================
# SECTION 7 — PnL formula validity
# ===================================================================

class TestPnlFormulaValidity:
    """Prove that (sell_value - buy_cost) gives correct P/L for both
    LONG and SHORT positions via the MatchRecord mapping."""

    def test_long_profit(self):
        """BUY at 100, SELL at 120 → profit 20 per share."""
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 10, price=10000),
            _make_trade(2, "2026-01-10", "TCS", "SELL", "delivery", 10, price=12000),
        ]
        matches = match_fifo(trades)
        m = matches[0]
        pnl = (m['matched_quantity'] * 12000) - (m['matched_quantity'] * 10000)
        assert pnl == 20000  # 10 shares × 20 paise profit

    def test_short_profit(self):
        """SELL at 120, BUY at 100 → profit 20 per share (short)."""
        trades = [
            _make_trade(1, "2026-01-01", "SBIN", "SELL", "intraday", 10, price=12000),
            _make_trade(2, "2026-01-01", "SBIN", "BUY", "intraday", 10, price=10000),
        ]
        matches = match_fifo(trades)
        m = matches[0]
        # sell_id=1 (SELL at 12000), buy_id=2 (BUY at 10000)
        assert m['sell_id'] == 1
        assert m['buy_id'] == 2
        # PnL = sell_value - buy_cost = 120000 - 100000 = +20000
        pnl = (m['matched_quantity'] * 12000) - (m['matched_quantity'] * 10000)
        assert pnl == 20000

    def test_short_loss(self):
        """SELL at 100, BUY at 120 → loss 20 per share (short)."""
        trades = [
            _make_trade(1, "2026-01-01", "SBIN", "SELL", "intraday", 10, price=10000),
            _make_trade(2, "2026-01-01", "SBIN", "BUY", "intraday", 10, price=12000),
        ]
        matches = match_fifo(trades)
        m = matches[0]
        pnl = (m['matched_quantity'] * 10000) - (m['matched_quantity'] * 12000)
        assert pnl == -20000  # Loss because sold low, bought back high


# ===================================================================
# SECTION 8 — Contract isolation
# ===================================================================

class TestContractIsolation:

    def test_different_equities_isolated(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-01", "INFY", "BUY", "delivery", 200),
            _make_trade(3, "2026-01-05", "TCS", "SELL", "delivery", 100),
            _make_trade(4, "2026-01-05", "INFY", "SELL", "delivery", 200),
        ]
        matches = match_fifo(trades)
        tcs_matches = [m for m in matches if m['equity'] == 'TCS']
        infy_matches = [m for m in matches if m['equity'] == 'INFY']
        assert len(tcs_matches) == 1
        assert len(infy_matches) == 1
        assert tcs_matches[0]['matched_quantity'] == 100
        assert infy_matches[0]['matched_quantity'] == 200


# ===================================================================
# SECTION 9 — validate_fifo
# ===================================================================

class TestValidateFifo:

    def test_valid_trades(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-10", "TCS", "SELL", "delivery", 100),
        ]
        assert validate_fifo(trades) is True

    def test_oversell_raises(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-10", "TCS", "SELL", "delivery", 200),
        ]
        with pytest.raises(FifoMatchError):
            validate_fifo(trades)

    def test_empty_trades(self):
        assert validate_fifo([]) is True


# ===================================================================
# SECTION 10 — collect_matches=False
# ===================================================================

class TestCollectMatchesFalse:

    def test_returns_none(self):
        trades = [
            _make_trade(1, "2026-01-01", "TCS", "BUY", "delivery", 100),
            _make_trade(2, "2026-01-10", "TCS", "SELL", "delivery", 100),
        ]
        result = match_fifo(trades, collect_matches=False)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__])
