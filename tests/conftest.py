from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
CATEGORY_HEADER = ["category_id", "name", "description"]
PRODUCT_HEADER = [
    "product_id",
    "price_brl",
    "name",
    "category_id",
    "description",
    "stock_quantity",
    "status",
    "specs",
    "created_at",
]


def read_fixture_rows(dataset: str, filename: str) -> list[dict[str, str]]:
    path = FIXTURE_ROOT / dataset / filename
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_catalog(
    data_dir: Path,
    categories: list[dict[str, str]],
    products: list[dict[str, str]],
    category_header: list[str] | None = None,
    product_header: list[str] | None = None,
) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_rows(
        data_dir / "desafio_tecnico_ai_eng - categories.csv",
        category_header or CATEGORY_HEADER,
        categories,
    )
    _write_rows(
        data_dir / "desafio_tecnico_ai_eng - products.csv",
        product_header or PRODUCT_HEADER,
        products,
    )


def _write_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in rows:
            writer.writerow([row.get(column, "") for column in header])


def make_category_row(
    category_id: str | int = 1,
    name: str = "Violões",
    description: str = "Violões clássicos e acústicos",
) -> dict[str, str]:
    return {
        "category_id": str(category_id),
        "name": name,
        "description": description,
    }


def make_product_row(
    product_id: str | int = 101,
    name: str = "Yamaha C40 Nylon Natural",
    category_id: str | int = 1,
    price_brl: str = "599.9",
    description: str = "Violão clássico com tampo em Spruce e fundo em Meranti.",
    stock_quantity: str | int = 5,
    status: str = "active",
    specs: str = '{"top":"Spruce","back_sides":"Meranti"}',
    created_at: str = "2021-03-15",
) -> dict[str, str]:
    return {
        "product_id": str(product_id),
        "price_brl": str(price_brl),
        "name": name,
        "category_id": str(category_id),
        "description": description,
        "stock_quantity": str(stock_quantity),
        "status": status,
        "specs": specs,
        "created_at": created_at,
    }


@pytest.fixture
def catalog_builder():
    return write_catalog


@pytest.fixture
def category_row():
    return make_category_row


@pytest.fixture
def product_row():
    return make_product_row


@pytest.fixture
def build_catalog_db():
    def _build(data_dir: Path, db_path: Path) -> dict:
        from app.catalog.importer import build_catalog

        return build_catalog(data_dir=data_dir, output=db_path)

    return _build


@pytest.fixture
def catalog(tmp_path, monkeypatch, catalog_builder, build_catalog_db):
    data_dir = tmp_path / "raw"
    catalog_builder(
        data_dir,
        read_fixture_rows("catalog_valid", "categories.csv"),
        read_fixture_rows("catalog_valid", "products.csv"),
    )
    db_path = tmp_path / "generated" / "catalog.sqlite"
    report = build_catalog_db(data_dir, db_path)
    assert report["status"] == "ok"
    monkeypatch.setenv("EMPORIO_CATALOG_DB", str(db_path))
    return SimpleNamespace(data_dir=data_dir, db_path=db_path, report=report)


@pytest.fixture
def edge_catalog(tmp_path, monkeypatch, catalog_builder, build_catalog_db):
    data_dir = tmp_path / "raw"
    catalog_builder(
        data_dir,
        read_fixture_rows("catalog_edge", "categories.csv"),
        read_fixture_rows("catalog_edge", "products.csv"),
    )
    db_path = tmp_path / "generated" / "catalog.sqlite"
    report = build_catalog_db(data_dir, db_path)
    assert report["status"] == "ok"
    monkeypatch.setenv("EMPORIO_CATALOG_DB", str(db_path))
    return SimpleNamespace(data_dir=data_dir, db_path=db_path, report=report)
