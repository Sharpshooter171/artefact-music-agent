"""Real request workers and loopback HTTP, never a real provider or credential."""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sys
from threading import Event, Thread
from time import monotonic

import pytest

from app.agent import http_worker, llm_client
from app.agent.config import Config
from app.agent.deadline import Deadline
from app.agent.llm_client import ChatClient, ProviderError


KEY = "synthetic-worker-io-key"


def isolated_worker(tmp_path, monkeypatch, setup=""):
    """Change only this spawned test worker; production endpoint stays immutable."""
    script = tmp_path / "loopback_worker.py"
    pidfile = tmp_path / "worker.pid"
    script.write_text(
        "import importlib.util,os,socket,ssl,sys,time\n"
        "from pathlib import Path\n"
        f"spec=importlib.util.spec_from_file_location('fixture_http_worker', {str(Path(http_worker.__file__).resolve())!r})\n"
        "worker=importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(worker)\n"
        f"Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
        + setup + "\nworker.main()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(llm_client, "_worker_command", lambda: [sys.executable, "-I", str(script)])
    return pidfile


def assert_reaped(pidfile):
    assert pidfile.exists(), "Worker must actually start before cancellation"
    pid = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    with pytest.raises(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)


@pytest.mark.parametrize("stage", ["dns", "connect"])
def test_real_worker_cancelled_inside_blocked_resolution_or_connect(tmp_path, monkeypatch, stage):
    """Injected blocking hooks run inside the worker's actual urllib call stack."""
    entered = tmp_path / "entered"
    survived = tmp_path / "survived"
    setup = (
        "worker.ENDPOINT='http://127.0.0.1:9/chat/completions'\n"
        "def blocked(*args, **kwargs):\n"
        f"    Path({str(entered)!r}).write_text({stage!r})\n"
        "    time.sleep(3)\n"
        f"    Path({str(survived)!r}).write_text('request continued')\n"
        "    raise OSError('synthetic blocked operation')\n"
    )
    setup += "socket.getaddrinfo=blocked\n" if stage == "dns" else "socket.socket.connect=blocked\n"
    pidfile = isolated_worker(tmp_path, monkeypatch, setup)
    client = ChatClient(Config(KEY))
    started = monotonic()
    with pytest.raises(ProviderError) as caught:
        client.complete_with_deadline([], [], Deadline(0.4))
    assert monotonic() - started < 1.2
    assert caught.value.code == "REQUEST_DEADLINE_EXCEEDED"
    assert entered.read_text() == stage
    assert not survived.exists()
    assert_reaped(pidfile)
    assert KEY not in str(caught.value)
    assert KEY not in repr(client.last_diagnostic)


@contextmanager
def loopback_server(mode):
    stop = Event()
    disconnected = Event()
    entered = Event()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            requests.append(self.path)
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            entered.set()
            if mode == "redirect":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/destination")
                self.end_headers()
                return
            if mode == "success":
                body = json.dumps({
                    "model": "fixture/synthetic:free", "usage": {"cost": 0},
                    "choices": [{"finish_reason": "stop", "message": {
                        "role": "assistant", "content": "synthetic response",
                    }}],
                }).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(http_worker.MAX_RESPONSE_BYTES + 2))
            self.end_headers()
            self.wfile.flush()
            try:
                if mode == "oversized":
                    self.wfile.write(b"x" * (http_worker.MAX_RESPONSE_BYTES + 2))
                    self.wfile.flush()
                elif mode == "stalled":
                    # No further request bytes exist: EOF proves the client closed.
                    if not self.connection.recv(1):
                        disconnected.set()
                else:
                    # Every short write resets a socket inactivity timeout, but the
                    # overall deadline must still terminate the request.
                    while not stop.wait(0.02):
                        self.wfile.write(b"x")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                disconnected.set()

        def do_GET(self):
            requests.append(self.path)
            self.send_response(200)
            self.end_headers()

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 2
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/chat/completions", requests, entered, disconnected
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        thread.join(2)
        assert not thread.is_alive(), "Loopback fixture must leave no server thread"


@pytest.mark.parametrize("mode", ["stalled", "dribbling"])
def test_actual_loopback_read_cancelled_socket_closed_and_worker_reaped(tmp_path, monkeypatch, mode):
    with loopback_server(mode) as (url, requests, entered, disconnected):
        pidfile = isolated_worker(tmp_path, monkeypatch, f"worker.ENDPOINT={url!r}\n")
        client = ChatClient(Config(KEY))
        started = monotonic()
        with pytest.raises(ProviderError) as caught:
            client.complete_with_deadline([], [], Deadline(0.4))
        elapsed = monotonic() - started
        assert caught.value.code == "REQUEST_DEADLINE_EXCEEDED"
        assert 0.3 <= elapsed < 1.2
        assert entered.is_set()
        assert client.last_http_status == 200
        assert requests == ["/chat/completions"]
        assert disconnected.wait(0.5), "Killed worker must close the active HTTP socket"
        assert_reaped(pidfile)


def test_actual_loopback_redirect_refused_without_second_request(tmp_path, monkeypatch):
    with loopback_server("redirect") as (url, requests, _, _):
        pidfile = isolated_worker(tmp_path, monkeypatch, f"worker.ENDPOINT={url!r}\n")
        client = ChatClient(Config(KEY))
        with pytest.raises(ProviderError) as caught:
            client.complete_with_deadline([], [], Deadline(2))
        assert caught.value.code == "PROVIDER_REDIRECT"
        assert client.last_http_status == 302
        assert requests == ["/chat/completions"]
        assert_reaped(pidfile)


def test_actual_loopback_success_preserves_chatclient_message_and_metadata(tmp_path, monkeypatch):
    with loopback_server("success") as (url, requests, _, _):
        pidfile = isolated_worker(tmp_path, monkeypatch, f"worker.ENDPOINT={url!r}\n")
        client = ChatClient(Config(KEY))
        assert client.complete_with_deadline([], [], Deadline(2)) == {
            "role": "assistant", "content": "synthetic response",
        }
        assert requests == ["/chat/completions"]
        assert client.last_model == "fixture/synthetic:free"
        assert client.last_http_status == 200
        assert client.last_error_code is None
        assert client.last_cost == 0
        assert_reaped(pidfile)


def test_actual_loopback_response_size_is_bounded(tmp_path, monkeypatch):
    with loopback_server("oversized") as (url, requests, _, _):
        pidfile = isolated_worker(tmp_path, monkeypatch, f"worker.ENDPOINT={url!r}\n")
        client = ChatClient(Config(KEY))
        with pytest.raises(ProviderError) as caught:
            client.complete_with_deadline([], [], Deadline(2))
        assert caught.value.code == "RESPONSE_TOO_LARGE"
        assert client.last_http_status == 200
        assert requests == ["/chat/completions"]
        assert_reaped(pidfile)


def test_worker_tls_context_verifies_certificates_and_errors_cannot_echo_key(tmp_path, monkeypatch, capfd):
    observed = tmp_path / "tls.json"
    setup = (
        "class ExplodingOpener:\n"
        "    def open(self, request, timeout):\n"
        "        secret=request.get_header('Authorization')\n"
        "        sys.stderr.write(secret)\n"
        "        raise RuntimeError(secret)\n"
        "def inspect_opener(*handlers):\n"
        "    contexts=[handler._context for handler in handlers if isinstance(handler, worker.HTTPSHandler)]\n"
        "    context=contexts[0]\n"
        f"    Path({str(observed)!r}).write_text(worker.json.dumps([context.check_hostname,context.verify_mode==ssl.CERT_REQUIRED]))\n"
        "    return ExplodingOpener()\n"
        "worker.build_opener=inspect_opener\n"
    )
    pidfile = isolated_worker(tmp_path, monkeypatch, setup)
    client = ChatClient(Config(KEY))
    with pytest.raises(ProviderError) as caught:
        client.complete_with_deadline([], [], Deadline(2))
    assert caught.value.code == "PROVIDER_UNAVAILABLE"
    assert json.loads(observed.read_text()) == [True, True]
    captured = capfd.readouterr()
    assert KEY not in captured.out + captured.err + str(caught.value) + repr(client.last_diagnostic)
    assert_reaped(pidfile)
