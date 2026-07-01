"""Business rules for trading products.

This module is the SINGLE SOURCE OF TRUTH for all product-specific
business logic.  No other module should hard-code product behaviour.

Design principles
-----------------
*   Every public function answers a question about a product.
*   The module is purely declarative — no state, no I/O, no database.
*   Adding a new product means adding ONE entry to ``PRODUCT_RULES`` and
    nothing else.
*   Other modules (FIFO matcher, validation, trade manager, …) import
    these functions instead of embedding their own ``if type1 == …``
    branches.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import FrozenSet, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ProductType(str, Enum):
    """Known product types (matches the ``type1`` database column)."""
    DELIVERY = "delivery"
    INTRADAY = "intraday"
    MTF = "mtf"
    FUTURES = "futures"
    OPTIONS = "options"


class TradeDirection(str, Enum):
    """Direction that was executed on the exchange."""
    BUY = "BUY"
    SELL = "SELL"


class PositionSide(str, Enum):
    """Which side of the market the position sits on."""
    LONG = "LONG"
    SHORT = "SHORT"


class EventRole(str, Enum):
    """Whether a trade opens or closes a position."""
    OPENING = "OPENING"
    CLOSING = "CLOSING"


class ContractFieldRequirement(str, Enum):
    """What derivative-classification fields a product needs."""
    NONE = "NONE"           # type2, strike, expiry all empty
    EXPIRY_ONLY = "EXPIRY"  # only expiry required
    FULL = "FULL"           # type2 + strike + expiry


# ---------------------------------------------------------------------------
# Product rule record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductRule:
    """Immutable rule set describing one product's business behaviour."""

    product: ProductType

    # --- position opening rules ---
    can_buy_open: bool
    can_sell_open: bool

    # --- lifecycle rules ---
    overnight_allowed: bool
    expiry_applicable: bool

    # --- financial rules ---
    mtf_interest_applicable: bool
    auto_brokerage_supported: bool

    # --- contract classification ---
    contract_fields: ContractFieldRequirement

    # --- allowed type2 values (for options) ---
    allowed_type2: FrozenSet[str] = frozenset()


# ---------------------------------------------------------------------------
# Central product rules table
# ---------------------------------------------------------------------------
# Adding a new product?  Add one entry here.  That is all.

PRODUCT_RULES: dict[ProductType, ProductRule] = {
    ProductType.DELIVERY: ProductRule(
        product=ProductType.DELIVERY,
        can_buy_open=True,
        can_sell_open=False,
        overnight_allowed=True,
        expiry_applicable=False,
        mtf_interest_applicable=False,
        auto_brokerage_supported=True,
        contract_fields=ContractFieldRequirement.NONE,
    ),
    ProductType.INTRADAY: ProductRule(
        product=ProductType.INTRADAY,
        can_buy_open=True,
        can_sell_open=True,
        overnight_allowed=False,
        expiry_applicable=False,
        mtf_interest_applicable=False,
        auto_brokerage_supported=True,
        contract_fields=ContractFieldRequirement.NONE,
    ),
    ProductType.MTF: ProductRule(
        product=ProductType.MTF,
        can_buy_open=True,
        can_sell_open=False,
        overnight_allowed=True,
        expiry_applicable=False,
        mtf_interest_applicable=True,
        auto_brokerage_supported=True,
        contract_fields=ContractFieldRequirement.NONE,
    ),
    ProductType.FUTURES: ProductRule(
        product=ProductType.FUTURES,
        can_buy_open=True,
        can_sell_open=True,
        overnight_allowed=True,
        expiry_applicable=True,
        mtf_interest_applicable=False,
        auto_brokerage_supported=False,
        contract_fields=ContractFieldRequirement.EXPIRY_ONLY,
    ),
    ProductType.OPTIONS: ProductRule(
        product=ProductType.OPTIONS,
        can_buy_open=True,
        can_sell_open=True,
        overnight_allowed=True,
        expiry_applicable=True,
        mtf_interest_applicable=False,
        auto_brokerage_supported=False,
        contract_fields=ContractFieldRequirement.FULL,
        allowed_type2=frozenset({"CE", "PE"}),
    ),
}


# ---------------------------------------------------------------------------
# Public query helpers
# ---------------------------------------------------------------------------

def get_product_rule(type1: str) -> ProductRule:
    """Return the rule set for *type1*.

    Raises ``ValueError`` if the product is unknown.
    """
    key = type1.strip().lower()
    try:
        product = ProductType(key)
    except ValueError:
        valid = ", ".join(p.value for p in ProductType)
        raise ValueError(
            f"Unknown product type '{type1}'. Valid types: {valid}"
        )
    return PRODUCT_RULES[product]


def get_all_product_types() -> list[str]:
    """Return the list of valid type1 strings (lowercase)."""
    return [p.value for p in ProductType]


# --- opening / closing questions ----------------------------------------

def can_buy_open(type1: str) -> bool:
    """Can a BUY trade open a new position for this product?"""
    return get_product_rule(type1).can_buy_open


def can_sell_open(type1: str) -> bool:
    """Can a SELL trade open a new position for this product?"""
    return get_product_rule(type1).can_sell_open


def supports_short_selling(type1: str) -> bool:
    """Alias — can the product initiate a short (SELL-open) position?"""
    return can_sell_open(type1)


# --- lifecycle questions -------------------------------------------------

def is_overnight_allowed(type1: str) -> bool:
    """Can a position in this product remain open overnight?"""
    return get_product_rule(type1).overnight_allowed


def is_expiry_applicable(type1: str) -> bool:
    """Does this product have an expiry date?"""
    return get_product_rule(type1).expiry_applicable


# --- financial questions -------------------------------------------------

def applies_mtf_interest(type1: str) -> bool:
    """Does this product incur MTF (margin-trade-funding) interest?"""
    return get_product_rule(type1).mtf_interest_applicable


def supports_auto_brokerage(type1: str) -> bool:
    """Does the application have a configured auto-brokerage rate?"""
    return get_product_rule(type1).auto_brokerage_supported


# --- contract classification questions -----------------------------------

def get_contract_field_requirement(type1: str) -> ContractFieldRequirement:
    """What derivative fields does this product require?"""
    return get_product_rule(type1).contract_fields


def get_allowed_type2_values(type1: str) -> FrozenSet[str]:
    """Return valid type2 values (e.g. CE/PE for options)."""
    return get_product_rule(type1).allowed_type2


# --- trade role resolution -----------------------------------------------

def resolve_trade_role(
    type1: str,
    direction: TradeDirection,
    current_net_qty: int,
) -> EventRole:
    """Determine whether a trade is OPENING or CLOSING a position.

    Business logic
    ~~~~~~~~~~~~~~
    *   If the position is flat (``current_net_qty == 0``), the trade
        always opens a new position — provided the product rules allow
        that direction to open.
    *   If the position is long (``> 0``) and a SELL arrives, the trade
        is CLOSING.
    *   If the position is short (``< 0``) and a BUY arrives, the trade
        is CLOSING.
    *   A trade that extends the existing direction (BUY on a long, or
        SELL on a short) is OPENING (adding to position).

    Raises ``ValueError`` for illegal transitions such as a Delivery
    SELL when the position is flat.
    """
    rule = get_product_rule(type1)

    # --- flat position ---------------------------------------------------
    if current_net_qty == 0:
        if direction is TradeDirection.BUY:
            if not rule.can_buy_open:
                raise ValueError(
                    f"{rule.product.value.title()} does not allow BUY to "
                    f"open a position."
                )
            return EventRole.OPENING
        else:  # SELL
            if not rule.can_sell_open:
                raise ValueError(
                    f"{rule.product.value.title()} does not allow SELL to "
                    f"open a position (short selling not permitted)."
                )
            return EventRole.OPENING

    # --- long position (net > 0) -----------------------------------------
    if current_net_qty > 0:
        if direction is TradeDirection.BUY:
            # Adding to a long → opening
            return EventRole.OPENING
        else:
            # Selling against a long → closing
            return EventRole.CLOSING

    # --- short position (net < 0) ----------------------------------------
    if direction is TradeDirection.SELL:
        # Adding to a short → opening
        return EventRole.OPENING
    else:
        # Buying against a short → closing
        return EventRole.CLOSING
