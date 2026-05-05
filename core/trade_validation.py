"""Trade classification validation for derivatives support."""

from datetime import datetime
from typing import Optional, Tuple

TYPE1_VALUES = ("intraday", "delivery", "mtf", "futures", "options")
TYPE2_VALUES = ("CE", "PE")


def _normalize_date(date_str: str) -> str:
    """
    Normalize date input to YYYY-MM-DD.
    Accepts DD-MM-YYYY or YYYY-MM-DD.
    """
    raw = date_str.strip()
    if not raw:
        raise ValueError("Expiry date is required.")

    parts = raw.split("-")
    if len(parts) != 3:
        raise ValueError("Expiry date must be DD-MM-YYYY or YYYY-MM-DD.")

    if len(parts[0]) == 4:
        year, month, day = parts
    elif len(parts[2]) == 4:
        day, month, year = parts
    else:
        raise ValueError("Expiry date must be DD-MM-YYYY or YYYY-MM-DD.")

    try:
        dt = datetime(int(year), int(month), int(day))
    except ValueError as exc:
        raise ValueError(f"Invalid expiry date: {raw}") from exc

    return dt.strftime("%Y-%m-%d")


def normalize_trade_classification(
    type1_raw: Optional[str],
    type2_raw: Optional[str],
    strike_raw: Optional[str],
    expiry_raw: Optional[str],
    *,
    require_type1: bool = True
) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[str]]:
    """
    Validate and normalize derivatives classification fields.

    Returns:
        (type1, type2, strike, expiry)
        - type1: lowercase or None
        - type2: uppercase or None
        - strike: float or None
        - expiry: YYYY-MM-DD or None
    """
    type1 = (type1_raw or "").strip().lower()
    type2 = (type2_raw or "").strip().upper()
    strike_text = (strike_raw or "").strip()
    expiry_text = (expiry_raw or "").strip()

    if not type1:
        if require_type1:
            raise ValueError("Type1 is required.")
        if type2 or strike_text or expiry_text:
            raise ValueError("Type1 is required when Type2/Strike/Expiry is provided.")
        return None, None, None, None

    if type1 not in TYPE1_VALUES:
        raise ValueError(f"Type1 must be one of: {', '.join(TYPE1_VALUES)}")

    strike = None
    if strike_text:
        try:
            strike = float(strike_text)
        except ValueError as exc:
            raise ValueError("Strike must be a number.") from exc
        if strike <= 0:
            raise ValueError("Strike must be greater than 0.")

    expiry = None
    if expiry_text:
        expiry = _normalize_date(expiry_text)

    if type1 == "options":
        if not type2:
            raise ValueError("Type2 is required for options (CE/PE).")
        if type2 not in TYPE2_VALUES:
            raise ValueError("Type2 must be CE or PE for options.")
        if strike is None:
            raise ValueError("Strike is required for options.")
        if expiry is None:
            raise ValueError("Expiry is required for options.")
    elif type1 == "futures":
        if type2:
            raise ValueError("Type2 must be empty for futures.")
        if strike is not None:
            raise ValueError("Strike must be empty for futures.")
        if expiry is None:
            raise ValueError("Expiry is required for futures.")
    else:
        if type2:
            raise ValueError("Type2 must be empty for intraday/delivery/mtf.")
        if strike is not None:
            raise ValueError("Strike must be empty for intraday/delivery/mtf.")
        if expiry is not None:
            raise ValueError("Expiry must be empty for intraday/delivery/mtf.")

    return type1, (type2 if type2 else None), strike, expiry
