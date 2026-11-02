"""Isolated read-only tools retain their contracts and cannot outlive a turn."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys
from time import monotonic

import pytest

from app.agent.deadline import Deadline
from app.agent import tool_registry
from app.agent.tool_registry import ToolRegistry
from app.policy.source import extract_policy_index


@pytest.mark.parametrize(("name", "arguments"), [
    ("search_products", '{"category":"Violões","limit":2}'),
    ("get_product_details", '{"product_id":101}'),
    ("list_categories", '{}'),
])
def test_isolated_catalog_tool_matches_unchanged_direct_contract(catalog, name, arguments):
    registry = ToolRegistry()
    expected = registry.dispatch(name, arguments)
    assert expected["ok"] is True
    assert registry.dispatch_with_deadline(name, arguments, Deadline(3)) == expected


def test_isolated_policy_tool_matches_unchanged_citations_and_cautions(tmp_path, monkeypatch):
    index = tmp_path / "policy.json"
    index.write_text(json.dumps(extract_policy_index(Path("resources/políticas_da_loja.pdf"))), encoding="utf-8")
    monkeypatch.setenv("EMPORIO_POLICY_INDEX", str(index))
    registry = ToolRegistry()
    arguments = '{"query":"Qual o WhatsApp?","limit":1}'
    expected = registry.dispatch("search_store_policies", arguments)
    assert expected["ok"] is True
    assert expected["data"]["cautions"]
    assert expected["data"]["matches"][0]["pages"]
    assert registry.dispatch_with_deadline("search_store_policies", arguments, Deadline(3)) == expected


def tool_script(tmp_path, monkeypatch, body):
    script = tmp_path / "tool_worker_fixture.py"
    pidfile = tmp_path / "tool_worker.pid"
    script.write_text(
        "import json,os,sys,time\nfrom pathlib import Path\n"
        f"Path({str(pidfile)!r}).write_text(str(os.getpid()))\n" + body,
        encoding="utf-8",
    )
    monkeypatch.setattr(tool_registry, "_tool_worker_command", lambda: [sys.executable, "-I", str(script)])
    return pidfile


def assert_reaped(pidfile):
    assert pidfile.exists()
    pid = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    with pytest.raises(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)


def test_blocked_tool_worker_is_killed_and_reaped_without_inherited_provider_key(tmp_path, monkeypatch):
    key = "synthetic-tool-worker-private-key"
    monkeypatch.setenv("EMPORIO_LLM_API_KEY", key)
    monkeypatch.setenv("OPENROUTER_API_KEY", key)
    capture = tmp_path / "capture.json"
    continued = tmp_path / "continued"
    pidfile = tool_script(tmp_path, monkeypatch,
        "packet=sys.stdin.buffer.read()\n"
        f"Path({str(capture)!r}).write_text(json.dumps([sys.argv,dict(os.environ),packet.decode()]))\n"
        "time.sleep(3)\n"
        f"Path({str(continued)!r}).write_text('abandoned work continued')\n"
    )
    started = monotonic()
    with pytest.raises(Exception) as caught:
        ToolRegistry().dispatch_with_deadline("list_categories", '{}', Deadline(0.3))
    assert caught.value.code == "TURN_DEADLINE_EXCEEDED"
    assert monotonic() - started < 1.1
    assert key not in capture.read_text()
    assert key not in str(caught.value)
    assert not continued.exists()
    assert_reaped(pidfile)


def test_real_sqlite_lock_wait_is_cancelled_by_tool_deadline(catalog, tmp_path, monkeypatch):
    """SQLite's five-second busy wait must not extend the remaining turn budget."""
    entered = tmp_path / "sqlite-select-entered"
    worker_path = Path(tool_registry.__file__).with_name("tool_worker.py").resolve()
    pidfile = tool_script(tmp_path, monkeypatch,
        "import runpy,sqlite3\n"
        "original_connect=sqlite3.connect\n"
        "class TrackedConnection(sqlite3.Connection):\n"
        "    def execute(self,sql,*args,**kwargs):\n"
        "        if sql.lstrip().upper().startswith('SELECT'):\n"
        f"            Path({str(entered)!r}).write_text('sqlite lock wait entered')\n"
        "        return super().execute(sql,*args,**kwargs)\n"
        "def connect(*args,**kwargs):\n"
        "    kwargs['factory']=TrackedConnection\n"
        "    return original_connect(*args,**kwargs)\n"
        "sqlite3.connect=connect\n"
        f"runpy.run_path({str(worker_path)!r},run_name='__main__')\n"
    )
    lock = sqlite3.connect(catalog.db_path)
    lock.execute("BEGIN EXCLUSIVE")
    try:
        started = monotonic()
        with pytest.raises(Exception) as caught:
            ToolRegistry().dispatch_with_deadline("list_categories", '{}', Deadline(0.5))
        assert caught.value.code == "TURN_DEADLINE_EXCEEDED"
        assert monotonic() - started < 1.3
        assert entered.exists(), "Actual SQLite SELECT must enter before cancellation"
        assert_reaped(pidfile)
    finally:
        lock.rollback()
        lock.close()
    assert ToolRegistry().dispatch("list_categories", '{}')["ok"] is True


def test_expired_turn_does_not_launch_tool_worker(monkeypatch):
    def forbidden():
        pytest.fail("Expired turn attempted to create tool worker")
    monkeypatch.setattr(tool_registry, "_tool_worker_command", forbidden)
    with pytest.raises(Exception) as caught:
        ToolRegistry().dispatch_with_deadline("list_categories", '{}', Deadline(0))
    assert caught.value.code == "TURN_DEADLINE_EXCEEDED"


def test_tool_worker_stdout_is_bounded_and_failure_reaps_process(tmp_path, monkeypatch):
    pidfile = tool_script(tmp_path, monkeypatch,
        "sys.stdin.buffer.read()\n"
        "while True: os.write(1,b'x'*8192)\n"
    )
    started = monotonic()
    result = ToolRegistry().dispatch_with_deadline("list_categories", '{}', Deadline(2))
    assert result["ok"] is False
    assert result["error"]["code"] in {"TOOL_FAILURE", "TOOL_OUTPUT_TOO_LARGE"}
    assert monotonic() - started < 1.1
    assert_reaped(pidfile)
