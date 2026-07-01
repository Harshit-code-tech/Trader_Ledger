"""Tests for core/trading_rules.py — Phase 1 verification.

These tests prove that the Business Rules module correctly encodes
every product-specific rule documented in the Trading Rules Engine
Specification v1.0 and the approved architecture proposal.

NO existing module is modified or imported — this test file validates
ONLY the new trading_rules.py module.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest

from core.trading_rules import (
    ProductType,
    TradeDirection,
    PositionSide,
    EventRole,
    ContractFieldRequirement,
    ProductRule,
    PRODUCT_RULES,
    get_product_rule,
    get_all_product_types,
    can_buy_open,
    can_sell_open,
    supports_short_selling,
    is_overnight_allowed,
    is_expiry_applicable,
    applies_mtf_interest,
    supports_auto_brokerage,
    get_contract_field_requirement,
    get_allowed_type2_values,
    resolve_trade_role,
)


# ===================================================================
# SECTION 1 — Product rule table correctness
# ===================================================================

class TestProductRuleTable:
    """Verify PRODUCT_RULES matches the specification exactly."""

    def test_all_five_products_defined(self):
        assert len(PRODUCT_RULES) == 5
        expected = {
            ProductType.DELIVERY,
            ProductType.INTRADAY,
            ProductType.MTF,
            ProductType.FUTURES,
            ProductType.OPTIONS,
        }
        assert set(PRODUCT_RULES.keys()) == expected

    def test_product_rules_are_frozen(self):
        """ProductRule is a frozen dataclass — immutability matters."""
        for rule in PRODUCT_RULES.values():
            assert isinstance(rule, ProductRule)
            with pytest.raises(AttributeError):
                rule.can_buy_open = False  # type: ignore[misc]


# ===================================================================
# SECTION 2 — Opening rules per product (from Specification §2 & §3)
# ===================================================================

class TestOpeningRules:
    """Verify which products can open with BUY and/or SELL."""

    # --- Delivery ---
    def test_delivery_buy_opens(self):
        assert can_buy_open("delivery") is True

    def test_delivery_sell_cannot_open(self):
        assert can_sell_open("delivery") is False

    # --- Intraday ---
    def test_intraday_buy_opens(self):
        assert can_buy_open("intraday") is True

    def test_intraday_sell_opens(self):
        assert can_sell_open("intraday") is True

    # --- MTF ---
    def test_mtf_buy_opens(self):
        assert can_buy_open("mtf") is True

    def test_mtf_sell_cannot_open(self):
        assert can_sell_open("mtf") is False

    # --- Futures ---
    def test_futures_buy_opens(self):
        assert can_buy_open("futures") is True

    def test_futures_sell_opens(self):
        assert can_sell_open("futures") is True

    # --- Options ---
    def test_options_buy_opens(self):
        assert can_buy_open("options") is True

    def test_options_sell_opens(self):
        assert can_sell_open("options") is True


# ===================================================================
# SECTION 3 — Short selling rules (from Specification §7)
# ===================================================================

class TestShortSellingRules:
    def test_delivery_no_short(self):
        assert supports_short_selling("delivery") is False

    def test_mtf_no_short(self):
        assert supports_short_selling("mtf") is False

    def test_intraday_allows_short(self):
        assert supports_short_selling("intraday") is True

    def test_futures_allows_short(self):
        assert supports_short_selling("futures") is True

    def test_options_allows_short(self):
        assert supports_short_selling("options") is True


# ===================================================================
# SECTION 4 — Overnight / lifecycle rules (from Specification §2)
# ===================================================================

class TestOvernightRules:
    def test_delivery_overnight(self):
        assert is_overnight_allowed("delivery") is True

    def test_intraday_no_overnight(self):
        assert is_overnight_allowed("intraday") is False

    def test_mtf_overnight(self):
        assert is_overnight_allowed("mtf") is True

    def test_futures_overnight(self):
        assert is_overnight_allowed("futures") is True

    def test_options_overnight(self):
        assert is_overnight_allowed("options") is True


# ===================================================================
# SECTION 5 — Expiry applicability (from Specification §2)
# ===================================================================

class TestExpiryRules:
    def test_delivery_no_expiry(self):
        assert is_expiry_applicable("delivery") is False

    def test_intraday_no_expiry(self):
        assert is_expiry_applicable("intraday") is False

    def test_mtf_no_expiry(self):
        assert is_expiry_applicable("mtf") is False

    def test_futures_has_expiry(self):
        assert is_expiry_applicable("futures") is True

    def test_options_has_expiry(self):
        assert is_expiry_applicable("options") is True


# ===================================================================
# SECTION 6 — MTF interest (from Specification §11)
# ===================================================================

class TestMtfInterestRules:
    def test_only_mtf_has_interest(self):
        assert applies_mtf_interest("mtf") is True

    def test_delivery_no_interest(self):
        assert applies_mtf_interest("delivery") is False

    def test_intraday_no_interest(self):
        assert applies_mtf_interest("intraday") is False

    def test_futures_no_interest(self):
        assert applies_mtf_interest("futures") is False

    def test_options_no_interest(self):
        assert applies_mtf_interest("options") is False


# ===================================================================
# SECTION 7 — Auto brokerage support (from Specification §10)
# ===================================================================

class TestBrokerageRules:
    def test_delivery_auto_brokerage(self):
        assert supports_auto_brokerage("delivery") is True

    def test_intraday_auto_brokerage(self):
        assert supports_auto_brokerage("intraday") is True

    def test_mtf_auto_brokerage(self):
        assert supports_auto_brokerage("mtf") is True

    def test_futures_no_auto_brokerage(self):
        assert supports_auto_brokerage("futures") is False

    def test_options_no_auto_brokerage(self):
        assert supports_auto_brokerage("options") is False


# ===================================================================
# SECTION 8 — Contract field requirements (from Specification §6)
# ===================================================================

class TestContractFieldRequirements:
    def test_delivery_no_fields(self):
        assert get_contract_field_requirement("delivery") is ContractFieldRequirement.NONE

    def test_intraday_no_fields(self):
        assert get_contract_field_requirement("intraday") is ContractFieldRequirement.NONE

    def test_mtf_no_fields(self):
        assert get_contract_field_requirement("mtf") is ContractFieldRequirement.NONE

    def test_futures_expiry_only(self):
        assert get_contract_field_requirement("futures") is ContractFieldRequirement.EXPIRY_ONLY

    def test_options_full(self):
        assert get_contract_field_requirement("options") is ContractFieldRequirement.FULL

    def test_options_type2_values(self):
        assert get_allowed_type2_values("options") == frozenset({"CE", "PE"})

    def test_delivery_no_type2(self):
        assert get_allowed_type2_values("delivery") == frozenset()


# ===================================================================
# SECTION 9 — Trade role resolution (from Architecture §4)
# ===================================================================

class TestTradeRoleResolution:
    """Verify resolve_trade_role correctly classifies OPENING/CLOSING."""

    # --- Flat position (net = 0) ---

    def test_flat_buy_delivery_opens(self):
        role = resolve_trade_role("delivery", TradeDirection.BUY, 0)
        assert role is EventRole.OPENING

    def test_flat_sell_delivery_raises(self):
        """Delivery cannot open with SELL (no short selling)."""
        with pytest.raises(ValueError, match="short selling not permitted"):
            resolve_trade_role("delivery", TradeDirection.SELL, 0)

    def test_flat_sell_intraday_opens(self):
        role = resolve_trade_role("intraday", TradeDirection.SELL, 0)
        assert role is EventRole.OPENING

    def test_flat_buy_intraday_opens(self):
        role = resolve_trade_role("intraday", TradeDirection.BUY, 0)
        assert role is EventRole.OPENING

    def test_flat_sell_mtf_raises(self):
        """MTF cannot open with SELL."""
        with pytest.raises(ValueError, match="short selling not permitted"):
            resolve_trade_role("mtf", TradeDirection.SELL, 0)

    def test_flat_sell_futures_opens(self):
        role = resolve_trade_role("futures", TradeDirection.SELL, 0)
        assert role is EventRole.OPENING

    def test_flat_sell_options_opens(self):
        role = resolve_trade_role("options", TradeDirection.SELL, 0)
        assert role is EventRole.OPENING

    # --- Long position (net > 0) ---

    def test_long_buy_adds(self):
        """Buying more on a long position → OPENING (adding)."""
        role = resolve_trade_role("delivery", TradeDirection.BUY, 100)
        assert role is EventRole.OPENING

    def test_long_sell_closes(self):
        """Selling against a long → CLOSING."""
        role = resolve_trade_role("delivery", TradeDirection.SELL, 100)
        assert role is EventRole.CLOSING

    def test_long_sell_intraday_closes(self):
        role = resolve_trade_role("intraday", TradeDirection.SELL, 50)
        assert role is EventRole.CLOSING

    def test_long_sell_futures_closes(self):
        role = resolve_trade_role("futures", TradeDirection.SELL, 200)
        assert role is EventRole.CLOSING

    # --- Short position (net < 0) ---

    def test_short_buy_closes(self):
        """Buying against a short → CLOSING (covering)."""
        role = resolve_trade_role("intraday", TradeDirection.BUY, -100)
        assert role is EventRole.CLOSING

    def test_short_sell_adds(self):
        """Selling more on a short → OPENING (adding to short)."""
        role = resolve_trade_role("intraday", TradeDirection.SELL, -100)
        assert role is EventRole.OPENING

    def test_short_buy_futures_closes(self):
        role = resolve_trade_role("futures", TradeDirection.BUY, -50)
        assert role is EventRole.CLOSING

    def test_short_sell_options_adds(self):
        role = resolve_trade_role("options", TradeDirection.SELL, -30)
        assert role is EventRole.OPENING


# ===================================================================
# SECTION 10 — Position lifecycle (from Specification §8)
# ===================================================================

class TestPositionLifecycle:
    """Walk through the confirmed lifecycle example:
    SELL 100 → BUY 40 → SELL 20 → BUY 80
    to verify role resolution at every step.
    """

    def test_lifecycle_sell_100_buy_40_sell_20_buy_80(self):
        product = "futures"
        net = 0

        # SELL 100 → opens short
        role = resolve_trade_role(product, TradeDirection.SELL, net)
        assert role is EventRole.OPENING
        net -= 100  # -100

        # BUY 40 → partially closes short
        role = resolve_trade_role(product, TradeDirection.BUY, net)
        assert role is EventRole.CLOSING
        net += 40   # -60

        # SELL 20 → extends short
        role = resolve_trade_role(product, TradeDirection.SELL, net)
        assert role is EventRole.OPENING
        net -= 20   # -80

        # BUY 80 → fully closes short
        role = resolve_trade_role(product, TradeDirection.BUY, net)
        assert role is EventRole.CLOSING
        net += 80   # 0

        assert net == 0


# ===================================================================
# SECTION 11 — Edge cases & error handling
# ===================================================================

class TestEdgeCases:
    def test_unknown_product_raises(self):
        with pytest.raises(ValueError, match="Unknown product type"):
            get_product_rule("crypto")

    def test_case_insensitive_lookup(self):
        """Users may pass 'Delivery' or 'DELIVERY'."""
        rule = get_product_rule("DELIVERY")
        assert rule.product is ProductType.DELIVERY

    def test_whitespace_stripped(self):
        rule = get_product_rule("  futures  ")
        assert rule.product is ProductType.FUTURES

    def test_get_all_product_types(self):
        types = get_all_product_types()
        assert len(types) == 5
        assert "delivery" in types
        assert "intraday" in types
        assert "mtf" in types
        assert "futures" in types
        assert "options" in types


# ===================================================================
# SECTION 12 — Enumeration values
# ===================================================================

class TestEnumerations:
    def test_position_side_values(self):
        assert PositionSide.LONG.value == "LONG"
        assert PositionSide.SHORT.value == "SHORT"

    def test_event_role_values(self):
        assert EventRole.OPENING.value == "OPENING"
        assert EventRole.CLOSING.value == "CLOSING"

    def test_trade_direction_values(self):
        assert TradeDirection.BUY.value == "BUY"
        assert TradeDirection.SELL.value == "SELL"

if __name__ == "__main__":
    pytest.main([__file__])
