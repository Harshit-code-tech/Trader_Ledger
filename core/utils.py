"""
Utility functions for Trader Ledger application.

Provides common helpers used across multiple modules:
- Currency formatting
- Date formatting
- Common calculations
"""

from datetime import datetime


def format_money(paise: int) -> str:
    """
    Convert paise (integer) to formatted rupees string with sign.
    
    Args:
        paise: Amount in paise (1 rupee = 100 paise)
    
    Returns:
        Formatted string like "₹ +1234.56" or "₹ -500.00"
    
    Examples:
        >>> format_money(123456)
        '₹ +1234.56'
        >>> format_money(0)
        '₹ 0.00'
        >>> format_money(-50000)
        '₹ -500.00'
    """
    rupees = paise / 100
    if paise > 0:
        return f"₹ +{rupees:,.2f}"
    elif paise < 0:
        return f"₹ -{abs(rupees):,.2f}"
    else:
        return f"₹ {rupees:.2f}"


def format_money_abs(paise: int) -> str:
    """
    Convert paise to formatted rupees string with absolute value.
    Useful for displaying losses as positive numbers.
    
    Args:
        paise: Amount in paise (can be negative)
    
    Returns:
        Formatted string with absolute value like "₹1234.56"
    
    Examples:
        >>> format_money_abs(-123456)
        '₹1234.56'
        >>> format_money_abs(123456)
        '₹1234.56'
    """
    rupees = abs(paise) / 100
    return f"₹{rupees:,.2f}"


def format_period_label(period_key: str, mode: str) -> str:
    """
    Convert internal period keys into human-friendly labels.
    
    Args:
        period_key: Internal key (YYYY-MM-DD, YYYY-Www, YYYY-MM, YYYY)
        mode: Period type ('daily' | 'weekly' | 'monthly' | 'yearly')
    
    Returns:
        Human-readable label
    
    Examples:
        >>> format_period_label('2026-01-15', 'daily')
        '15 Jan 2026'
        >>> format_period_label('2026-W03', 'weekly')
        'Week 3 (Jan 2026)'
    """
    if mode == "daily":
        # '2026-01-15' → '15 Jan 2026'
        dt = datetime.strptime(period_key, "%Y-%m-%d")
        return dt.strftime("%d %b %Y")
    
    if mode == "weekly":
        # '2026-W03' → 'Week 3 (Jan 2026)'
        year, week = period_key.split("-W")
        dt = datetime.fromisocalendar(int(year), int(week), 1)
        return f"Week {int(week)} ({dt.strftime('%b %Y')})"
    
    if mode == "monthly":
        # '2026-01' → 'Jan 2026'
        dt = datetime.strptime(period_key, "%Y-%m")
        return dt.strftime("%b %Y")
    
    if mode == "yearly":
        # '2026' → 'Year 2026'
        return f"Year {period_key}"
    
    # Fallback
    return period_key
    return f"₹{rupees:.2f}"


def paise_to_rupees(paise: int) -> float:
    """
    Convert paise to rupees as a float.
    
    Args:
        paise: Amount in paise
    
    Returns:
        Amount in rupees as float
    """
    return paise / 100


def rupees_to_paise(rupees: float) -> int:
    """
    Convert rupees to paise as an integer.
    
    Args:
        rupees: Amount in rupees
    
    Returns:
        Amount in paise as integer
    """
    return int(rupees * 100)
