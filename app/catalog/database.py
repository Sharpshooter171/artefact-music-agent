from __future__ import annotations

import sqlite3
from pathlib import Path

from app.catalog.constants import INDEX_DEFINITIONS, SCHEMA_VERSION
from app.catalog.errors import CatalogError
from app.catalog.validation import PreparedCatalog

_SCHEMA = """
CREATE TABLE catalog_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    description TEXT NOT NULL,
    stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
    status TEXT NOT NULL CHECK (status IN ('active', 'discontinued', 'coming_soon')),
    availability TEXT NOT NULL CHECK (
        availability IN ('available', 'out_of_stock', 'coming_soon', 'discontinued')
    ),
    specs_json TEXT NOT NULL,
    search_text TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL
);
"""


def create_catalog_db(path: Path, prepared: PreparedCatalog) -> None:
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": prepared.report["snapshot_id"],
    }
    for source in prepared.report["source_files"]:
        if source["name"].endswith("categories.csv"):
            metadata["categories_sha256"] = source["sha256"]
        elif source["name"].endswith("products.csv"):
            metadata["products_sha256"] = source["sha256"]

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_SCHEMA)
        for statement in INDEX_DEFINITIONS:
            conn.execute(statement)
        conn.executemany(
            """
            INSERT INTO categories (
                category_id, name, normalized_name, description,
                source_file, source_row
            ) VALUES (
                :category_id, :name, :normalized_name, :description,
                :source_file, :source_row
            )
            """,
            prepared.categories,
        )
        conn.executemany(
            """
            INSERT INTO products (
                product_id, price_cents, name, normalized_name, category_id,
                description, stock_quantity, status, availability, specs_json,
                search_text, source_file, source_row
            ) VALUES (
                :product_id, :price_cents, :name, :normalized_name, :category_id,
                :description, :stock_quantity, :status, :availability, :specs_json,
                :search_text, :source_file, :source_row
            )
            """,
            prepared.products,
        )
        conn.executemany(
            "INSERT INTO catalog_meta (key, value) VALUES (?, ?)",
            sorted(metadata.items()),
        )
        foreign_key_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if foreign_key_issues or integrity != "ok":
            raise RuntimeError("catalog integrity check failed")
        conn.commit()
    finally:
        conn.close()


def connect_readonly(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    uri = f"{path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def read_metadata(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM catalog_meta").fetchall()
    return {row["key"]: row["value"] for row in rows}


def ensure_supported_schema(conn: sqlite3.Connection) -> str:
    try:
        metadata = read_metadata(conn)
    except sqlite3.Error as exc:
        raise CatalogError("CATALOG_UNAVAILABLE", "Catálogo indisponível.") from exc

    if metadata.get("schema_version") != SCHEMA_VERSION:
        raise CatalogError("CATALOG_UNAVAILABLE", "Catálogo indisponível.")
    snapshot_id = metadata.get("snapshot_id")
    if not snapshot_id:
        raise CatalogError("CATALOG_UNAVAILABLE", "Catálogo indisponível.")
    return snapshot_id
