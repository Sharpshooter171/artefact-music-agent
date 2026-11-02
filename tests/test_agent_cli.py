"""Offline CLI acceptance tests; no provider requests or real credentials."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent import cli


@pytest.fixture
def harness(monkeypatch):
    calls = []
    config = SimpleNamespace()
    monkeypatch.setattr(cli.Config, "from_env", lambda: config)
    monkeypatch.setattr(cli, "ChatClient", lambda value: value)
    monkeypatch.setattr(cli, "list_categories", lambda: {"ok": True})
    monkeypatch.setattr(cli, "search_store_policies", lambda *a, **k: {"ok": True})

    class FakeAgent:
        def __init__(self, client):
            self.last_trace = []
            self.last_error_code = None
            self.turn = 0

        def reply(self, text):
            self.turn += 1
            calls.append((self.turn, text))
            self.last_trace = [{"tool": "search_products", "error_code": None}]
            return f"Resposta em português {self.turn}."

    monkeypatch.setattr(cli, "Orchestrator", FakeAgent)
    return calls


def inputs(monkeypatch, lines):
    iterator = iter(lines)

    def read(prompt):
        try:
            value = next(iterator)
        except StopIteration:
            raise EOFError from None
        if isinstance(value, BaseException):
            raise value
        return value

    monkeypatch.setattr("builtins.input", read)


def test_multiturn_ptbr_single_session_and_blanks(harness, monkeypatch, capsys):
    inputs(monkeypatch, ["", "   ", "Vocês têm ukuleles?", "E no PIX?", "sair"])
    assert cli.main([]) == 0
    assert harness == [(1, "Vocês têm ukuleles?"), (2, "E no PIX?")]
    output = capsys.readouterr().out
    assert "Empório da Música" in output
    assert "Assistente: Resposta em português 1." in output
    assert "Assistente: Resposta em português 2." in output


@pytest.mark.parametrize("exit_input", ["sair", "/sair", "exit", " SAIR ", EOFError(), KeyboardInterrupt()])
def test_graceful_exit_never_calls_model(harness, monkeypatch, capsys, exit_input):
    inputs(monkeypatch, [exit_input])
    assert cli.main([]) == 0
    assert harness == []
    assert "Traceback" not in capsys.readouterr().out


def test_interrupt_during_reply_exits(harness, monkeypatch, capsys):
    def interrupted(self, text):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.Orchestrator, "reply", interrupted)
    inputs(monkeypatch, ["Olá"])
    assert cli.main([]) == 0
    assert "Traceback" not in capsys.readouterr().out


def test_help_does_not_read_dotenv_or_construct_client(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("startup attempted")

    monkeypatch.setattr(cli.Config, "from_env", forbidden)
    monkeypatch.setattr(cli, "ChatClient", forbidden)
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "--debug-tools" in capsys.readouterr().out


def test_config_failure_is_sanitized_and_instructive(harness, monkeypatch, capsys):
    def invalid():
        raise cli.ConfigError("MISSING_API_KEY")

    monkeypatch.setattr(cli.Config, "from_env", invalid)
    assert cli.main([]) == 2
    assert harness == []
    output = capsys.readouterr().out
    assert ".env" in output
    assert "EMPORIO_LLM_API_KEY" in output
    assert "Traceback" not in output


@pytest.mark.parametrize("which", ["catalog", "policy", "both"])
def test_artifact_failure_offers_exact_build_commands(harness, monkeypatch, capsys, which):
    if which in {"catalog", "both"}:
        monkeypatch.setattr(cli, "list_categories", lambda: {"ok": False})
    if which in {"policy", "both"}:
        monkeypatch.setattr(cli, "search_store_policies", lambda *a, **k: {"ok": False})
    assert cli.main([]) == 2
    assert harness == []
    output = capsys.readouterr().out
    if which in {"catalog", "both"}:
        assert "-m scripts.build_catalog --data-dir data/raw --output data/generated/catalog.sqlite" in output
    if which in {"policy", "both"}:
        assert "-m scripts.build_policy_index" in output
        assert "resources/políticas_da_loja.pdf" in output
        assert "data/generated/policy_index.json" in output


def test_debug_is_off_by_default(harness, monkeypatch, capsys):
    inputs(monkeypatch, ["Ukulele", "sair"])
    assert cli.main([]) == 0
    assert "search_products" not in capsys.readouterr().out


def test_debug_emits_only_allowlisted_tool_names_and_codes(harness, monkeypatch, capsys):
    original = cli.Orchestrator.reply

    def reply(self, text):
        response = original(self, text)
        self.last_trace = [
            {"tool": "search_products", "error_code": None, "raw": "PRIVATE_SECRET"},
            {"tool": "PRIVATE_SECRET", "error_code": "PRIVATE_SECRET"},
        ]
        self.last_error_code = "RATE_LIMITED"
        return response

    monkeypatch.setattr(cli.Orchestrator, "reply", reply)
    inputs(monkeypatch, ["Ukulele", "sair"])
    assert cli.main(["--debug-tools"]) == 0
    output = capsys.readouterr().out
    assert "search_products" in output
    assert "RATE_LIMITED" in output
    assert "PRIVATE_SECRET" not in output


@pytest.mark.parametrize("policy_state", ["valid", "missing", "corrupt"])
def test_startup_uses_real_readonly_artifact_validation(catalog, tmp_path, monkeypatch, capsys, policy_state):
    from app.policy.source import extract_policy_index

    index_path = tmp_path / "policy.json"
    if policy_state == "valid":
        index = extract_policy_index(Path("resources/políticas_da_loja.pdf"))
        index_path.write_text(json.dumps(index), encoding="utf-8")
    elif policy_state == "corrupt":
        index_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("EMPORIO_POLICY_INDEX", str(index_path))
    monkeypatch.setattr(cli.Config, "from_env", lambda: SimpleNamespace())
    monkeypatch.setattr(cli, "ChatClient", lambda config: config)
    monkeypatch.setattr(cli, "Orchestrator", lambda client: SimpleNamespace())
    inputs(monkeypatch, ["exit"])
    before = catalog.db_path.read_bytes()
    assert cli.main([]) == (0 if policy_state == "valid" else 2)
    assert catalog.db_path.read_bytes() == before
    assert index_path.exists() is (policy_state != "missing")
    if policy_state != "valid":
        assert "build_policy_index" in capsys.readouterr().out


@pytest.mark.parametrize("catalog_state", ["missing", "corrupt"])
def test_bad_catalog_is_not_recreated(tmp_path, monkeypatch, capsys, catalog_state):
    from app.policy.source import extract_policy_index

    index_path = tmp_path / "policy.json"
    index = extract_policy_index(Path("resources/políticas_da_loja.pdf"))
    index_path.write_text(json.dumps(index), encoding="utf-8")
    catalog_path = tmp_path / "catalog.sqlite"
    if catalog_state == "corrupt":
        catalog_path.write_bytes(b"not a database")
    monkeypatch.setenv("EMPORIO_POLICY_INDEX", str(index_path))
    monkeypatch.setenv("EMPORIO_CATALOG_DB", str(catalog_path))
    monkeypatch.setattr(cli.Config, "from_env", lambda: SimpleNamespace())
    assert cli.main([]) == 2
    assert catalog_path.exists() is (catalog_state == "corrupt")
    if catalog_state == "corrupt":
        assert catalog_path.read_bytes() == b"not a database"
    output = capsys.readouterr().out
    assert "build_catalog" in output
    assert str(tmp_path) not in output
