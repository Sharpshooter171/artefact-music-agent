import sqlite3

import pytest

from app.catalog.tools import get_product_details


def _assert_no_stock_key(value):
    if isinstance(value, dict):
        assert "stock_quantity" not in value
        assert "stock" not in value
        for nested in value.values():
            _assert_no_stock_key(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_stock_key(nested)


def test_product_details_are_grounded_in_catalog_data(catalog):
    result = get_product_details(101)

    assert result["ok"] is True
    assert result["data"]["product"] == {
        "product_id": 101,
        "name": "Yamaha C40 Nylon Natural",
        "category": {"id": 1, "name": "Violões"},
        "description": "Violão clássico com tampo em Spruce e fundo em Meranti.",
        "specs": {"strings": "nylon", "top": "Spruce", "back_sides": "Meranti"},
        "price": {"amount_cents": 59990, "currency": "BRL"},
        "availability": "available",
    }
    assert result["meta"] == {
        "snapshot_id": catalog.report["snapshot_id"],
        "returned": 1,
        "truncated": False,
    }
    _assert_no_stock_key(result)


@pytest.mark.parametrize(
    ("product_id", "availability"),
    [
        (102, "coming_soon"),
        (103, "discontinued"),
        (104, "out_of_stock"),
    ],
)
def test_details_return_status_based_availability(catalog, product_id, availability):
    result = get_product_details(product_id)

    assert result["ok"] is True
    assert result["data"]["product"]["availability"] == availability


def test_unknown_product_returns_error_without_stock(catalog):
    result = get_product_details(999)

    assert result["ok"] is False
    assert result["error"]["code"] == "PRODUCT_NOT_FOUND"
    assert result["meta"]["snapshot_id"] == catalog.report["snapshot_id"]
    _assert_no_stock_key(result)


@pytest.mark.parametrize("product_id", [0, -1, "101", True, 1.5, None])
def test_invalid_product_id_returns_invalid_argument(catalog, product_id):
    result = get_product_details(product_id)

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


@pytest.mark.parametrize(
    "specs_json",
    [
        "not valid json",
        '["nylon"]',
        "null",
        '{"strings": 1}',
        '{"strings": null}',
    ],
)
def test_corrupted_specs_json_returns_catalog_unavailable(catalog, specs_json):
    conn = sqlite3.connect(catalog.db_path)
    try:
        conn.execute(
            "UPDATE products SET specs_json = ? WHERE product_id = 101",
            (specs_json,),
        )
        conn.commit()
    finally:
        conn.close()

    result = get_product_details(101)

    assert result["ok"] is False
    assert result["error"]["code"] == "CATALOG_UNAVAILABLE"
    assert result["meta"]["snapshot_id"] == catalog.report["snapshot_id"]
    _assert_no_stock_key(result)
