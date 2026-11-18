"""Money and currency calculation helpers.

Rules:
- All stored money values are integer paise (BIGINT).
- Unit costs (paise per base unit) use NUMERIC(18,6) Decimals.
- Line values and tax amounts round half-up to whole paise.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Union


def round_half_up(value: Union[Decimal, float, int, str]) -> int:
    """Round a decimal value half-up to the nearest integer.

    Args:
        value: Number to round.

    Returns:
        Rounded integer.
    """
    d = Decimal(str(value))
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def rupees_to_paise(rupees: Union[Decimal, float, int, str]) -> int:
    """Convert an amount in rupees to integer paise (1 Rupee = 100 paise).

    Args:
        rupees: Amount in rupees (e.g. 50 or "50.00").

    Returns:
        Integer paise (e.g. 5000).
    """
    d = Decimal(str(rupees)) * Decimal("100")
    return round_half_up(d)


def paise_to_rupees(paise: int) -> Decimal:
    """Convert integer paise to Decimal rupees with 2 decimal places.

    Args:
        paise: Amount in paise (e.g. 5000).

    Returns:
        Decimal amount in rupees (e.g. Decimal("50.00")).
    """
    return (Decimal(paise) / Decimal("100")).quantize(Decimal("0.01"))


def compute_line_value(qty_base: int, unit_cost: Union[Decimal, str, float]) -> int:
    """Compute total line value in integer paise from base qty and unit cost.

    Args:
        qty_base: Stored quantity in integer base units.
        unit_cost: Unit cost in paise per base unit (NUMERIC(18,6)).

    Returns:
        Total value in integer paise, rounded half-up.
    """
    d_cost = Decimal(str(unit_cost))
    raw_val = Decimal(qty_base) * d_cost
    return round_half_up(raw_val)


def format_inr(paise: int) -> str:
    """Format paise as Indian Rupee string, e.g., 787500 -> '₹7,875.00'.

    Args:
        paise: Amount in integer paise.

    Returns:
        Formatted INR string with standard Indian number commas.
    """
    rupees = paise_to_rupees(paise)
    s = f"{rupees:.2f}"
    parts = s.split(".")
    int_part = parts[0]
    dec_part = parts[1]

    # Indian comma grouping (last 3, then pairs of 2)
    is_neg = False
    if int_part.startswith("-"):
        is_neg = True
        int_part = int_part[1:]

    if len(int_part) <= 3:
        formatted_int = int_part
    else:
        last3 = int_part[-3:]
        rest = int_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        formatted_int = ",".join(groups) + "," + last3

    if is_neg:
        formatted_int = "-" + formatted_int

    return f"₹{formatted_int}.{dec_part}"
