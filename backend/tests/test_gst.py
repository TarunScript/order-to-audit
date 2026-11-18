"""Unit tests for GST calculation logic."""
from decimal import Decimal

try:
    import pytest
except ImportError:
    class _PytestMock:
        @staticmethod
        def raises(exc_type, match=None):
            class _Context:
                def __enter__(self):
                    return self
                def __exit__(self, exc_type_val, exc_val, exc_tb):
                    if not exc_val:
                        raise AssertionError(f"Expected {exc_type} but nothing was raised")
                    return issubclass(exc_type_val, exc_type)
            return _Context()
    pytest = _PytestMock()

from app.core.gst import calculate_line_tax


def test_intra_state_gst_retailer_a():
    """Retailer A in Tamil Nadu (state code 33), 150 packets @ ₹50 = ₹7,500.00."""
    taxable_paise = 750000  # ₹7,500.00
    res = calculate_line_tax(
        taxable_paise=taxable_paise,
        customer_state_code=33,
        seller_state_code=33,
        gst_rate_bp=500,
    )
    assert res.supply_type == "INTRA"
    assert res.cgst_paise == 18750  # ₹187.50
    assert res.sgst_paise == 18750  # ₹187.50
    assert res.igst_paise == 0
    assert res.total_tax_paise == 37500
    assert res.total_paise == 787500  # ₹7,875.00


def test_inter_state_gst_distributor_b():
    """Distributor B in Karnataka (state code 29), 120 packets @ ₹50 = ₹6,000.00."""
    taxable_paise = 600000  # ₹6,000.00
    res = calculate_line_tax(
        taxable_paise=taxable_paise,
        customer_state_code=29,
        seller_state_code=33,
        gst_rate_bp=500,
    )
    assert res.supply_type == "INTER"
    assert res.cgst_paise == 0
    assert res.sgst_paise == 0
    assert res.igst_paise == 30000  # ₹300.00
    assert res.total_tax_paise == 30000
    assert res.total_paise == 630000  # ₹6,300.00


def test_inter_state_gst_distributor_b_edited_shortage():
    """Distributor B adjusted for shortage: 88 packets @ ₹50 = ₹4,400.00."""
    taxable_paise = 440000  # ₹4,400.00
    res = calculate_line_tax(
        taxable_paise=taxable_paise,
        customer_state_code=29,
        seller_state_code=33,
        gst_rate_bp=500,
    )
    assert res.supply_type == "INTER"
    assert res.cgst_paise == 0
    assert res.sgst_paise == 0
    assert res.igst_paise == 22000  # ₹220.00
    assert res.total_paise == 462000  # ₹4,620.00


def test_gst_rounding_half_up():
    """Verify standard half-up rounding behaviour."""
    # 101 paise @ 5% intra: 101 * 0.025 = 2.525 -> 3 paise
    res = calculate_line_tax(taxable_paise=101, customer_state_code=33, seller_state_code=33, gst_rate_bp=500)
    assert res.cgst_paise == 3
    assert res.sgst_paise == 3
    assert res.total_paise == 107


def test_gst_negative_input_rejected():
    with pytest.raises(ValueError):
        calculate_line_tax(taxable_paise=-100, customer_state_code=33)

    with pytest.raises(ValueError):
        calculate_line_tax(taxable_paise=100, customer_state_code=33, gst_rate_bp=-50)


if __name__ == "__main__":
    test_intra_state_gst_retailer_a()
    test_inter_state_gst_distributor_b()
    test_inter_state_gst_distributor_b_edited_shortage()
    test_gst_rounding_half_up()
    test_gst_negative_input_rejected()
    print("All GST calculation tests passed successfully!")
