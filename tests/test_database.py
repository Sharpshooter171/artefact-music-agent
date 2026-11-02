import sqlite3

import pytest

from app.catalog.database import connect_readonly, read_metadata


def test_schema_contains_only_catalog_tables(catalog):
    conn = connect_readonly(catalog.db_path)
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        }
        index_names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    finally:
        conn.close()

    assert tables == {"catalog_meta", "categories", "products"}
    assert {
        "idx_products_category_id",
        "idx_products_normalized_name",
        "idx_products_availability",
        "idx_products_price_cents",
    } <= index_names


def test_schema_has_no_brand_model_or_out_of_scope_columns(catalog):
    conn = connect_readonly(catalog.db_path)
    try:
        product_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(products)")
        }
        category_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(categories)")
        }
    finally:
        conn.close()

    assert "brand" not in product_columns
    assert "model" not in product_columns
    assert "customer_id" not in product_columns
    assert "parent_category_id" not in category_columns
    assert "stock_quantity" in product_columns


def test_metadata_is_complete(catalog):
    conn = connect_readonly(catalog.db_path)
    try:
        metadata = read_metadata(conn)
    finally:
        conn.close()

    assert metadata["schema_version"] == "1"
    assert metadata["snapshot_id"] == catalog.report["snapshot_id"]
    assert len(metadata["categories_sha256"]) == 64
    assert len(metadata["products_sha256"]) == 64


def test_read_only_connection_rejects_writes(catalog):
    conn = connect_readonly(catalog.db_path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO categories (category_id, name, normalized_name, "
                "description, source_file, source_row) VALUES (99, 'X', 'x', 'X', 'x', 1)"
            )
    finally:
        conn.close()
