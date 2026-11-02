"""Bounded stdlib OpenRouter Chat Completions transport; no automatic retries."""
from __future__ import annotations

import base64
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import selectors
import subprocess
import sys
from time import monotonic
import json
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request

from app.agent import worker_process
from app.agent.deadline import Deadline
from app.agent.http_worker import (MAX_IPC_INPUT, MAX_IPC_OUTPUT, NoRedirect, http_error_code)

from app.agent.config import FREE_MODEL, Config


MAX_RESPONSE_BYTES = 128 * 1024
MAX_REQUEST_BYTES = 256 * 1024


class ProviderError(Exception):
    """Sanitized provider failure. Never retain raw error text or response body."""

    def __init__(self, code: str, http_status: int | None = None):
        self.code = code
        self.http_status = http_status
        super().__init__(f"Serviço de IA indisponível ({code}).")


def _worker_command():
    # Absolute code path, isolated imports; neither credentials nor customer data in argv.
    return [sys.executable, '-I', str(Path(__file__).with_name('http_worker.py').resolve())]


class ChatClient:
    def __init__(self, config: Config, opener=None):
        self.config = config
        # Explicit opener injection is a trusted synchronous offline test seam. The
        # shipped CLI never supplies it; production always uses an isolated worker.
        self._open = opener
        self.last_model: str | None = None
        self.last_http_status: int | None = None
        self.last_error_code: str | None = None
        self.last_cost: float | None = None
        self.last_latency_ms: float | None = None
        self.last_diagnostic: dict = {}

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        return self.complete_with_deadline(messages, tools, None)

    def complete_with_deadline(self, messages: list[dict], tools: list[dict],
                               deadline: Deadline | None) -> dict:
        started = monotonic()
        request_deadline = Deadline(self.config.request_deadline)
        if deadline is not None and deadline.remaining() < request_deadline.remaining():
            request_deadline = deadline
        self.last_model = None
        self.last_http_status = None
        self.last_error_code = None
        self.last_cost = None
        self.last_latency_ms = 0.0
        self.last_diagnostic = {}
        try:
            if request_deadline.expired:
                raise ProviderError('REQUEST_DEADLINE_EXCEEDED')
            result = self._complete(messages, tools, request_deadline)
            if request_deadline.expired:
                raise ProviderError('REQUEST_DEADLINE_EXCEEDED', self.last_http_status)
            return result
        except ProviderError as error:
            self.last_error_code = error.code
            raise
        except (TimeoutError, socket.timeout):
            self.last_error_code = 'PROVIDER_TIMEOUT'
            raise ProviderError(self.last_error_code, self.last_http_status) from None
        except (URLError, OSError, ValueError, TypeError, RecursionError):
            self.last_error_code = 'PROVIDER_UNAVAILABLE'
            raise ProviderError(self.last_error_code, self.last_http_status) from None
        finally:
            self.last_latency_ms = round((monotonic() - started) * 1000, 3)
            self.last_diagnostic = {
                'http_status': self.last_http_status, 'returned_model': self.last_model,
                'latency_ms': self.last_latency_ms, 'error_code': self.last_error_code,
            }

    def _complete(self, messages, tools, deadline):
        payload = {
            "model": self.config.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
            "max_tokens": self.config.max_tokens,
            "provider": {
                "allow_fallbacks": self.config.provider_failover,
                "require_parameters": True,
                "max_price": {"prompt": 0, "completion": 0, "request": 0, "image": 0},
            },
        }
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(body) > MAX_REQUEST_BYTES:
            raise ProviderError("REQUEST_TOO_LARGE")
        if deadline.expired:
            raise ProviderError('REQUEST_DEADLINE_EXCEEDED')
        if self._open is None:
            raw = self._isolated_request(body, deadline)
        else:
            raw = self._injected_request(body)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderError("RESPONSE_TOO_LARGE", self.last_http_status)
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise ProviderError("MALFORMED_RESPONSE", self.last_http_status) from None
        if not isinstance(data, dict):
            raise ProviderError("MALFORMED_RESPONSE", self.last_http_status)
        if "error" in data:
            raise ProviderError("PROVIDER_REJECTED", self.last_http_status)
        actual_model = data.get("model")
        if _contains_secret(actual_model, self.config.api_key):
            raise ProviderError("UNSAFE_RESPONSE", self.last_http_status)
        # The approved free router returns the concrete model it selected rather
        # than echoing the request alias. Never broaden the outgoing model choice
        # or accept a paid/unqualified returned identity.
        if not _response_model_allowed(actual_model, self.config.model):
            raise ProviderError("UNAUTHORIZED_RESPONSE_MODEL", self.last_http_status)
        self.last_model = actual_model
        usage = data.get("usage", {})
        if not isinstance(usage, dict):
            raise ProviderError("MALFORMED_RESPONSE", self.last_http_status)
        if "cost" in usage:
            cost = usage["cost"]
            try:
                amount = Decimal(str(cost))
            except InvalidOperation:
                raise ProviderError("INVALID_PROVIDER_COST", self.last_http_status) from None
            if isinstance(cost, bool) or not amount.is_finite() or amount != 0:
                raise ProviderError("NONZERO_PROVIDER_COST", self.last_http_status)
            self.last_cost = 0
        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ProviderError("MALFORMED_RESPONSE", self.last_http_status)
        choice = choices[0]
        if choice.get("finish_reason") not in ("stop", "tool_calls", None):
            raise ProviderError("INCOMPLETE_RESPONSE", self.last_http_status)
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise ProviderError("MALFORMED_RESPONSE", self.last_http_status)
        content, calls = message.get("content"), message.get("tool_calls")
        if content is not None and not isinstance(content, str):
            raise ProviderError("MALFORMED_RESPONSE", self.last_http_status)
        if calls is not None and (not isinstance(calls, list) or not all(isinstance(call, dict) for call in calls)):
            raise ProviderError("MALFORMED_RESPONSE", self.last_http_status)
        if not (isinstance(content, str) and content.strip()) and not calls:
            raise ProviderError("EMPTY_RESPONSE", self.last_http_status)
        result = {"role": "assistant", "content": content}
        if calls:
            result["tool_calls"] = calls
        if _contains_secret(result, self.config.api_key):
            raise ProviderError("UNSAFE_RESPONSE", self.last_http_status)
        return result

    def _injected_request(self, body):
        """Trusted fake transport injection; not used by the production CLI."""
        request = Request(
            self.config.base_url + '/chat/completions', data=body, method='POST',
            headers={'Authorization': 'Bearer ' + self.config.api_key,
                     'Content-Type': 'application/json', 'Accept': 'application/json'},
        )
        try:
            with self._open(request, timeout=self.config.timeout) as response:
                self.last_http_status = response.status
                if response.status != 200:
                    raise self._http_error(response.status)
                return response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            self.last_http_status = error.code
            error.close()
            raise self._http_error(error.code) from None

    def _isolated_request(self, body, deadline):
        packet = json.dumps({'api_key': self.config.api_key, 'timeout': self.config.timeout,
                             'body': body.decode('utf-8')}, ensure_ascii=False).encode('utf-8')
        if len(packet) > MAX_IPC_INPUT:
            raise ProviderError('REQUEST_TOO_LARGE')
        if deadline.expired:
            raise ProviderError('REQUEST_DEADLINE_EXCEEDED')
        # Empty child env: no inherited provider credentials in /proc/.../environ.
        # stderr is discarded, never collected or printed, even for startup failures.
        process = None
        mask = worker_process.block_spawn_signals()
        try:
            try:
                process = subprocess.Popen(_worker_command(), stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                           env={}, start_new_session=True)
            finally:
                # A queued turn alarm is delivered here, after the child has an owner.
                worker_process.restore_spawn_signals(mask)
            output = bytearray()
            pending = memoryview(packet)
            with selectors.DefaultSelector() as selector:
                os.set_blocking(process.stdin.fileno(), False)
                os.set_blocking(process.stdout.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE)
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = deadline.remaining()
                    if remaining <= 0:
                        raise ProviderError('REQUEST_DEADLINE_EXCEEDED', self.last_http_status)
                    for key, _ in selector.select(remaining):
                        if key.fileobj is process.stdin:
                            try:
                                count = os.write(process.stdin.fileno(), pending[:8192])
                            except BrokenPipeError:
                                pending = pending[:0]
                            else:
                                pending = pending[count:]
                            if not pending:
                                selector.unregister(process.stdin)
                                try:
                                    process.stdin.close()
                                except OSError:
                                    pass
                        else:
                            chunk = os.read(process.stdout.fileno(), 16384)
                            if not chunk:
                                selector.unregister(process.stdout)
                                continue
                            output.extend(chunk)
                            if len(output) > MAX_IPC_OUTPUT:
                                raise ProviderError('WORKER_PROTOCOL_ERROR')
                            # Bounded metadata frame emitted as soon as headers arrive.
                            first_line = output.partition(b'\n')[0]
                            if b'\n' in output and self.last_http_status is None:
                                try:
                                    status = json.loads(first_line).get('http_status')
                                except (ValueError, AttributeError):
                                    raise ProviderError('WORKER_PROTOCOL_ERROR') from None
                                if type(status) is int and 100 <= status <= 599:
                                    self.last_http_status = status
                try:
                    process.wait(timeout=deadline.remaining())
                except subprocess.TimeoutExpired:
                    raise ProviderError('REQUEST_DEADLINE_EXCEEDED', self.last_http_status) from None
            if deadline.expired:
                raise ProviderError('REQUEST_DEADLINE_EXCEEDED', self.last_http_status)
            if process.returncode != 0:
                raise ProviderError('WORKER_PROTOCOL_ERROR', self.last_http_status)
            try:
                lines = output.splitlines()
                if not 1 <= len(lines) <= 2:
                    raise ValueError
                result = json.loads(lines[-1])
                status = result.get('http_status')
                if status is not None and (type(status) is not int or not 100 <= status <= 599):
                    raise ValueError
                self.last_http_status = status
                code = result.get('error_code')
                if code is not None:
                    if code not in _WORKER_CODES:
                        raise ValueError
                    raise ProviderError(code, status)
                if status != 200 or not isinstance(result.get('body_b64'), str):
                    raise ValueError
                raw = base64.b64decode(result['body_b64'], validate=True)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ProviderError('RESPONSE_TOO_LARGE', status)
                return raw
            except (ValueError, TypeError, AttributeError, KeyError):
                raise ProviderError('WORKER_PROTOCOL_ERROR', self.last_http_status) from None
        finally:
            # Every exit path, including turn alarm / Ctrl-C, owns cleanup.
            worker_process.terminate(process)

    def _http_error(self, status):
        return ProviderError(http_error_code(status), status)


_WORKER_CODES = frozenset({
    'PROVIDER_RATE_LIMIT', 'PROVIDER_AUTH', 'PROVIDER_REDIRECT', 'PROVIDER_HTTP_ERROR',
    'PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT', 'RESPONSE_TOO_LARGE', 'WORKER_PROTOCOL_ERROR',
})


def _contains_secret(value, secret: str) -> bool:
    if isinstance(value, str):
        return secret in value
    if isinstance(value, dict):
        return any(_contains_secret(key, secret) or _contains_secret(item, secret)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret(item, secret) for item in value)
    return False


def _response_model_allowed(model: object, requested_model: str) -> bool:
    if not _free_response_model(model):
        return False
    return requested_model == FREE_MODEL or model == requested_model


def _free_response_model(model: object) -> bool:
    return isinstance(model, str) and (
        model == FREE_MODEL
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*:free",
            model,
        ) is not None
    )
