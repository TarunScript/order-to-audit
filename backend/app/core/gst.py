"""GST calculation helpers for Indian Goods and Services Tax.

Rules:
- Seller state is Tamil Nadu (state code 33).
- Intra-state (Customer State == 33): CGST + SGST (half rate each).
- Inter-state (Customer State != 33): IGST (full rate).
- Rates are stored in basis points (e.g. 500 bp = 5.00%).
- Tax amounts are calculated per line in integer paise, rounded half-up.
- Invoice totals are the exact sums of line values.
"""
from decimal import Decimal
from typing import Dict, NamedTuple
from app.core.money import round_half_up

DEFAULT_SELLER_STATE_CODE = 33
DEFAULT_GST_RATE_BP = 500  # 5%


class LineTaxResult(NamedTuple):
    supply_type: str  # 'INTRA' or 'INTER'
    taxable_paise: int
    gst_rate_bp: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_tax_paise: int
    total_paise: int


def calculate_line_tax(
    taxable_paise: int,
    customer_state_code: int,
    seller_state_code: int = DEFAULT_SELLER_STATE_CODE,
    gst_rate_bp: int = DEFAULT_GST_RATE_BP,
) -> LineTaxResult:
    """Calculate GST components for a single line item in paise.

    Args:
        taxable_paise: Pre-tax amount in integer paise.
        customer_state_code: Numeric 2-digit Indian state code of customer.
        seller_state_code: State code of seller (defaults to 33 - Tamil Nadu).
        gst_rate_bp: GST rate in basis points (500 bp = 5%).

    Returns:
        LineTaxResult containing split taxes and totals in paise.
    """
    if taxable_paise < 0:
        raise ValueError(f"taxable_paise cannot be negative: {taxable_paise}")
    if gst_rate_bp < 0:
        raise ValueError(f"gst_rate_bp cannot be negative: {gst_rate_bp}")

    is_intra = customer_state_code == seller_state_code
    supply_type = "INTRA" if is_intra else "INTER"

    d_taxable = Decimal(taxable_paise)
    d_rate = Decimal(gst_rate_bp) / Decimal(10000)

    if is_intra:
        half_rate = d_rate / Decimal(2)
        cgst = round_half_up(d_taxable * half_rate)
        sgst = round_half_up(d_taxable * half_rate)
        igst = 0
    else:
        cgst = 0
        sgst = 0
        igst = round_half_up(d_taxable * d_rate)

    total_tax = cgst + sgst + igst
    total_paise = taxable_paise + total_tax

    return LineTaxResult(
        supply_type=supply_type,
        taxable_paise=taxable_paise,
        gst_rate_bp=gst_rate_bp,
        cgst_paise=cgst,
        sgst_paise=sgst,
        igst_paise=igst,
        total_tax_paise=total_tax,
        total_paise=total_paise,
    )
