"""
Utility functions for Trader Ledger application.

Provides common helpers used across multiple modules:
- Currency formatting
- Date formatting
- Common calculations
"""


def format_money(paise: int) -> str:
    """
    Convert paise (integer) to formatted rupees string.
    
    Args:
        paise: Amount in paise (1 rupee = 100 paise)
    
    Returns:
        Formatted string like "₹1234.56"
    
    Examples:
        >>> format_money(123456)
        '₹1234.56'
        >>> format_money(0)
        '₹0.00'
        >>> format_money(-50000)
        '₹-500.00'
    """
    rupees = paise / 100
    return f"₹{rupees:.2f}"


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
