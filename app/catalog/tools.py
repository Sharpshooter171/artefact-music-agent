from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from app.catalog.constants import (
    AVAILABILITIES,
    CATALOG_DB_ENV,
    DEFAULT_CATALOG_DB,
    DEFAULT_SEARCH_AVAILABILITY,
    DEFAULT_SEARCH_LIMIT,
    MAX_CATEGORY_LENGTH,
    MAX_QUERY_LENGTH,
    MAX_SEARCH_LIMIT,
    MIN_QUERY_LENGTH,
)
from app.catalog.database import connect_readonly, ensure_supported_schema
from app.catalog.errors import CatalogError
from app.catalog.normalization import normalize_text, tokenize_query


def search_products(
    query: str | None = None,
    category: str | None = None,
    price_min_cents: int | None = None,
    price_max_cents: int | None = None,
    availability: str = DEFAULT_SEARCH_AVAILABILITY,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> dict:
    validation_error = _validate_search_args(
        query=query,
        category=category,
        availability=availability,
        price_min_cents=price_min_cents,
        price_max_cents=price_max_cents,
        limit=limit,
    )
    if validation_error:
        message, details = validation_error
        return _error("INVALID_ARGUMENT", message, details=details)

    effective_availability = availability
    try:
        conn, snapshot_id = _open_catalog()
    except CatalogError as exc:
        return _error(exc.code, exc.message)

    try:
        category_id = None
        if category is not None:
            row = conn.execute(
                "SELECT category_id FROM categories WHERE normalized_name = ?",
                (normalize_text(category),),
            ).fetchone()
            if row is None:
                return _error(
                    "CATEGORY_NOT_FOUND",
                    "Categoria não encontrada.",
                    snapshot_id,
                )
            category_id = row["category_id"]

        clauses = []
        parameters: list[object] = []
        if effective_availability != "any":
            clauses.append("p.availability = ?")
            parameters.append(effective_availability)
        if category_id is not None:
            clauses.append("p.category_id = ?")
            parameters.append(category_id)
        if price_min_cents is not None:
            clauses.append("p.price_cents >= ?")
            parameters.append(price_min_cents)
        if price_max_cents is not None:
            clauses.append("p.price_cents <= ?")
            parameters.append(price_max_cents)
        if query is not None:
            for token in tokenize_query(query):
                clauses.append("instr(p.search_text, ?) > 0")
                parameters.append(token)

        where_sql = " AND ".join(clauses) if clauses else "1 = 1"
        rows = conn.execute(
            f"""
            SELECT
                p.product_id,
                p.price_cents,
                p.name,
                p.category_id,
                c.name AS category_name,
                p.availability
            FROM products AS p
            JOIN categories AS c ON c.category_id = p.category_id
            WHERE {where_sql}
            ORDER BY p.normalized_name ASC, p.product_id ASC
            LIMIT ?
            """,
            (*parameters, limit + 1),
        ).fetchall()

        truncated = len(rows) > limit
        rows = rows[:limit]
        products = [
            {
                "product_id": row["product_id"],
                "name": row["name"],
                "category": {
                    "id": row["category_id"],
                    "name": row["category_name"],
                },
                "price": {
                    "amount_cents": row["price_cents"],
                    "currency": "BRL",
                },
                "availability": row["availability"],
            }
            for row in rows
        ]
        return _success(
            {"products": products},
            snapshot_id,
            returned=len(products),
            truncated=truncated,
        )
    except sqlite3.Error:
        return _error("CATALOG_UNAVAILABLE", "Catálogo indisponível.")
    except Exception:
        return _error("INTERNAL_ERROR", "Erro interno ao consultar o catálogo.")
    finally:
        conn.close()


def get_product_details(product_id: int) -> dict:
    if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id <= 0:
        return _error(
            "INVALID_ARGUMENT",
            "product_id inválido.",
            details={"field": "product_id"},
        )

    try:
        conn, snapshot_id = _open_catalog()
    except CatalogError as exc:
        return _error(exc.code, exc.message)

    try:
        row = conn.execute(
            """
            SELECT
                p.product_id,
                p.name,
                p.category_id,
                c.name AS category_name,
                p.description,
                p.specs_json,
                p.price_cents,
                p.availability
            FROM products AS p
            JOIN categories AS c ON c.category_id = p.category_id
            WHERE p.product_id = ?
            """,
            (product_id,),
        ).fetchone()
        if row is None:
            return _error(
                "PRODUCT_NOT_FOUND",
                "Produto não encontrado.",
                snapshot_id,
            )

        try:
            specs = _parse_specs(row["specs_json"])
        except CatalogError as exc:
            return _error(exc.code, exc.message, snapshot_id)

        return _success(
            {
                "product": {
                    "product_id": row["product_id"],
                    "name": row["name"],
                    "category": {
                        "id": row["category_id"],
                        "name": row["category_name"],
                    },
                    "description": row["description"],
                    "specs": specs,
                    "price": {
                        "amount_cents": row["price_cents"],
                        "currency": "BRL",
                    },
                    "availability": row["availability"],
                }
            },
            snapshot_id,
            returned=1,
            truncated=False,
        )
    except sqlite3.Error:
        return _error("CATALOG_UNAVAILABLE", "Catálogo indisponível.")
    except Exception:
        return _error("INTERNAL_ERROR", "Erro interno ao consultar o catálogo.")
    finally:
        conn.close()


def list_categories() -> dict:
    try:
        conn, snapshot_id = _open_catalog()
    except CatalogError as exc:
        return _error(exc.code, exc.message)

    try:
        rows = conn.execute(
            """
            SELECT
                c.category_id,
                c.name,
                c.description,
                COUNT(p.product_id) AS product_count
            FROM categories AS c
            LEFT JOIN products AS p ON p.category_id = c.category_id
            GROUP BY c.category_id
            ORDER BY c.normalized_name ASC, c.category_id ASC
            """
        ).fetchall()
        categories = [
            {
                "category_id": row["category_id"],
                "name": row["name"],
                "description": row["description"],
                "product_count": row["product_count"],
            }
            for row in rows
        ]
        return _success(
            {"categories": categories},
            snapshot_id,
            returned=len(categories),
            truncated=False,
        )
    except sqlite3.Error:
        return _error("CATALOG_UNAVAILABLE", "Catálogo indisponível.")
    except Exception:
        return _error("INTERNAL_ERROR", "Erro interno ao consultar o catálogo.")
    finally:
        conn.close()


def _validate_search_args(
    *,
    query: str | None,
    category: str | None,
    availability: str,
    price_min_cents: int | None,
    price_max_cents: int | None,
    limit: int,
) -> tuple[str, dict] | None:
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 1
        or limit > MAX_SEARCH_LIMIT
    ):
        return "limit inválido.", {"field": "limit"}

    if query is not None:
        if not isinstance(query, str):
            return "query inválida.", {"field": "query"}
        if len(query.strip()) < MIN_QUERY_LENGTH or len(query.strip()) > MAX_QUERY_LENGTH:
            return "query inválida.", {"field": "query"}
        if not normalize_text(query):
            return "query inválida.", {"field": "query"}

    if category is not None:
        if not isinstance(category, str):
            return "category inválida.", {"field": "category"}
        if not category.strip() or len(category.strip()) > MAX_CATEGORY_LENGTH:
            return "category inválida.", {"field": "category"}

    if not isinstance(availability, str) or availability not in AVAILABILITIES + ("any",):
        return "availability inválida.", {"field": "availability"}

    if price_min_cents is not None and (
        not isinstance(price_min_cents, int)
        or isinstance(price_min_cents, bool)
        or price_min_cents < 0
    ):
        return "price inválido.", {"field": "price_min_cents"}
    if price_max_cents is not None and (
        not isinstance(price_max_cents, int)
        or isinstance(price_max_cents, bool)
        or price_max_cents < 0
    ):
        return "price inválido.", {"field": "price_max_cents"}
    if (
        price_min_cents is not None
        and price_max_cents is not None
        and price_min_cents > price_max_cents
    ):
        return "price inválido.", {"field": "price_max_cents"}

    if all(value is None for value in (query, category, price_min_cents, price_max_cents)):
        return "Informe um termo, categoria ou faixa de preço.", {"field": None}
    return None


def _parse_specs(raw_specs: object) -> dict[str, str]:
    try:
        specs = json.loads(raw_specs)
    except (TypeError, json.JSONDecodeError) as exc:
        raise CatalogError("CATALOG_UNAVAILABLE", "Catálogo indisponível.") from exc

    if not isinstance(specs, dict) or not all(
        isinstance(value, str) for value in specs.values()
    ):
        raise CatalogError("CATALOG_UNAVAILABLE", "Catálogo indisponível.")
    return specs


def _open_catalog():
    path = Path(os.environ.get(CATALOG_DB_ENV, str(DEFAULT_CATALOG_DB)))
    conn = None
    try:
        conn = connect_readonly(path)
        snapshot_id = ensure_supported_schema(conn)
        return conn, snapshot_id
    except CatalogError:
        if conn is not None:
            conn.close()
        raise
    except Exception as exc:
        if conn is not None:
            conn.close()
        raise CatalogError("CATALOG_UNAVAILABLE", "Catálogo indisponível.") from exc


def _success(
    data: dict,
    snapshot_id: str,
    *,
    returned: int | None = None,
    truncated: bool | None = None,
) -> dict:
    meta = {"snapshot_id": snapshot_id}
    if returned is not None:
        meta["returned"] = returned
    if truncated is not None:
        meta["truncated"] = truncated
    return {"ok": True, "data": data, "meta": meta}


def _error(
    code: str,
    message: str,
    snapshot_id: str | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "meta": {"snapshot_id": snapshot_id},
    }
