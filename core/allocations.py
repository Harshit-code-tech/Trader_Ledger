"""Shared allocation helpers for proportional amounts in paise."""

from typing import Iterable


class AllocationError(Exception):
    pass


def round_divide(numerator: int, denominator: int) -> int:
    if denominator == 0:
        raise AllocationError("Division by zero in allocation")
    if numerator >= 0:
        return (numerator + (denominator // 2)) // denominator
    return -((abs(numerator) + (denominator // 2)) // denominator)


def allocate_proportional_amount(
    total_amount: int,
    trade_quantity: int,
    match_quantities: Iterable[int]
) -> tuple[list[int], int]:
    """
    Allocate total_amount proportionally to matched quantities.

    Allocation order rule (deterministic):
    - match_quantities must be provided in FIFO match order
    - remainder paise is assigned to the LAST match in that order

    - total_amount: full trade amount (paise)
    - trade_quantity: original trade quantity
    - match_quantities: matched quantities (FIFO order)

    Returns (allocations_per_match, allocated_total).

    For partial matches, allocated_total is proportional to matched_qty_total.
    Remainder paise is assigned to the last match deterministically.
    """
    if trade_quantity <= 0:
        raise AllocationError(f"Invalid trade quantity: {trade_quantity}")

    qty_list = list(match_quantities)
    matched_total = sum(qty_list)
    if matched_total <= 0:
        return [0 for _ in qty_list], 0

    proportional_total = round_divide(total_amount * matched_total, trade_quantity)

    allocations = [
        (proportional_total * qty) // matched_total
        for qty in qty_list
    ]
    remainder = proportional_total - sum(allocations)
    if allocations:
        allocations[-1] += remainder

    return allocations, proportional_total
