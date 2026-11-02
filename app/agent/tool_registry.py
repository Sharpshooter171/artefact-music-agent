"""Static schemas and a validated, read-only boundary for model tool calls."""

from __future__ import annotations

from copy import deepcopy
import json

from app.catalog import tools as catalog_tools
from app.catalog.constants import (
    AVAILABILITIES,
    MAX_CATEGORY_LENGTH,
    MAX_QUERY_LENGTH,
    MAX_SEARCH_LIMIT,
    MIN_QUERY_LENGTH,
)
from app.policy import tools as policy_tools


MAX_ARGUMENT_BYTES = 4096
_MAX_SQLITE_INTEGER = 2**63 - 1


def _function(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object", "properties": properties,
                "required": required, "additionalProperties": False,
            },
        },
    }


TOOL_SCHEMAS = [
    _function(
        "search_products",
        "Consulte instrumentos no catálogo local (snapshot, não estoque ao vivo). "
        "Use termo de instrumento ou categoria exata; evite plurais se não houver resultado. "
        "Filtros de preço são centavos inteiros de BRL. O padrão retorna somente disponíveis. "
        "Informe ao menos query, category ou faixa de preço. Não informe limite alto sem necessidade.",
        {
            "query": {"type": ["string", "null"], "minLength": MIN_QUERY_LENGTH, "maxLength": MAX_QUERY_LENGTH},
            "category": {"type": ["string", "null"], "minLength": 1, "maxLength": MAX_CATEGORY_LENGTH},
            "price_min_cents": {"type": ["integer", "null"], "minimum": 0, "maximum": _MAX_SQLITE_INTEGER},
            "price_max_cents": {"type": ["integer", "null"], "minimum": 0, "maximum": _MAX_SQLITE_INTEGER},
            "availability": {"type": "string", "enum": [*AVAILABILITIES, "any"], "default": "available"},
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_SEARCH_LIMIT, "default": 10},
        },
        [],
    ),
    _function(
        "get_product_details",
        "Consulte descrição, especificações, preço e disponibilidade de um instrumento "
        "pelo product_id retornado pelo catálogo. Nunca invente IDs ou quantidades de estoque.",
        {"product_id": {"type": "integer", "minimum": 1, "maximum": _MAX_SQLITE_INTEGER}},
        ["product_id"],
    ),
    _function(
        "list_categories",
        "Liste categorias de instrumentos do catálogo e contagem de produtos cadastrados "
        "por categoria. Essa contagem não representa unidades em estoque.",
        {},
        [],
    ),
    _function(
        "search_store_policies",
        "Consulte o manual da loja para PIX, pagamentos, descontos, horários, entrega, "
        "troca, garantia e contato. Use uma pergunta curta em português. Preserve cautions, "
        "contradições e páginas; o manual não prova campanhas ativas.",
        {
            "query": {"type": "string", "minLength": 3, "maxLength": 240},
            "limit": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
        },
        ["query"],
    ),
]

_PARAMETERS = {
    tool["function"]["name"]: deepcopy(tool["function"]["parameters"])
    for tool in TOOL_SCHEMAS
}


class ToolRegistry:
    """Only these four explicitly imported functions can be invoked."""

    @property
    def schemas(self) -> list[dict]:
        return deepcopy(TOOL_SCHEMAS)

    def dispatch(self, name: str, arguments: str) -> dict:
        if not isinstance(name, str) or name not in _PARAMETERS:
            return _error("UNKNOWN_TOOL")
        try:
            if not isinstance(arguments, str) or len(arguments.encode("utf-8")) > MAX_ARGUMENT_BYTES:
                raise ValueError
            params = json.loads(
                arguments,
                object_pairs_hook=_unique_keys,
                parse_constant=_invalid_constant,
            )
            _validate(name, params)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return _error("INVALID_ARGUMENT")

        # Do not derive Python imports, attributes or executable SQL from model text.
        functions = {
            "search_products": catalog_tools.search_products,
            "get_product_details": catalog_tools.get_product_details,
            "list_categories": catalog_tools.list_categories,
            "search_store_policies": policy_tools.search_store_policies,
        }
        try:
            result = functions[name](**params)
            if not isinstance(result, dict) or type(result.get("ok")) is not bool:
                return _error("TOOL_FAILURE")
            return result
        except Exception:
            return _error("TOOL_FAILURE")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError
        values[key] = value
    return values


def _invalid_constant(value: str) -> None:
    raise ValueError


def _validate(name: str, params: object) -> None:
    spec = _PARAMETERS[name]
    if not isinstance(params, dict):
        raise ValueError
    properties = spec["properties"]
    if params.keys() - properties.keys() or not set(spec["required"]) <= params.keys():
        raise ValueError
    for field, value in params.items():
        rule = properties[field]
        types = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
        if value is None and "null" in types:
            continue
        if "integer" in types and type(value) is int:
            if not rule["minimum"] <= value <= rule["maximum"]:
                raise ValueError
        elif "string" in types and isinstance(value, str):
            if "enum" in rule:
                if value not in rule["enum"]:
                    raise ValueError
            elif not rule["minLength"] <= len(value.strip()) <= rule["maxLength"]:
                raise ValueError
            if field == "query" and not any(char.isalnum() for char in value):
                raise ValueError
        else:
            raise ValueError
    if name == "search_products":
        if all(params.get(field) is None for field in ("query", "category", "price_min_cents", "price_max_cents")):
            raise ValueError
        minimum, maximum = params.get("price_min_cents"), params.get("price_max_cents")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError


def _error(code: str) -> dict:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": "Não foi possível consultar essa informação. Consulte a equipe da loja.",
            "details": {},
        },
        "meta": {},
    }
