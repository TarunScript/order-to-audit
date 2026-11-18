"""Unit conversion helpers.

All stored quantities in the database are integers in base units:
- Raw materials: grams ('g') or millilitres ('ml')
- Packaging & finished goods: pieces ('piece' / packets)

Conversions must result in exact integers. Any non-whole-number base unit result
is strictly rejected.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Union


def to_base_units(qty: Union[Decimal, float, int, str], factor_to_base: int) -> int:
    """Convert a quantity in a display/input unit to integer base units.

    Args:
        qty: Input quantity (e.g., 40 for 40 kg, 10.5 for 10.5 L).
        factor_to_base: Conversion factor to base unit (e.g., 1000 for kg->g).

    Returns:
        Exact integer quantity in base units.

    Raises:
        ValueError: If factor_to_base <= 0, or if conversion does not yield a whole number.
    """
    if factor_to_base <= 0:
        raise ValueError(f"factor_to_base must be positive, got {factor_to_base}")

    d_qty = Decimal(str(qty))
    d_factor = Decimal(factor_to_base)
    d_base = d_qty * d_factor

    # Check if the result is an exact integer
    if d_base != d_base.to_integral_value():
        raise ValueError(
            f"Quantity {qty} with factor {factor_to_base} produces non-integer base units: {d_base}"
        )

    return int(d_base)


def from_base_units(qty_base: int, factor_to_base: int) -> Decimal:
    """Convert integer base units to display unit value.

    Args:
        qty_base: Stored quantity in integer base units.
        factor_to_base: Conversion factor to base unit.

    Returns:
        Decimal quantity in the display unit.

    Raises:
        ValueError: If factor_to_base <= 0.
    """
    if factor_to_base <= 0:
        raise ValueError(f"factor_to_base must be positive, got {factor_to_base}")

    return Decimal(qty_base) / Decimal(factor_to_base)
