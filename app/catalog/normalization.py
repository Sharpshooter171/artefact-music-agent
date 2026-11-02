from __future__ import annotations

import json
import unicodedata
from typing import Any


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().split())


def tokenize_query(query: str) -> list[str]:
    normalized = normalize_text(query)
    return normalized.split() if normalized else []


def build_search_text(
    category_name: str,
    product_name: str,
    description: str,
    specs: dict[str, str],
) -> str:
    spec_values = [str(value) for _, value in sorted(specs.items())]
    return normalize_text(
        " ".join((category_name, product_name, description, *spec_values))
    )


def serialize_specs(specs: dict[str, Any]) -> str:
    return json.dumps(
        specs,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
