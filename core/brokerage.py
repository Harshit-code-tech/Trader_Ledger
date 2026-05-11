"""Brokerage calculation helpers (paise, integer-safe)."""

from typing import Optional

from core.allocations import round_divide

# Rates in parts-per-million (ppm)
BROKERAGE_RATE_PPM: dict[tuple[str, str], int] = {
    ("delivery", "BUY"): 2370,
    ("delivery", "SELL"): 2220,
    ("mtf", "BUY"): 2370,
    ("mtf", "SELL"): 2220,
    ("intraday", "BUY"): 190,
    ("intraday", "SELL"): 410,
}


def get_brokerage_rate_ppm(type1: str, trade_type: str) -> Optional[int]:
    key = (type1.strip().lower(), trade_type.strip().upper())
    return BROKERAGE_RATE_PPM.get(key)


def calculate_brokerage_auto(quantity: int, price_paise: int, type1: str, trade_type: str) -> tuple[int, int]:
    """
    Calculate brokerage in paise using configured rate.
    Returns (brokerage_paise, rate_ppm).
    Raises ValueError if rate is not configured.
    """
    rate_ppm = get_brokerage_rate_ppm(type1, trade_type)
    if rate_ppm is None:
        raise ValueError("Brokerage rate not configured for this trade type")

    trade_amount = quantity * price_paise
    brokerage = round_divide(trade_amount * rate_ppm, 1_000_000)
    return brokerage, rate_ppm


def get_effective_brokerage(trade: dict) -> int:
    """Resolve effective brokerage with override > auto > legacy brokerage fallback."""
    override = trade.get("brokerage_override")
    if override is not None:
        return int(override)

    auto = trade.get("brokerage_auto")
    if auto is not None and int(auto) > 0:
        return int(auto)

    legacy = trade.get("brokerage")
    if legacy is not None:
        return int(legacy)

    return 0
