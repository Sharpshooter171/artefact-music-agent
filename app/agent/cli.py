"""Small local pt-BR terminal interface. Imports never contact a provider."""

from __future__ import annotations

import argparse

from app.agent.config import Config, ConfigError
from app.agent.llm_client import ChatClient
from app.agent.orchestrator import Orchestrator, safe_milliseconds, safe_model_identity
from app.agent.tool_registry import TOOL_ERROR_CODES
from app.catalog.tools import list_categories
from app.policy.tools import search_store_policies


_TOOLS = frozenset({
    "search_products", "get_product_details", "list_categories", "search_store_policies",
})
_ERRORS = frozenset({
    "RATE_LIMITED", "HTTP_ERROR", "AUTH_ERROR", "PROVIDER_UNAVAILABLE",
    "PROVIDER_ERROR", "NETWORK_ERROR", "TIMEOUT", "MALFORMED_RESPONSE",
    "INVALID_RESPONSE", "RESPONSE_TOO_LARGE", "UNEXPECTED_MODEL", "PAID_RESPONSE",
    "UNKNOWN_TOOL", "INVALID_ARGUMENT", "INVALID_ARGUMENTS", "TOOL_ERROR",
    "INTERNAL_ERROR", "CATALOG_UNAVAILABLE", "POLICY_UNAVAILABLE",
    "BUDGET_EXHAUSTED", "REQUEST_LIMIT", "TOOL_LIMIT", "TOOL_OUTPUT_LIMIT",
    "INPUT_TOO_LONG", "UNGROUNDED_RESPONSE", "EMPTY_RESPONSE", "INVALID_TOOL_CALL",
    "LOOP_LIMIT", "GROUNDING_FAILED", "NO_EVIDENCE", "LIMIT_EXCEEDED",
    "TOOL_FAILURE", "BUDGET_EXCEEDED", "INVALID_INPUT",
    "PROVIDER_TIMEOUT", "REQUEST_TOO_LARGE", "PROVIDER_REJECTED",
    "UNAUTHORIZED_RESPONSE_MODEL", "INVALID_PROVIDER_COST", "NONZERO_PROVIDER_COST",
    "INCOMPLETE_RESPONSE", "UNSAFE_RESPONSE", "PROVIDER_RATE_LIMIT",
    "PROVIDER_AUTH", "PROVIDER_REDIRECT", "PROVIDER_HTTP_ERROR",
    "REQUEST_DEADLINE_EXCEEDED", "TURN_DEADLINE_EXCEEDED", "TURN_DEADLINE_UNAVAILABLE",
    "WORKER_PROTOCOL_ERROR",
}) | TOOL_ERROR_CODES


def _artifacts_ready() -> bool:
    """Use the existing tools so configured paths and validation stay authoritative."""
    catalog_ok = list_categories().get("ok") is True
    policy_ok = search_store_policies("horário", limit=1).get("ok") is True
    if not catalog_ok:
        print("Catálogo local ausente ou inválido. Gere o catálogo com:")
        print(".venv/bin/python -m scripts.build_catalog --data-dir data/raw --output data/generated/catalog.sqlite")
    if not policy_ok:
        print("Índice de políticas ausente ou inválido. Gere o índice com:")
        print(".venv/bin/python -m scripts.build_policy_index --input 'resources/políticas_da_loja.pdf' --output data/generated/policy_index.json")
    return catalog_ok and policy_ok


def _print_debug(agent: Orchestrator) -> None:
    """Never interpolate arbitrary provider/tool content in diagnostic output."""
    trace = getattr(agent, "last_trace", [])
    for event in trace[:6] if isinstance(trace, list) else []:
        if isinstance(event, str):
            name, code = event, None
        elif isinstance(event, dict):
            name = event.get("tool", event.get("name"))
            code = event.get("error_code")
        else:
            continue
        if isinstance(name, str) and name in _TOOLS:
            print(f"[ferramenta: {name}]")
        if isinstance(code, str) and code in _ERRORS:
            print(f"[erro: {code}]")
    tool_diagnostics = getattr(agent, "last_tool_diagnostics", [])
    for event in tool_diagnostics[:6] if isinstance(tool_diagnostics, list) else []:
        if not isinstance(event, dict):
            continue
        name, duration = event.get("name"), safe_milliseconds(event.get("duration_ms"))
        if isinstance(name, str) and name in _TOOLS and duration is not None:
            print(f"[ferramenta: {name}, duration_ms={duration}]")
    requests = getattr(agent, "last_requests", [])
    for event in requests[:4] if isinstance(requests, list) else []:
        if not isinstance(event, dict):
            continue
        fields = []
        status = event.get("http_status")
        if type(status) is int and 100 <= status <= 599:
            fields.append(f"HTTP={status}")
        latency = safe_milliseconds(event.get("latency_ms"))
        if latency is not None:
            fields.append(f"latency_ms={latency}")
        secret = getattr(getattr(getattr(agent, "client", None), "config", None), "api_key", None)
        model = safe_model_identity(event.get("returned_model"), secret)
        if model:
            fields.append(f"model={model}")
        code = event.get("error_code")
        if isinstance(code, str) and code in _ERRORS:
            fields.append(f"error={code}")
        if fields:
            print("[requisição: " + ", ".join(fields) + "]")
    turn = getattr(agent, "last_turn", {})
    if isinstance(turn, dict):
        fields = []
        duration = safe_milliseconds(turn.get("duration_ms"))
        if duration is not None:
            fields.append(f"duration_ms={duration}")
        count = turn.get("request_count")
        if type(count) is int and 0 <= count <= 4:
            fields.append(f"request_count={count}")
        state = turn.get("deadline_state")
        if isinstance(state, str) and state in {"expired", "within_budget", "unavailable"}:
            fields.append(f"deadline={state}")
        if fields:
            print("[turno: " + ", ".join(fields) + "]")
    code = getattr(agent, "last_error_code", None)
    if isinstance(code, str) and code in _ERRORS:
        print(f"[erro: {code}]")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assistente virtual do Empório da Música.")
    parser.add_argument("--debug-tools", action="store_true", help="Mostrar ferramentas, latência, HTTP, modelo e erros sanitizados.")
    args = parser.parse_args(argv)
    try:
        config = Config.from_env()
    except ConfigError:
        print("Configuração inválida. Revise o .env local conforme .env.example: EMPORIO_LLM_API_KEY, EMPORIO_LLM_MODEL e EMPORIO_LLM_BASE_URL. Use somente o modelo gratuito autorizado do OpenRouter.")
        return 2
    if not _artifacts_ready():
        return 2
    agent = Orchestrator(ChatClient(config))
    print("Empório da Música — assistente virtual")
    print("Pergunte sobre instrumentos e políticas da loja. Digite /sair para encerrar.")
    try:
        while True:
            text = input("Você: ").strip()
            if text.casefold() in {"/sair", "sair", "exit"}:
                break
            if not text:
                continue
            answer = agent.reply(text)
            print(f"Assistente: {answer}")
            if args.debug_tools:
                _print_debug(agent)
    except (EOFError, KeyboardInterrupt):
        pass
    print("Até mais! A música continua por aqui. 🎵")
    return 0
