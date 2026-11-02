from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass

from app.catalog.constants import (
    AVAILABILITIES,
    CATEGORIES_SOURCE,
    CATEGORY_COLUMNS,
    PRODUCT_COLUMNS,
    PRODUCTS_SOURCE,
    VALID_STATUSES,
)
from app.catalog.normalization import build_search_text, normalize_text, serialize_specs
from app.catalog.rules import (
    derive_availability,
    parse_price_to_cents,
    parse_stock_quantity,
)

_ID_PATTERN = re.compile(r"^[1-9]\d*$")


@dataclass(frozen=True)
class PreparedCatalog:
    report: dict
    categories: tuple[dict, ...]
    products: tuple[dict, ...]


def validate_catalog(
    categories_text: str,
    products_text: str,
    source_hashes: dict[str, str] | None = None,
    source_sizes: dict[str, int] | None = None,
) -> PreparedCatalog:
    hashes = source_hashes or {}
    sizes = source_sizes or {}
    warnings: list[dict] = []
    rejected: list[dict] = []

    category_header, category_rows = _parse_csv(
        categories_text,
        CATEGORIES_SOURCE,
        CATEGORY_COLUMNS,
        warnings,
        rejected,
    )
    product_header, product_rows = _parse_csv(
        products_text,
        PRODUCTS_SOURCE,
        PRODUCT_COLUMNS,
        warnings,
        rejected,
    )

    categories, category_count = _prepare_categories(
        category_rows, rejected
    )
    categories_by_id = {category["category_id"]: category for category in categories}
    products, product_count = _prepare_products(
        product_rows,
        categories_by_id,
        warnings,
        rejected,
    )

    source_files = [
        {
            "name": CATEGORIES_SOURCE,
            "size_bytes": sizes.get(CATEGORIES_SOURCE, 0),
            "sha256": hashes.get(CATEGORIES_SOURCE, ""),
            "rows_read": category_count,
        },
        {
            "name": PRODUCTS_SOURCE,
            "size_bytes": sizes.get(PRODUCTS_SOURCE, 0),
            "sha256": hashes.get(PRODUCTS_SOURCE, ""),
            "rows_read": product_count,
        },
    ]

    by_status = {status: 0 for status in VALID_STATUSES}
    by_availability = {availability: 0 for availability in AVAILABILITIES}
    for product in products:
        by_status[product["status"]] += 1
        by_availability[product["availability"]] += 1

    report = {
        "status": "ok" if not rejected else "failed",
        "snapshot_id": None,
        "source_files": source_files,
        "rows_read": category_count + product_count,
        "canonical_rows_loaded": (
            0 if rejected else len(categories) + len(products)
        ),
        "counts": {
            "categories": len(categories),
            "products": len(products),
            "rows_read": category_count + product_count,
            "by_status": by_status,
            "by_availability": by_availability,
        },
        "warnings": warnings,
        "rows_rejected": rejected,
    }
    if report["status"] == "ok" or all(
        source["sha256"] for source in source_files
    ):
        report["snapshot_id"] = _snapshot_id(source_files)

    return PreparedCatalog(
        report=report,
        categories=tuple(categories),
        products=tuple(products),
    )


def _parse_csv(
    text: str,
    source_name: str,
    required_columns: tuple[str, ...],
    warnings: list[dict],
    rejected: list[dict],
) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    try:
        reader = csv.reader(io.StringIO(text), strict=True)
        raw_header = next(reader, None)
        if raw_header is None:
            rejected.append(
                _issue("MISSING_HEADER", source_name, "CSV sem cabeçalho.")
            )
            return [], []
        header = [cell.lstrip("\ufeff").strip() for cell in raw_header]
        rows = list(reader)
    except csv.Error:
        rejected.append(_issue("CSV_ERROR", source_name, "CSV inválido."))
        return [], []

    blank_header = any(not column for column in header)
    if blank_header:
        rejected.append(
            _issue("BLANK_HEADER", source_name, "Cabeçalho com coluna vazia.")
        )
    if len(header) != len(set(header)):
        rejected.append(
            _issue("DUPLICATE_HEADER", source_name, "Cabeçalho duplicado.")
        )
    missing = [column for column in required_columns if column not in header]
    if missing:
        rejected.append(
            _issue(
                "MISSING_HEADER",
                source_name,
                "Colunas obrigatórias ausentes: " + ", ".join(missing) + ".",
            )
        )
    for column in header:
        if column not in required_columns:
            warnings.append(
                _issue(
                    "EXTRA_COLUMN",
                    source_name,
                    f"Coluna extra ignorada: {column}.",
                    field=column,
                    severity="warning",
                )
            )
    if blank_header or missing or len(header) != len(set(header)):
        return header, []

    parsed_rows: list[tuple[int, dict[str, str]]] = []
    for row_number, raw_row in enumerate(rows, start=1):
        if len(raw_row) != len(header):
            rejected.append(
                _issue(
                    "ROW_FIELD_COUNT",
                    source_name,
                    "Linha com quantidade de campos diferente do cabeçalho.",
                    row=row_number,
                )
            )
            continue
        parsed_rows.append((row_number, dict(zip(header, raw_row))))
    return header, parsed_rows


def _prepare_categories(
    rows: list[tuple[int, dict[str, str]]],
    rejected: list[dict],
) -> tuple[list[dict], int]:
    records: list[dict] = []
    seen_ids: set[int] = set()
    seen_names: set[str] = set()

    for row_number, row in rows:
        category_id = _parse_id(row.get("category_id", ""), CATEGORIES_SOURCE, row_number, "category_id", rejected)
        name = row.get("name", "").strip()
        description = row.get("description", "").strip()
        if category_id is None:
            continue
        if not name:
            rejected.append(
                _issue(
                    "BLANK_FIELD",
                    CATEGORIES_SOURCE,
                    "Campo obrigatório vazio: name.",
                    row=row_number,
                    field="name",
                )
            )
            continue
        if not description:
            rejected.append(
                _issue(
                    "BLANK_FIELD",
                    CATEGORIES_SOURCE,
                    "Campo obrigatório vazio: description.",
                    row=row_number,
                    field="description",
                )
            )
            continue
        if category_id in seen_ids:
            rejected.append(
                _issue(
                    "DUPLICATE_ID",
                    CATEGORIES_SOURCE,
                    f"category_id duplicado: {category_id}.",
                    row=row_number,
                    field="category_id",
                )
            )
            continue
        normalized_name = normalize_text(name)
        if normalized_name in seen_names:
            rejected.append(
                _issue(
                    "DUPLICATE_CATEGORY_NAME",
                    CATEGORIES_SOURCE,
                    f"Nome de categoria duplicado: {name}.",
                    row=row_number,
                    field="name",
                )
            )
            continue
        seen_ids.add(category_id)
        seen_names.add(normalized_name)
        records.append(
            {
                "category_id": category_id,
                "name": name,
                "normalized_name": normalized_name,
                "description": description,
                "source_file": CATEGORIES_SOURCE,
                "source_row": row_number,
            }
        )

    records.sort(key=lambda record: record["category_id"])
    return records, len(rows)


def _prepare_products(
    rows: list[tuple[int, dict[str, str]]],
    categories_by_id: dict[int, dict],
    warnings: list[dict],
    rejected: list[dict],
) -> tuple[list[dict], int]:
    records: list[dict] = []
    seen_ids: set[int] = set()
    seen_names: set[str] = set()

    for row_number, row in rows:
        product_id = _parse_id(row.get("product_id", ""), PRODUCTS_SOURCE, row_number, "product_id", rejected)
        category_id = _parse_id(row.get("category_id", ""), PRODUCTS_SOURCE, row_number, "category_id", rejected)
        name = row.get("name", "").strip()
        description = row.get("description", "").strip()
        if product_id is None or category_id is None:
            continue
        if not name:
            rejected.append(
                _issue(
                    "BLANK_FIELD",
                    PRODUCTS_SOURCE,
                    "Campo obrigatório vazio: name.",
                    row=row_number,
                    field="name",
                )
            )
            continue
        if not description:
            rejected.append(
                _issue(
                    "BLANK_FIELD",
                    PRODUCTS_SOURCE,
                    "Campo obrigatório vazio: description.",
                    row=row_number,
                    field="description",
                )
            )
            continue
        if product_id in seen_ids:
            rejected.append(
                _issue(
                    "DUPLICATE_ID",
                    PRODUCTS_SOURCE,
                    f"product_id duplicado: {product_id}.",
                    row=row_number,
                    field="product_id",
                )
            )
            continue
        if category_id not in categories_by_id:
            rejected.append(
                _issue(
                    "ORPHAN_CATEGORY",
                    PRODUCTS_SOURCE,
                    f"Categoria inexistente: {category_id}.",
                    row=row_number,
                    field="category_id",
                )
            )
            continue

        try:
            price_cents = parse_price_to_cents(row.get("price_brl", ""))
        except ValueError:
            rejected.append(
                _issue(
                    "INVALID_PRICE",
                    PRODUCTS_SOURCE,
                    "Preço inválido.",
                    row=row_number,
                    field="price_brl",
                )
            )
            continue

        try:
            stock_quantity = parse_stock_quantity(row.get("stock_quantity", ""))
        except ValueError:
            rejected.append(
                _issue(
                    "INVALID_STOCK",
                    PRODUCTS_SOURCE,
                    "Estoque inválido.",
                    row=row_number,
                    field="stock_quantity",
                )
            )
            continue

        status = row.get("status", "").strip()
        if status not in VALID_STATUSES:
            rejected.append(
                _issue(
                    "INVALID_STATUS",
                    PRODUCTS_SOURCE,
                    "Status inválido.",
                    row=row_number,
                    field="status",
                )
            )
            continue
        try:
            availability = derive_availability(status, stock_quantity)
        except ValueError:
            rejected.append(
                _issue(
                    "INVALID_STATUS",
                    PRODUCTS_SOURCE,
                    "Status inválido.",
                    row=row_number,
                    field="status",
                )
            )
            continue

        specs = _parse_specs(row.get("specs", ""))
        if specs is None:
            rejected.append(
                _issue(
                    "INVALID_SPECS",
                    PRODUCTS_SOURCE,
                    "Especificações inválidas.",
                    row=row_number,
                    field="specs",
                )
            )
            continue

        normalized_name = normalize_text(name)
        if normalized_name in seen_names:
            warnings.append(
                _issue(
                    "DUPLICATE_PRODUCT_NAME",
                    PRODUCTS_SOURCE,
                    f"Nome de produto duplicado: {name}.",
                    row=row_number,
                    field="name",
                    severity="warning",
                )
            )
        seen_names.add(normalized_name)
        seen_ids.add(product_id)
        category_name = categories_by_id[category_id]["name"]
        records.append(
            {
                "product_id": product_id,
                "price_cents": price_cents,
                "name": name,
                "normalized_name": normalized_name,
                "category_id": category_id,
                "description": description,
                "stock_quantity": stock_quantity,
                "status": status,
                "availability": availability,
                "specs_json": serialize_specs(specs),
                "search_text": build_search_text(
                    category_name, name, description, specs
                ),
                "source_file": PRODUCTS_SOURCE,
                "source_row": row_number,
            }
        )

    records.sort(key=lambda record: record["product_id"])
    return records, len(rows)


def _parse_id(
    raw: str,
    source_name: str,
    row_number: int,
    field: str,
    rejected: list[dict],
) -> int | None:
    value = raw.strip()
    if not _ID_PATTERN.fullmatch(value):
        rejected.append(
            _issue(
                "INVALID_ID",
                source_name,
                f"Identificador inválido: {field}.",
                row=row_number,
                field=field,
            )
        )
        return None
    return int(value)


def _parse_specs(raw: str) -> dict[str, str] | None:
    if not raw.strip():
        return None
    try:
        specs = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(specs, dict):
        return None
    if not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in specs.items()
    ):
        return None
    return specs


def _snapshot_id(source_files: list[dict]) -> str:
    payload = "\n".join(
        f"{item['name']}:{item['sha256']}"
        for item in sorted(source_files, key=lambda item: item["name"])
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _issue(
    code: str,
    source_name: str,
    message: str,
    row: int | None = None,
    field: str | None = None,
    severity: str = "critical",
) -> dict:
    return {
        "code": code,
        "message": message,
        "file": source_name,
        "row": row,
        "field": field,
        "severity": severity,
    }
