"""Unit tests for unit conversion functions."""
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

from app.core.units import to_base_units, from_base_units


def test_to_base_units_valid():
    # 40 kg flour to grams (factor 1000)
    assert to_base_units(40, 1000) == 40000
    assert to_base_units("40", 1000) == 40000
    assert to_base_units(Decimal("40"), 1000) == 40000

    # 10.5 L oil to ml (factor 1000)
    assert to_base_units(10.5, 1000) == 10500
    assert to_base_units("10.5", 1000) == 10500

    # 1.2 kg spice to grams (factor 1000)
    assert to_base_units(1.2, 1000) == 1200

    # Carton of Murukku (20 packets per carton)
    assert to_base_units(2, 20) == 40

    # Base unit direct (factor 1)
    assert to_base_units(500, 1) == 500


def test_to_base_units_rejects_non_whole_numbers():
    # 0.0005 kg with factor 1000 = 0.5 g -> not an integer!
    with pytest.raises(ValueError, match="produces non-integer base units"):
        to_base_units(0.0005, 1000)

    # 1.3 pieces with factor 1 = 1.3 -> not an integer!
    with pytest.raises(ValueError, match="produces non-integer base units"):
        to_base_units(1.3, 1)


def test_to_base_units_invalid_factor():
    with pytest.raises(ValueError, match="factor_to_base must be positive"):
        to_base_units(10, 0)

    with pytest.raises(ValueError, match="factor_to_base must be positive"):
        to_base_units(10, -5)


def test_from_base_units():
    assert from_base_units(40000, 1000) == Decimal("40")
    assert from_base_units(10500, 1000) == Decimal("10.5")
    assert from_base_units(1200, 1000) == Decimal("1.2")
    assert from_base_units(40, 20) == Decimal("2")


if __name__ == "__main__":
    test_to_base_units_valid()
    test_to_base_units_rejects_non_whole_numbers()
    test_to_base_units_invalid_factor()
    test_from_base_units()
    print("All unit conversion tests passed successfully!")
