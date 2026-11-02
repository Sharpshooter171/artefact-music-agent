"""Shipped CLI wiring with real local tools/workers and a synthetic model only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys

import pytest

from app.agent import cli, tool_registry
from app.agent.config import Config
from app.agent.llm_client import ChatClient
from app.agent.orchestrator import FALLBACK
from app.policy.source import extract_policy_index


_ROOT = Path(__file__).resolve().parents[1]
_KEY = "synthetic-cli-path-private-key"
_CUSTOMER = "PRIVATE_CUSTOMER_MESSAGE Consulte instrumentos."
_UNKNOWN_CATEGORY = "PRIVATE_CATEGORY_THAT_DOES_NOT_EXIST"
_PRODUCT = "Yamaha C40 Nylon Natural"


@pytest.fixture(scope="module")
def policy_index_text():
    return json.dumps(extract_policy_index(_ROOT / "resources/políticas_da_loja.pdf"))


@pytest.fixture(autouse=True)
def forbid_provider_access(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("CLI tool-path tests must not contact a model provider")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(ChatClient, "_isolated_request", forbidden)


@pytest.mark.parametrize("relative_paths", [False, True])
@pytest.mark.parametrize("unknown_category", [False, True])
@pytest.mark.parametrize("debug", [False, True])
def test_shipped_cli_uses_actual_worker_without_parent_direct_fallback(
    catalog, monkeypatch, capsys, policy_index_text, relative_paths, unknown_category, debug,
):
    policy_path = catalog.db_path.parent / "policy_index.json"
    policy_path.write_text(policy_index_text, encoding="utf-8")
    monkeypatch.setenv("EMPORIO_POLICY_INDEX", str(policy_path))
    monkeypatch.setenv("EMPORIO_LLM_API_KEY", _KEY)
    monkeypatch.setenv("OPENROUTER_API_KEY", _KEY)
    if relative_paths:
        monkeypatch.chdir(catalog.db_path.parent)
        monkeypatch.setenv("EMPORIO_CATALOG_DB", catalog.db_path.name)
        monkeypatch.setenv("EMPORIO_POLICY_INDEX", policy_path.name)

    category = _UNKNOWN_CATEGORY if unknown_category else "Violões"
    arguments = json.dumps({"category": category, "price_max_cents": 60000})
    responses = [{"role": "assistant", "content": None, "tool_calls": [{
        "id": "synthetic_cli_call", "type": "function", "function": {
            "name": "search_products", "arguments": arguments,
        },
    }]}, {"role": "assistant", "content": json.dumps({
        "kind": "answer", "text": f"{_PRODUCT} por R$ 599,90 no catálogo local.",
        "sources": ["search_products"],
    })}]

    class SyntheticModel:
        config = Config(api_key=_KEY)

        def __init__(self):
            self.calls = 0

        def complete(self, messages, tools):
            self.calls += 1
            return responses[self.calls - 1]

    model = SyntheticModel()
    monkeypatch.setattr(cli.Config, "from_env", lambda: model.config)
    monkeypatch.setattr(cli, "ChatClient", lambda config: model)

    def no_parent_dispatch(*args, **kwargs):
        pytest.fail("Shipped CLI fell back to direct parent dispatch")

    monkeypatch.setattr(tool_registry.ToolRegistry, "dispatch", no_parent_dispatch)
    original_popen = tool_registry.subprocess.Popen
    spawned = []

    def tracked_popen(command, **kwargs):
        assert command == [sys.executable, "-I", str(
            Path(tool_registry.__file__).with_name("tool_worker.py").resolve())]
        assert _KEY not in json.dumps([command, kwargs.get("env", {})])
        process = original_popen(command, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(tool_registry.subprocess, "Popen", tracked_popen)
    turns = iter([_CUSTOMER, "/sair"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(turns))

    assert cli.main(["--debug-tools"] if debug else []) == 0
    assert len(spawned) == 1
    assert spawned[0].returncode == 0
    with pytest.raises(ChildProcessError):
        os.waitpid(spawned[0].pid, os.WNOHANG)
    output = capsys.readouterr().out
    assert model.calls == (1 if unknown_category else 2)
    if unknown_category:
        assert f"Assistente: {FALLBACK}" in output
        assert _PRODUCT not in output
        if debug:
            assert "[erro: CATEGORY_NOT_FOUND]" in output
            assert "[erro: TOOL_FAILURE]" in output
    else:
        assert f"Assistente: {_PRODUCT} por R$ 599,90 no catálogo local." in output
        assert FALLBACK not in output

    diagnostics = "\n".join(line for line in output.splitlines() if line.startswith("["))
    assert bool(diagnostics) is debug
    for private in (_KEY, _CUSTOMER, _UNKNOWN_CATEGORY, _PRODUCT, str(catalog.db_path),
                    str(policy_path), str(catalog.db_path.parent), arguments,
                    "stock_quantity", "specs", "Traceback", "Authorization"):
        assert private not in diagnostics
    assert _KEY not in output
    assert _CUSTOMER not in output
    assert _UNKNOWN_CATEGORY not in output
