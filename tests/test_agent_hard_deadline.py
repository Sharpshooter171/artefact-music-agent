"""Actual process cancellation with synthetic credentials; no provider traffic."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import sys
import time

import pytest

from app.agent.config import Config
from app.agent.llm_client import ChatClient, ProviderError
from app.agent.deadline import Deadline


def worker_command(tmp_path, body):
    script = tmp_path / 'worker.py'
    script.write_text(body)
    return [sys.executable, '-I', str(script)]


def test_supervisor_kills_and_reaps_actual_blocked_worker(tmp_path, monkeypatch):
    """The worker would write a marker after sleeping if cancellation failed."""
    from app.agent import llm_client
    marker = tmp_path / 'abandoned'
    pidfile = tmp_path / 'pid'
    command = worker_command(tmp_path, f'''import os,sys,time
from pathlib import Path
Path({str(pidfile)!r}).write_text(str(os.getpid()))
sys.stdin.buffer.read()
time.sleep(1)
Path({str(marker)!r}).write_text('request survived')
''')
    monkeypatch.setattr(llm_client, '_worker_command', lambda: command)
    client = ChatClient(Config('synthetic-hard-deadline-key'))
    started = time.monotonic()
    with pytest.raises(ProviderError) as caught:
        client.complete_with_deadline([], [], Deadline(0.2))
    elapsed = time.monotonic() - started
    assert caught.value.code == 'REQUEST_DEADLINE_EXCEEDED'
    assert elapsed < 0.8
    assert pidfile.exists()
    pid = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    with pytest.raises(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)
    time.sleep(1.05)
    assert not marker.exists()
    assert client.last_latency_ms >= 100


def test_supervisor_bounds_ipc_stdout(tmp_path, monkeypatch):
    from app.agent import llm_client
    command = worker_command(tmp_path, "import os,sys,time\nsys.stdin.buffer.read()\nwhile True: os.write(1,b'x'*8192)\n")
    monkeypatch.setattr(llm_client, '_worker_command', lambda: command)
    client = ChatClient(Config('synthetic-ipc-key'))
    with pytest.raises(ProviderError) as caught:
        client.complete_with_deadline([], [], Deadline(1))
    assert caught.value.code == 'WORKER_PROTOCOL_ERROR'


def test_worker_argv_and_environment_never_include_key(tmp_path, monkeypatch):
    from app.agent import llm_client
    capture = tmp_path / 'capture'
    key = 'synthetic-key-never-in-argv-or-env'
    monkeypatch.setenv('OPENROUTER_API_KEY', key)
    command = worker_command(tmp_path, f'''import json,os,sys
from pathlib import Path
Path({str(capture)!r}).write_text(json.dumps([sys.argv,dict(os.environ)]))
sys.stdin.buffer.read()
print('{{"error_code":"PROVIDER_UNAVAILABLE","http_status":null}}')
''')
    monkeypatch.setattr(llm_client, '_worker_command', lambda: command)
    client = ChatClient(Config(key))
    with pytest.raises(ProviderError):
        client.complete([], [])
    assert key not in capture.read_text()
    assert key not in repr(client.last_diagnostic)


def test_expired_budget_never_starts_worker(monkeypatch):
    from app.agent import llm_client
    def forbidden(*args, **kwargs):
        pytest.fail('expired budget started process')
    monkeypatch.setattr(llm_client.subprocess, 'Popen', forbidden)
    with pytest.raises(ProviderError) as caught:
        ChatClient(Config('synthetic-expired-key')).complete_with_deadline([], [], Deadline(0))
    assert caught.value.code == 'REQUEST_DEADLINE_EXCEEDED'


def test_turn_signal_during_worker_creation_never_abandons_process(tmp_path, monkeypatch):
    """Deliver turn expiry after OS spawn but before Popen returns to its caller."""
    from app.agent import llm_client
    from app.agent.orchestrator import Orchestrator

    command = worker_command(tmp_path, "import time; time.sleep(10)\n")
    children = []
    original_popen = llm_client.subprocess.Popen

    def interrupted_popen(*args, **kwargs):
        child = original_popen(*args, **kwargs)
        children.append(child)
        signal.raise_signal(signal.SIGALRM)
        return child

    monkeypatch.setattr(llm_client, '_worker_command', lambda: command)
    monkeypatch.setattr(llm_client.subprocess, 'Popen', interrupted_popen)
    client = ChatClient(Config('synthetic-spawn-window-key'))
    try:
        agent = Orchestrator(client, turn_deadline=1)
        agent.reply('Pergunta sintética')
        assert agent.last_error_code == 'TURN_DEADLINE_EXCEEDED'
        assert len(children) == 1
        assert children[0].poll() is not None
        with pytest.raises(ChildProcessError):
            os.waitpid(children[0].pid, os.WNOHANG)
    finally:
        # RED must not itself leak the process it demonstrates is abandoned.
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait()
            if child.stdin is not None and not child.stdin.closed:
                child.stdin.close()
            if child.stdout is not None and not child.stdout.closed:
                child.stdout.close()
