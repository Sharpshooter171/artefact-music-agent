import pytest

from app.catalog.tools import search_products


def _ids(result: dict) -> list[int]:
    return [product["product_id"] for product in result["data"]["products"]]


def test_default_search_returns_only_available_products_in_stable_order(catalog):
    result = search_products(category="Violões", limit=50)

    assert result["ok"] is True
    assert _ids(result) == [106, 101]
    assert result["meta"] == {
        "snapshot_id": catalog.report["snapshot_id"],
        "returned": 2,
        "truncated": False,
    }
    first = result["data"]["products"][0]
    assert first["name"] == "Tagima TW-73"
    assert first["category"] == {"id": 1, "name": "Violões"}
    assert first["price"] == {"amount_cents": 120000, "currency": "BRL"}
    assert first["availability"] == "available"
    assert "stock_quantity" not in first


def test_category_filter_is_independent_of_product_names(catalog):
    default = search_products(category="Ukuleles", limit=50)
    any_status = search_products(
        category="Ukuleles", availability="any", limit=50
    )

    assert _ids(default) == [105]
    assert _ids(any_status) == [102, 105]
    assert all("ukulele" not in product["name"].lower() for product in any_status["data"]["products"])


def test_category_lookup_is_case_and_accent_insensitive(catalog):
    result = search_products(category="violoes", limit=50)
    assert _ids(result) == [106, 101]


def test_public_signature_accepts_documented_positional_order(catalog):
    result = search_products("violao", "Violões", None, None, "any", 2)

    assert _ids(result) == [104, 101]


def test_zero_product_category_returns_successful_empty_result(catalog):
    result = search_products(category="Cordas Orquestrais")

    assert result["ok"] is True
    assert result["data"] == {"products": []}
    assert result["meta"]["returned"] == 0
    assert result["meta"]["truncated"] is False


def test_unknown_category_returns_error(catalog):
    result = search_products(category="Pianos")

    assert result["ok"] is False
    assert result["error"]["code"] == "CATEGORY_NOT_FOUND"
    assert result["meta"]["snapshot_id"] == catalog.report["snapshot_id"]


def test_multi_token_text_search_requires_every_token(catalog):
    assert _ids(search_products(query="violao classico", availability="any")) == [101]
    assert _ids(search_products(query="yamaha c40")) == [101]
    assert _ids(search_products(query="yamaha bass")) == []


def test_description_and_spec_searches_are_literal_and_grounded(catalog):
    assert _ids(search_products(query="meranti")) == [101]
    assert _ids(search_products(query="cedro solido")) == [105]
    assert _ids(search_products(query="captacao split-coil")) == []
    assert _ids(
        search_products(query="captacao split-coil", availability="any")
    ) == [103]


def test_price_filters_are_inclusive(catalog):
    assert _ids(search_products(category="Violões", price_min_cents=60000)) == [106]
    assert _ids(search_products(category="Violões", price_max_cents=59990)) == [101]
    assert _ids(
        search_products(
            category="Violões", price_min_cents=59990, price_max_cents=120000
        )
    ) == [106, 101]
    assert _ids(
        search_products(
            category="Violões", price_min_cents=59990, price_max_cents=59990
        )
    ) == [101]


def test_availability_filters_are_exact(catalog):
    assert _ids(
        search_products(category="Violões", availability="out_of_stock", limit=50)
    ) == [104]
    assert _ids(
        search_products(category="Violões", availability="discontinued", limit=50)
    ) == [103]
    assert _ids(
        search_products(category="Violões", availability="coming_soon", limit=50)
    ) == []
    assert _ids(
        search_products(category="Violões", availability="any", limit=50)
    ) == [104, 103, 106, 101]


def test_limit_and_truncation(catalog):
    one = search_products(category="Violões", limit=1)
    two = search_products(category="Violões", limit=2)

    assert _ids(one) == [106]
    assert one["meta"]["truncated"] is True
    assert _ids(two) == [106, 101]
    assert two["meta"]["truncated"] is False


def test_unfiltered_catalog_dump_is_rejected(catalog):
    result = search_products()

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"
    assert result["meta"]["snapshot_id"] is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"query": "a"},
        {"query": "   "},
        {"query": "ok", "limit": 0},
        {"query": "ok", "limit": 51},
        {"query": "ok", "limit": True},
        {"query": "ok", "availability": "maybe"},
        {"query": "ok", "category": ""},
        {"query": "ok", "price_min_cents": -1},
        {"query": "ok", "price_min_cents": 10, "price_max_cents": 5},
        {"query": 123},
        {"category": ["Violões"]},
    ],
)
def test_invalid_arguments_return_invalid_argument(catalog, kwargs):
    result = search_products(**kwargs)

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_literal_wildcards_and_injection_like_text_are_not_expanded(edge_catalog):
    assert _ids(search_products(query="100%")) == [203]
    assert _ids(search_products(query="%%")) == []
    assert _ids(search_products(query="x' OR 1=1 --", availability="any")) == []
