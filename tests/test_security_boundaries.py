import json
import sqlite3

from app.catalog.tools import get_product_details, list_categories, search_products


def _message(result: dict) -> str:
    return result["error"]["message"]


def _assert_sanitized(message: str, *forbidden: str) -> None:
    lowered = message.lower()
    assert "select" not in lowered
    assert "traceback" not in lowered
    assert "sqlite" not in lowered
    for item in forbidden:
        assert str(item) not in message


def test_missing_database_returns_catalog_unavailable(tmp_path, monkeypatch):
    missing = tmp_path / "does-not-exist.sqlite"
    monkeypatch.setenv("EMPORIO_CATALOG_DB", str(missing))

    result = search_products(query="violao")

    assert result["ok"] is False
    assert result["error"]["code"] == "CATALOG_UNAVAILABLE"
    _assert_sanitized(_message(result), str(tmp_path))


def test_corrupt_database_returns_catalog_unavailable(tmp_path, monkeypatch):
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"this is not a sqlite database")
    monkeypatch.setenv("EMPORIO_CATALOG_DB", str(corrupt))

    result = list_categories()

    assert result["ok"] is False
    assert result["error"]["code"] == "CATALOG_UNAVAILABLE"
    _assert_sanitized(_message(result), str(tmp_path))


def test_unsupported_schema_version_is_unavailable(catalog):
    conn = sqlite3.connect(catalog.db_path)
    try:
        conn.execute("UPDATE catalog_meta SET value = '999' WHERE key = 'schema_version'")
        conn.commit()
    finally:
        conn.close()

    result = get_product_details(101)

    assert result["ok"] is False
    assert result["error"]["code"] == "CATALOG_UNAVAILABLE"


def test_tool_errors_do_not_leak_paths_or_sql(catalog):
    results = [
        search_products(query="a"),
        search_products(category="Pianos"),
        get_product_details(999),
    ]

    for result in results:
        assert result["ok"] is False
        _assert_sanitized(_message(result), str(catalog.db_path), str(catalog.data_dir))


def test_public_tools_return_json_serializable_payloads(catalog):
    results = [
        search_products(query="violao"),
        get_product_details(101),
        list_categories(),
    ]

    for result in results:
        assert json.loads(json.dumps(result)) == result


def test_catalog_contains_no_out_of_scope_tables(catalog):
    conn = sqlite3.connect(catalog.db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    finally:
        conn.close()

    assert not {
        "customers",
        "orders",
        "order_items",
        "promotions",
        "users",
    } & tables
