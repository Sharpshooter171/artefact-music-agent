import pytest

from app.catalog.rules import (
    derive_availability,
    parse_price_to_cents,
    parse_stock_quantity,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("849", 84900),
        ("599.9", 59990),
        ("199.99", 19999),
        (" 10 ", 1000),
        ("0", 0),
    ],
)
def test_parse_price_to_exact_cents(raw, expected):
    assert parse_price_to_cents(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "-1", "R$ 10", "1.234", "1e3", ".5", "1.", "abc", "10,50"],
)
def test_invalid_prices_fail_instead_of_rounding(raw):
    with pytest.raises(ValueError):
        parse_price_to_cents(raw)


@pytest.mark.parametrize(("raw", "expected"), [("0", 0), ("15", 15), (" 3 ", 3)])
def test_parse_stock_quantity(raw, expected):
    assert parse_stock_quantity(raw) == expected


@pytest.mark.parametrize("raw", ["-1", "1.5", "abc", ""])
def test_invalid_stock_fails(raw):
    with pytest.raises(ValueError):
        parse_stock_quantity(raw)


@pytest.mark.parametrize(
    ("status", "stock", "expected"),
    [
        ("active", 5, "available"),
        ("active", 0, "out_of_stock"),
        ("coming_soon", 2, "coming_soon"),
        ("coming_soon", 0, "coming_soon"),
        ("discontinued", 13, "discontinued"),
        ("discontinued", 0, "discontinued"),
    ],
)
def test_status_to_availability(status, stock, expected):
    assert derive_availability(status, stock) == expected


def test_unknown_status_fails_closed():
    with pytest.raises(ValueError):
        derive_availability("sold_out", 1)
