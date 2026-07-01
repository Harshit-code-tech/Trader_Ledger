"""Position State Engine — stateful trade role resolver.

This module processes raw chronological trades and classifies each as
OPENING or CLOSING by tracking the running net position per contract.

Design principles
-----------------
*   This component is **stateful** — a trade's role depends on the
    position state at the moment it is processed.
*   It uses ``trading_rules`` for product-specific decisions (e.g.,
    "can Delivery open with SELL?") and never hard-codes product logic.
*   It outputs **Normalized Trade Events** that the FIFO matcher can
    consume without knowing anything about product types.
*   It is purely in-memory.  No database access, no cached state.
    Historical Determinism: every invocation replays from scratch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.fifo_matcher import TradeTuple, ContractKey
from core.trading_rules import (
    TradeDirection,
    EventRole,
    PositionSide,
    resolve_trade_role,
)


# ---------------------------------------------------------------------------
# Normalized Trade Event
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NormalizedTradeEvent:
    """What the FIFO matcher actually needs to process a trade.

    The matcher no longer cares whether the original trade was BUY or
    SELL.  It only sees OPENING and CLOSING events.
    """

    trade_id: int
    contract_key: ContractKey
    event_role: EventRole          # OPENING or CLOSING
    position_side: PositionSide    # LONG or SHORT
    quantity: int

    # --- passthrough fields for downstream modules -----------------------
    # These are forwarded transparently so that PnL, brokerage, and
    # interest modules can still look up the original trade data.
    trade_date: str
    equity: str
    original_direction: TradeDirection   # BUY or SELL (as executed)
    type1: str
    type2: Optional[str]
    strike: Optional[float]
    expiry: Optional[str]
    price: int
    brokerage: int
    notes: str
    is_active: int
    brokerage_auto: int
    brokerage_override: Optional[int]
    mtf_amount: int
    mtf_rate_ppm: Optional[int]


# ---------------------------------------------------------------------------
# Position State Engine Error
# ---------------------------------------------------------------------------

class PositionStateError(Exception):
    """Raised when the Position State Engine detects an invalid trade."""
    pass


# ---------------------------------------------------------------------------
# Position State Engine
# ---------------------------------------------------------------------------

def process_trades(trades: list[TradeTuple]) -> list[NormalizedTradeEvent]:
    """Process raw chronological trades and classify each as OPENING/CLOSING.

    This function replays the entire trade history from scratch (Historical
    Determinism) and produces a list of Normalized Trade Events in the
    exact same chronological order.

    Parameters
    ----------
    trades : list[TradeTuple]
        Raw trades from ``fetch_active_trades()``, already in
        chronological order.

    Returns
    -------
    list[NormalizedTradeEvent]
        One event per input trade, in the same order.

    Raises
    ------
    PositionStateError
        If a trade creates an invalid transition (e.g. Delivery SELL
        when position is flat).
    """
    # Running net position per contract.
    # Positive = LONG, Negative = SHORT, Zero = FLAT.
    net_positions: dict[ContractKey, int] = {}

    events: list[NormalizedTradeEvent] = []

    for trade in trades:
        # Unpack the TradeTuple
        (trade_id, trade_date, equity, trade_type, type1, type2,
         strike, expiry, quantity, price, brokerage, notes, is_active,
         brokerage_auto, brokerage_override, mtf_amount, mtf_rate_ppm) = trade

        contract_key: ContractKey = (equity, type1, type2, strike, expiry)
        current_net = net_positions.get(contract_key, 0)
        direction = TradeDirection(trade_type)

        # --- ask the Business Rules module ---
        try:
            event_role = resolve_trade_role(type1, direction, current_net)
        except ValueError as exc:
            # Wrap in PositionStateError with trade context
            contract_label = _format_contract_label(equity, type1, type2, strike, expiry)
            raise PositionStateError(
                f"\n{'='*60}\n"
                f"INVALID TRADE TRANSITION\n"
                f"{'='*60}\n"
                f"Trade ID: {trade_id}\n"
                f"Date: {trade_date}\n"
                f"Direction: {trade_type}\n"
                f"Contract: {contract_label}\n"
                f"Current net position: {current_net}\n"
                f"Error: {exc}\n"
                f"{'='*60}"
            ) from exc

        # --- Position Flip Detection ---
        # When a CLOSING trade's quantity exceeds the current position,
        # it "flips" the position. For example:
        #   LONG 78, SELL 32532 → Close 78 (CLOSING) + Open 32454 (OPENING SHORT)
        #   SHORT 50, BUY 200  → Close 50 (CLOSING) + Open 150 (OPENING LONG)
        #
        # This is only allowed if the product rules permit opening from
        # the new direction (e.g. intraday allows SELL-open, delivery does not).

        abs_current = abs(current_net)

        if event_role is EventRole.CLOSING and quantity > abs_current and abs_current > 0:
            # This trade exceeds the current position — check if flip is allowed
            from core.trading_rules import can_sell_open, can_buy_open
            flip_allowed = False
            if direction is TradeDirection.SELL:
                flip_allowed = can_sell_open(type1)
            else:
                flip_allowed = can_buy_open(type1)

            if not flip_allowed:
                # Product does not allow opening from this direction → error
                contract_label = _format_contract_label(equity, type1, type2, strike, expiry)
                raise PositionStateError(
                    f"\n{'='*60}\n"
                    f"OVERSELL DETECTED\n"
                    f"{'='*60}\n"
                    f"Trade ID: {trade_id}\n"
                    f"Date: {trade_date}\n"
                    f"Direction: {trade_type}\n"
                    f"Contract: {contract_label}\n"
                    f"Current position: {current_net}\n"
                    f"Trade quantity: {quantity}\n"
                    f"This product does not allow position flips.\n"
                    f"{'='*60}"
                )

            # --- SPLIT into two events ---
            close_qty = abs_current
            open_qty = quantity - abs_current

            # Determine position side for the CLOSING event
            if current_net > 0:
                close_side = PositionSide.LONG
            else:
                close_side = PositionSide.SHORT

            # Event 1: CLOSING — flatten the existing position
            events.append(NormalizedTradeEvent(
                trade_id=trade_id,
                contract_key=contract_key,
                event_role=EventRole.CLOSING,
                position_side=close_side,
                quantity=close_qty,
                trade_date=trade_date,
                equity=equity,
                original_direction=direction,
                type1=type1,
                type2=type2,
                strike=strike,
                expiry=expiry,
                price=price,
                brokerage=brokerage,
                notes=notes,
                is_active=is_active,
                brokerage_auto=brokerage_auto,
                brokerage_override=brokerage_override,
                mtf_amount=mtf_amount,
                mtf_rate_ppm=mtf_rate_ppm,
            ))

            # Determine the new position side for the OPENING event
            if direction is TradeDirection.BUY:
                new_side = PositionSide.LONG
            else:
                new_side = PositionSide.SHORT

            # Event 2: OPENING — start a new position in the opposite direction
            events.append(NormalizedTradeEvent(
                trade_id=trade_id,
                contract_key=contract_key,
                event_role=EventRole.OPENING,
                position_side=new_side,
                quantity=open_qty,
                trade_date=trade_date,
                equity=equity,
                original_direction=direction,
                type1=type1,
                type2=type2,
                strike=strike,
                expiry=expiry,
                price=price,
                brokerage=brokerage,
                notes=notes,
                is_active=is_active,
                brokerage_auto=brokerage_auto,
                brokerage_override=brokerage_override,
                mtf_amount=mtf_amount,
                mtf_rate_ppm=mtf_rate_ppm,
            ))

            # Update net position
            if direction is TradeDirection.BUY:
                net_positions[contract_key] = current_net + quantity
            else:
                net_positions[contract_key] = current_net - quantity

            continue  # Skip the normal single-event emit below

        # --- determine position side (normal, non-flip case) ---
        if current_net > 0:
            position_side = PositionSide.LONG
        elif current_net < 0:
            position_side = PositionSide.SHORT
        else:
            # Flat → side is determined by direction
            if direction is TradeDirection.BUY:
                position_side = PositionSide.LONG
            else:
                position_side = PositionSide.SHORT

        # --- update running net position ---
        if direction is TradeDirection.BUY:
            net_positions[contract_key] = current_net + quantity
        else:
            net_positions[contract_key] = current_net - quantity

        # --- emit the normalized event ---
        events.append(NormalizedTradeEvent(
            trade_id=trade_id,
            contract_key=contract_key,
            event_role=event_role,
            position_side=position_side,
            quantity=quantity,
            trade_date=trade_date,
            equity=equity,
            original_direction=direction,
            type1=type1,
            type2=type2,
            strike=strike,
            expiry=expiry,
            price=price,
            brokerage=brokerage,
            notes=notes,
            is_active=is_active,
            brokerage_auto=brokerage_auto,
            brokerage_override=brokerage_override,
            mtf_amount=mtf_amount,
            mtf_rate_ppm=mtf_rate_ppm,
        ))

    return events


def get_net_positions(trades: list[TradeTuple]) -> dict[ContractKey, int]:
    """Convenience: return final net positions without the events list.

    Useful for validation or open-position queries.
    """
    net_positions: dict[ContractKey, int] = {}
    for trade in trades:
        trade_type = trade[3]
        equity = trade[2]
        type1 = trade[4]
        type2 = trade[5]
        strike = trade[6]
        expiry = trade[7]
        quantity = trade[8]

        contract_key: ContractKey = (equity, type1, type2, strike, expiry)
        current = net_positions.get(contract_key, 0)
        if trade_type == "BUY":
            net_positions[contract_key] = current + quantity
        else:
            net_positions[contract_key] = current - quantity
    return net_positions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_contract_label(
    equity: str,
    type1: str,
    type2: Optional[str],
    strike: Optional[float],
    expiry: Optional[str],
) -> str:
    """Human-readable contract label for error messages."""
    if type1 == "options":
        return f"{equity} | options | {type2} | {strike} | {expiry}"
    if type1 == "futures":
        return f"{equity} | futures | {expiry}"
    return f"{equity} | {type1}"
