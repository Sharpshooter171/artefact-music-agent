from app.catalog.database import connect_readonly
from app.catalog.tools import get_product_details, list_categories, search_products


def _canonical_rows(db_path):
    conn = connect_readonly(db_path)
    try:
        products = [
            tuple(row)
            for row in conn.execute(
                "SELECT product_id, price_cents, name, category_id, description, "
                "status, availability, specs_json, normalized_name, search_text, "
                "source_file, source_row FROM products ORDER BY product_id"
            )
        ]
        categories = [
            tuple(row)
            for row in conn.execute(
                "SELECT category_id, name, normalized_name, description, "
                "source_file, source_row FROM categories ORDER BY category_id"
            )
        ]
    finally:
        conn.close()
    return products, categories


def test_repeated_imports_from_same_sources_are_identical(
    tmp_path, catalog, build_catalog_db
):
    second = build_catalog_db(catalog.data_dir, tmp_path / "generated" / "second.sqlite")
    third = build_catalog_db(catalog.data_dir, tmp_path / "generated" / "third.sqlite")

    assert second["snapshot_id"] == catalog.report["snapshot_id"]
    assert third["snapshot_id"] == catalog.report["snapshot_id"]
    assert second["counts"] == catalog.report["counts"]
    assert _canonical_rows(catalog.db_path) == _canonical_rows(
        tmp_path / "generated" / "second.sqlite"
    )


def test_tool_results_are_reproducible_for_the_same_snapshot(catalog):
    first = search_products(query="violao", limit=50)
    second = search_products(query="violao", limit=50)

    assert first == second
    assert first["meta"]["snapshot_id"] == catalog.report["snapshot_id"]
    assert get_product_details(101) == get_product_details(101)
    assert list_categories() == list_categories()
