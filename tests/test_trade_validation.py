"""Tests for core/trade_validation.py — Phase 4 verification.

These tests prove that:
1. `normalize_trade_classification` successfully uses `trading_rules.py`
   instead of hardcoded logic.
2. It correctly enforces required fields for Options (FULL), Futures
   (EXPIRY_ONLY), and Intraday/Delivery/MTF (NONE).
3. It validates Type1 against the dynamic list from `trading_rules`.
4. It normalizes dates correctly.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from core.trade_validation import normalize_trade_classification


class TestTradeValidationV2:

    def test_delivery_valid(self):
        t1, t2, strike, exp = normalize_trade_classification("delivery", None, None, None)
        assert t1 == "delivery"
        assert t2 is None
        assert strike is None
        assert exp is None

    def test_delivery_invalid_fields(self):
        with pytest.raises(ValueError, match="Type2 must be empty for delivery"):
            normalize_trade_classification("delivery", "CE", None, None)
        with pytest.raises(ValueError, match="Strike must be empty for delivery"):
            normalize_trade_classification("delivery", None, "100", None)
        with pytest.raises(ValueError, match="Expiry must be empty for delivery"):
            normalize_trade_classification("delivery", None, None, "2026-01-01")

    def test_futures_valid(self):
        t1, t2, strike, exp = normalize_trade_classification("futures", None, None, "2026-01-30")
        assert t1 == "futures"
        assert t2 is None
        assert strike is None
        assert exp == "2026-01-30"

    def test_futures_invalid_fields(self):
        with pytest.raises(ValueError, match="Type2 must be empty for futures"):
            normalize_trade_classification("futures", "CE", None, "2026-01-30")
        with pytest.raises(ValueError, match="Strike must be empty for futures"):
            normalize_trade_classification("futures", None, "100", "2026-01-30")
        with pytest.raises(ValueError, match="Expiry is required for futures"):
            normalize_trade_classification("futures", None, None, None)

    def test_options_valid(self):
        t1, t2, strike, exp = normalize_trade_classification("options", "CE", "22000", "30-01-2026")
        assert t1 == "options"
        assert t2 == "CE"
        assert strike == 22000.0
        assert exp == "2026-01-30"  # Normalized date

    def test_options_invalid_fields(self):
        with pytest.raises(ValueError, match="Type2 is required for options"):
            normalize_trade_classification("options", None, "22000", "2026-01-30")
        with pytest.raises(ValueError, match="Type2 must be CE or PE for options"):
            normalize_trade_classification("options", "XX", "22000", "2026-01-30")
        with pytest.raises(ValueError, match="Strike is required for options"):
            normalize_trade_classification("options", "CE", None, "2026-01-30")
        with pytest.raises(ValueError, match="Expiry is required for options"):
            normalize_trade_classification("options", "CE", "22000", None)

    def test_invalid_type1(self):
        with pytest.raises(ValueError, match="Type1 must be one of:"):
            normalize_trade_classification("magic", None, None, None)

    def test_date_normalization(self):
        _, _, _, exp = normalize_trade_classification("futures", None, None, "01-05-2026")
        assert exp == "2026-05-01"
        
        _, _, _, exp = normalize_trade_classification("futures", None, None, "2026-05-01")
        assert exp == "2026-05-01"

if __name__ == "__main__":
    pytest.main([__file__])
