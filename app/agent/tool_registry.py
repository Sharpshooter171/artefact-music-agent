"""Static schemas and a validated, read-only boundary for model tool calls."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

from app.agent import worker_process
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
MAX_TOOL_IPC_INPUT = 16 * 1024
MAX_TOOL_IPC_OUTPUT = 128 * 1024
_WORKER_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TZ")
_MAX_SQLITE_INTEGER = 2**63 - 1
# Fixed codes emitted by this adapter and the existing catalog/policy tools.
# Unrecognized tool text must never become a diagnostic.
TOOL_ERROR_CODES = frozenset({
    "INVALID_ARGUMENT", "UNKNOWN_TOOL", "CATEGORY_NOT_FOUND", "PRODUCT_NOT_FOUND",
    "CATALOG_UNAVAILABLE", "POLICY_UNAVAILABLE", "WORKER_PROTOCOL_ERROR",
    "TOOL_OUTPUT_TOO_LARGE", "TOOL_FAILURE",
})


def safe_tool_error_code(result: object) -> str:
    error = result.get("error") if isinstance(result, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) and code in TOOL_ERROR_CODES else "TOOL_FAILURE"


class ToolWorkerError(Exception):
    """Sanitized tool-worker failure; only a fixed code is exposed."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Consulta local indisponível ({code}).")


def _tool_worker_command():
    """Absolute script path and isolated imports; no arguments or secrets in argv."""
    return [sys.executable, "-I", str(Path(__file__).with_name("tool_worker.py").resolve())]


def _tool_worker_env():
    """Inherit only artifact paths and harmless process essentials, never credentials."""
    env = {name: os.environ[name] for name in _WORKER_ENV_KEYS if name in os.environ}
    for name in ("EMPORIO_CATALOG_DB", "EMPORIO_POLICY_INDEX"):
        if name in os.environ:
            env[name] = os.environ[name]
    env["PYTHONIOENCODING"] = "utf-8"
    return env


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
        "Para orçamento, recomendação, disponibilidade ou comparar preços, busque diretamente "
        "com price_max_cents em centavos; não precisa listar categorias antes. "
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
        "Use para descobrir categorias e visão geral, não como etapa obrigatória para orçamento. "
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


def parse_and_validate_arguments(name: str, arguments: str) -> tuple[dict | None, str | None]:
    """Apply the exact dispatch contract used by ToolRegistry without executing a tool."""
    if not isinstance(name, str) or name not in _PARAMETERS:
        return None, "UNKNOWN_TOOL"
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
        return None, "INVALID_ARGUMENT"
    return params, None


class ToolRegistry:
    """Only these four explicitly imported functions can be invoked."""

    @property
    def schemas(self) -> list[dict]:
        return deepcopy(TOOL_SCHEMAS)

    def dispatch(self, name: str, arguments: str) -> dict:
        params, code = parse_and_validate_arguments(name, arguments)
        if code is not None:
            return _error(code)

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

    def dispatch_with_deadline(self, name: str, arguments: str, deadline) -> dict:
        """Run the same read-only dispatch in a temporary killable process."""
        if deadline is None or deadline.expired:
            raise ToolWorkerError("TURN_DEADLINE_EXCEEDED")
        if not isinstance(name, str) or name not in _PARAMETERS:
            return _error("UNKNOWN_TOOL")
        try:
            if not isinstance(arguments, str) or len(arguments.encode("utf-8")) > MAX_ARGUMENT_BYTES:
                return _error("INVALID_ARGUMENT")
            packet = json.dumps(
                {"name": name, "arguments": arguments},
                ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
            if len(packet) > MAX_TOOL_IPC_INPUT:
                return _error("INVALID_ARGUMENT")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return _error("INVALID_ARGUMENT")
        return _run_tool_worker(packet, deadline)


def _run_tool_worker(packet: bytes, deadline) -> dict:
    process = None
    mask = worker_process.block_spawn_signals()
    try:
        try:
            process = subprocess.Popen(
                _tool_worker_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env=_tool_worker_env(),
                # Inherit caller cwd so relative artifact paths match CLI preflight
                # and direct dispatch. Script and import roots are already absolute.
                start_new_session=True,
            )
        finally:
            # A queued turn alarm is delivered here, after the child has an owner.
            worker_process.restore_spawn_signals(mask)
        try:
            output = worker_process.supervise_pipe(
                process, packet, deadline, MAX_TOOL_IPC_OUTPUT,
            )
        except worker_process.WorkerDeadlineExceeded:
            raise ToolWorkerError("TURN_DEADLINE_EXCEEDED") from None
        except worker_process.WorkerOutputTooLarge:
            return _error("TOOL_OUTPUT_TOO_LARGE")
        except worker_process.WorkerProtocolError:
            return _error("WORKER_PROTOCOL_ERROR")
        if process.returncode != 0:
            return _error("WORKER_PROTOCOL_ERROR")
        try:
            lines = output.splitlines()
            if len(lines) != 1:
                raise ValueError
            result = json.loads(lines[0], object_pairs_hook=_unique_keys,
                                parse_constant=_invalid_constant)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return _error("WORKER_PROTOCOL_ERROR")
        if not isinstance(result, dict) or type(result.get("ok")) is not bool:
            return _error("WORKER_PROTOCOL_ERROR")
        if result["ok"] is False:
            error = result.get("error")
            if not isinstance(error, dict) or not isinstance(error.get("code"), str):
                return _error("WORKER_PROTOCOL_ERROR")
            return _error(safe_tool_error_code(result))
        return result
    except OSError:
        # A failed worker launch/pipe cannot yield a valid tool protocol response.
        return _error("WORKER_PROTOCOL_ERROR")
    finally:
        # Covers all paths, including a signal delivered during spawn restore.
        worker_process.terminate(process)


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
