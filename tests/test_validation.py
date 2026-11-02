from pathlib import Path

from app.catalog.constants import CATEGORIES_SOURCE


def _issue_codes(report: dict) -> set[str]:
    return {issue["code"] for issue in report["rows_rejected"]}


def _warning_codes(report: dict) -> set[str]:
    return {issue["code"] for issue in report["warnings"]}


def _build_report(
    tmp_path: Path,
    catalog_builder,
    build_catalog_db,
    categories,
    products,
    category_header=None,
    product_header=None,
):
    data_dir = tmp_path / "raw"
    catalog_builder(
        data_dir,
        categories,
        products,
        category_header=category_header,
        product_header=product_header,
    )
    db_path = tmp_path / "generated" / "catalog.sqlite"
    return build_catalog_db(data_dir, db_path), db_path


def _build_with_malformed_category_row(
    tmp_path: Path,
    catalog_builder,
    build_catalog_db,
    category_row,
    product_row,
    raw_row: str,
):
    data_dir = tmp_path / "raw"
    catalog_builder(data_dir, [category_row()], [product_row()])
    (data_dir / CATEGORIES_SOURCE).write_text(
        "category_id,name,description\n" + raw_row + "\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "generated" / "catalog.sqlite"
    return build_catalog_db(data_dir, db_path), db_path


def test_missing_required_header_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, db_path = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row()],
        [product_row()],
        category_header=["category_id", "name"],
    )

    assert report["status"] == "failed"
    assert "MISSING_HEADER" in _issue_codes(report)
    assert not db_path.exists()


def test_duplicate_category_id_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, _ = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row(1), category_row(1, "Baixos")],
        [product_row(category_id=1)],
    )

    assert report["status"] == "failed"
    assert "DUPLICATE_ID" in _issue_codes(report)


def test_duplicate_normalized_category_name_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, _ = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row(1, "Violões"), category_row(2, "Violoes")],
        [product_row(category_id=1)],
    )

    assert report["status"] == "failed"
    assert "DUPLICATE_CATEGORY_NAME" in _issue_codes(report)


def test_orphan_product_category_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, _ = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row()],
        [product_row(category_id=99)],
    )

    assert report["status"] == "failed"
    assert "ORPHAN_CATEGORY" in _issue_codes(report)


def test_invalid_status_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, _ = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row()],
        [product_row(status="sold_out")],
    )

    assert report["status"] == "failed"
    assert "INVALID_STATUS" in _issue_codes(report)


def test_over_precision_price_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, _ = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row()],
        [product_row(price_brl="1.234")],
    )

    assert report["status"] == "failed"
    assert "INVALID_PRICE" in _issue_codes(report)


def test_invalid_stock_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, _ = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row()],
        [product_row(stock_quantity="-1")],
    )

    assert report["status"] == "failed"
    assert "INVALID_STOCK" in _issue_codes(report)


def test_invalid_specs_json_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, _ = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row()],
        [product_row(specs='{"top": 1}')],
    )

    assert report["status"] == "failed"
    assert "INVALID_SPECS" in _issue_codes(report)


def test_blank_specs_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, _ = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row()],
        [product_row(specs="   ")],
    )

    assert report["status"] == "failed"
    assert "INVALID_SPECS" in _issue_codes(report)


def test_blank_product_name_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, _ = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row()],
        [product_row(name="   ")],
    )

    assert report["status"] == "failed"
    assert "BLANK_FIELD" in _issue_codes(report)


def test_extra_columns_are_warnings_and_import_proceeds(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    category = {**category_row(), "extra": "ignored"}
    product = {**product_row(), "extra": "ignored"}
    report, db_path = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category],
        [product],
        category_header=["category_id", "name", "description", "extra"],
        product_header=[
            "product_id",
            "price_brl",
            "name",
            "category_id",
            "description",
            "stock_quantity",
            "status",
            "specs",
            "created_at",
            "extra",
        ],
    )

    assert report["status"] == "ok"
    assert "EXTRA_COLUMN" in _warning_codes(report)
    assert db_path.exists()


def test_duplicate_product_names_are_warnings(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, db_path = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row()],
        [
            product_row(101, "Violão Clássico"),
            product_row(102, "Violao Classico"),
        ],
    )

    assert report["status"] == "ok"
    assert "DUPLICATE_PRODUCT_NAME" in _warning_codes(report)
    assert db_path.exists()


def test_blank_header_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, _ = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row()],
        [product_row()],
        category_header=["category_id", "name", "description", ""],
    )

    assert report["status"] == "failed"
    assert "BLANK_HEADER" in _issue_codes(report)


def test_duplicate_header_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, _ = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row()],
        [product_row()],
        category_header=["category_id", "name", "description", "name"],
    )

    assert report["status"] == "failed"
    assert "DUPLICATE_HEADER" in _issue_codes(report)


def test_row_with_fewer_fields_than_header_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, db_path = _build_with_malformed_category_row(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        category_row,
        product_row,
        "1,Violões",
    )

    assert report["status"] == "failed"
    assert "ROW_FIELD_COUNT" in _issue_codes(report)
    assert not db_path.exists()


def test_row_with_more_fields_than_header_fails_closed(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, db_path = _build_with_malformed_category_row(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        category_row,
        product_row,
        "1,Violões,Violões clássicos,extra",
    )

    assert report["status"] == "failed"
    assert "ROW_FIELD_COUNT" in _issue_codes(report)
    assert not db_path.exists()


def test_failed_validation_does_not_report_published_canonical_rows(
    tmp_path, catalog_builder, build_catalog_db, category_row, product_row
):
    report, db_path = _build_report(
        tmp_path,
        catalog_builder,
        build_catalog_db,
        [category_row(1), category_row(1, "Baixos")],
        [product_row(category_id=1)],
    )

    assert report["status"] == "failed"
    assert report["rows_read"] == 3
    assert report["canonical_rows_loaded"] == 0
    assert not db_path.exists()
