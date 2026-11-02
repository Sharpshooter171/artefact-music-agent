from __future__ import annotations

import re
from decimal import Decimal

from app.catalog.constants import VALID_STATUSES

_PRICE_PATTERN = re.compile(r"^(0|[1-9]\d*)(?:\.(\d{1,2}))?$")
_STOCK_PATTERN = re.compile(r"^\d+$")


def parse_price_to_cents(raw: str) -> int:
    if not isinstance(raw, str):
        raise ValueError("price must be text")
    match = _PRICE_PATTERN.fullmatch(raw.strip())
    if not match:
        raise ValueError("invalid price")
    return int(Decimal(raw.strip()) * 100)


def parse_stock_quantity(raw: str) -> int:
    if not isinstance(raw, str):
        raise ValueError("stock must be text")
    value = raw.strip()
    if not _STOCK_PATTERN.fullmatch(value):
        raise ValueError("invalid stock")
    return int(value)


def derive_availability(status: str, stock_quantity: int) -> str:
    if status not in VALID_STATUSES:
        raise ValueError("invalid status")
    if status == "coming_soon":
        return "coming_soon"
    if status == "discontinued":
        return "discontinued"
    if stock_quantity > 0:
        return "available"
    return "out_of_stock"
