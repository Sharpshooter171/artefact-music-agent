from __future__ import annotations

from pathlib import Path

SCHEMA_VERSION = "1"
DEFAULT_CATALOG_DB = Path("data/generated/catalog.sqlite")
CATALOG_DB_ENV = "EMPORIO_CATALOG_DB"

CATEGORIES_SOURCE = "desafio_tecnico_ai_eng - categories.csv"
PRODUCTS_SOURCE = "desafio_tecnico_ai_eng - products.csv"

CATEGORY_COLUMNS = ("category_id", "name", "description")
PRODUCT_COLUMNS = (
    "product_id",
    "price_brl",
    "name",
    "category_id",
    "description",
    "stock_quantity",
    "status",
    "specs",
    "created_at",
)

VALID_STATUSES = ("active", "discontinued", "coming_soon")
AVAILABILITIES = (
    "available",
    "out_of_stock",
    "coming_soon",
    "discontinued",
)
DEFAULT_SEARCH_AVAILABILITY = "available"

DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50
MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 120
MAX_CATEGORY_LENGTH = 80

INDEX_DEFINITIONS = (
    "CREATE INDEX idx_products_category_id ON products(category_id)",
    "CREATE INDEX idx_products_normalized_name ON products(normalized_name)",
    "CREATE INDEX idx_products_availability ON products(availability)",
    "CREATE INDEX idx_products_price_cents ON products(price_cents)",
)
