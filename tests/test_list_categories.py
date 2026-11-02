from app.catalog.tools import list_categories


def test_list_categories_counts_all_availability_states(catalog):
    result = list_categories()

    assert result["ok"] is True
    assert result["data"]["categories"] == [
        {
            "category_id": 4,
            "name": "Cordas Orquestrais",
            "description": "Violinos e violoncelos",
            "product_count": 0,
        },
        {
            "category_id": 3,
            "name": "Instrumentos de Sopro (Madeiras)",
            "description": "Flautas e clarinetes",
            "product_count": 1,
        },
        {
            "category_id": 2,
            "name": "Ukuleles",
            "description": "Ukuleles soprano e barítono",
            "product_count": 2,
        },
        {
            "category_id": 1,
            "name": "Violões",
            "description": "Violões clássicos e acústicos",
            "product_count": 4,
        },
    ]
    assert result["meta"] == {
        "snapshot_id": catalog.report["snapshot_id"],
        "returned": 4,
        "truncated": False,
    }


def test_list_categories_does_not_expose_stock_or_mutable_data(catalog):
    result = list_categories()

    for category in result["data"]["categories"]:
        assert "stock_quantity" not in category
        assert "stock" not in category


def test_list_categories_exact_public_schema(catalog):
    result = list_categories()

    assert set(result) == {"ok", "data", "meta"}
    assert set(result["data"]) == {"categories"}
    assert set(result["meta"]) == {"snapshot_id", "returned", "truncated"}
    assert all(
        set(category)
        == {"category_id", "name", "description", "product_count"}
        for category in result["data"]["categories"]
    )
