import hashlib
import json
from pathlib import Path

import app.catalog.importer as importer
from app.catalog.database import connect_readonly, read_metadata


def test_valid_import_loads_all_fields_and_provenance(catalog):
    report = catalog.report
    assert report["status"] == "ok"
    assert report["snapshot_id"]
    assert len(report["snapshot_id"]) == 64
    assert report["counts"]["categories"] == 4
    assert report["counts"]["products"] == 7
    assert report["counts"]["by_status"] == {
        "active": 5,
        "discontinued": 1,
        "coming_soon": 1,
    }
    assert report["counts"]["by_availability"] == {
        "available": 4,
        "out_of_stock": 1,
        "coming_soon": 1,
        "discontinued": 1,
    }
    assert report["rows_read"] == 11
    assert report["canonical_rows_loaded"] == 11
    assert all(source["size_bytes"] > 0 for source in report["source_files"])

    conn = connect_readonly(catalog.db_path)
    try:
        row = conn.execute(
            "SELECT * FROM products WHERE product_id = 101"
        ).fetchone()
        assert row["name"] == "Yamaha C40 Nylon Natural"
        assert row["normalized_name"] == "yamaha c40 nylon natural"
        assert row["category_id"] == 1
        assert row["price_cents"] == 59990
        assert row["stock_quantity"] == 5
        assert row["status"] == "active"
        assert row["availability"] == "available"
        assert row["source_file"] == "desafio_tecnico_ai_eng - products.csv"
        assert row["source_row"] == 1
        assert row["specs_json"] == (
            '{"back_sides":"Meranti","strings":"nylon","top":"Spruce"}'
        )
    finally:
        conn.close()


def test_source_bytes_unchanged_and_only_two_sources_read(
    catalog, tmp_path, build_catalog_db
):
    category_path = catalog.data_dir / "desafio_tecnico_ai_eng - categories.csv"
    product_path = catalog.data_dir / "desafio_tecnico_ai_eng - products.csv"
    before = (category_path.read_bytes(), product_path.read_bytes())

    (catalog.data_dir / "customers.csv").write_text(
        "customer_id,name\n1,Must not be read\n", encoding="utf-8"
    )
    report = build_catalog_db(catalog.data_dir, tmp_path / "generated" / "other.sqlite")

    assert report["status"] == "ok"
    assert [item["name"] for item in report["source_files"]] == [
        "desafio_tecnico_ai_eng - categories.csv",
        "desafio_tecnico_ai_eng - products.csv",
    ]
    assert (category_path.read_bytes(), product_path.read_bytes()) == before


def test_report_hashes_match_source_bytes(catalog):
    category_path = catalog.data_dir / "desafio_tecnico_ai_eng - categories.csv"
    product_path = catalog.data_dir / "desafio_tecnico_ai_eng - products.csv"
    by_name = {item["name"]: item for item in catalog.report["source_files"]}

    assert by_name[category_path.name]["sha256"] == hashlib.sha256(
        category_path.read_bytes()
    ).hexdigest()
    assert by_name[product_path.name]["sha256"] == hashlib.sha256(
        product_path.read_bytes()
    ).hexdigest()


def test_snapshot_id_matches_database_metadata(catalog):
    conn = connect_readonly(catalog.db_path)
    try:
        metadata = read_metadata(conn)
    finally:
        conn.close()

    assert metadata["snapshot_id"] == catalog.report["snapshot_id"]
    assert metadata["schema_version"] == "1"


def test_failed_import_preserves_existing_database(
    catalog,
    catalog_builder,
    build_catalog_db,
    category_row,
    product_row,
):
    original_snapshot = catalog.report["snapshot_id"]

    catalog_builder(
        catalog.data_dir,
        [category_row(1), category_row(1, "Baixos")],
        [product_row(category_id=1)],
    )
    report = build_catalog_db(catalog.data_dir, catalog.db_path)

    assert report["status"] == "failed"
    assert report["snapshot_id"] is not None
    conn = connect_readonly(catalog.db_path)
    try:
        metadata = read_metadata(conn)
    finally:
        conn.close()
    assert metadata["snapshot_id"] == original_snapshot


def test_missing_source_file_fails_without_database(
    tmp_path, build_catalog_db
):
    report = build_catalog_db(tmp_path / "empty", tmp_path / "generated" / "db.sqlite")

    assert report["status"] == "failed"
    assert report["snapshot_id"] is None
    assert "MISSING_FILE" in {issue["code"] for issue in report["rows_rejected"]}
    assert not (tmp_path / "generated" / "db.sqlite").exists()


def test_undecodable_source_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    data_dir = tmp_path / "raw"
    catalog_builder(data_dir, [category_row()], [product_row()])
    (data_dir / "desafio_tecnico_ai_eng - categories.csv").write_bytes(b"\xff\xfe")

    report = build_catalog_db(data_dir, tmp_path / "generated" / "db.sqlite")

    assert report["status"] == "failed"
    assert "DECODE_ERROR" in {issue["code"] for issue in report["rows_rejected"]}
    assert not (tmp_path / "generated" / "db.sqlite").exists()


def test_output_directory_creation_failure_returns_sanitized_report(catalog):
    blocked_parent = catalog.data_dir / "blocked-output"
    blocked_parent.write_text("not a directory", encoding="utf-8")
    output_path = blocked_parent / "catalog.sqlite"

    report = importer.build_catalog(catalog.data_dir, output_path)

    assert report["status"] == "failed"
    assert report["canonical_rows_loaded"] == 0
    assert "OUTPUT_ERROR" in {issue["code"] for issue in report["rows_rejected"]}
    assert "blocked-output" not in json.dumps(report)
    assert not output_path.exists()


def test_temp_file_creation_failure_preserves_existing_database(
    catalog, monkeypatch
):
    original_snapshot = catalog.report["snapshot_id"]

    def fail_mkstemp(*args, **kwargs):
        raise OSError("denied at /secret/temp/path")

    monkeypatch.setattr(importer.tempfile, "mkstemp", fail_mkstemp)
    report = importer.build_catalog(catalog.data_dir, catalog.db_path)

    assert report["status"] == "failed"
    assert report["canonical_rows_loaded"] == 0
    assert "OUTPUT_ERROR" in {issue["code"] for issue in report["rows_rejected"]}
    assert "/secret/temp/path" not in json.dumps(report)

    conn = connect_readonly(catalog.db_path)
    try:
        metadata = read_metadata(conn)
    finally:
        conn.close()
    assert metadata["snapshot_id"] == original_snapshot
