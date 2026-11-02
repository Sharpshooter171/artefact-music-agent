"""Bounded stdlib OpenRouter Chat Completions transport; no automatic retries."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.agent.config import FREE_MODEL, Config


MAX_RESPONSE_BYTES = 128 * 1024
MAX_REQUEST_BYTES = 256 * 1024


class ProviderError(Exception):
    """Sanitized provider failure. Never retain raw error text or response body."""

    def __init__(self, code: str, http_status: int | None = None):
        self.code = code
        self.http_status = http_status
        super().__init__(f"Serviço de IA indisponível ({code}).")


class NoRedirect(HTTPRedirectHandler):
    """Never forward Authorization to a redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ChatClient:
    def __init__(self, config: Config, opener=None):
        self.config = config
        self._open = opener if opener is not None else build_opener(NoRedirect()).open
        self.last_model: str | None = None
        self.last_http_status: int | None = None
        self.last_error_code: str | None = None
        self.last_cost: float | None = None

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        self.last_model = None
        self.last_http_status = None
        self.last_error_code = None
        self.last_cost = None
        try:
            return self._complete(messages, tools)
        except ProviderError as error:
            self.last_error_code = error.code
            raise
        except (TimeoutError, socket.timeout):
            self.last_error_code = "PROVIDER_TIMEOUT"
            raise ProviderError(self.last_error_code, self.last_http_status) from None
        except (URLError, OSError, ValueError, TypeError, RecursionError):
            self.last_error_code = "PROVIDER_UNAVAILABLE"
            raise ProviderError(self.last_error_code, self.last_http_status) from None

    def _complete(self, messages, tools):
        payload = {
            "model": self.config.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
            "max_tokens": 2048,
            "provider": {
                "allow_fallbacks": False,
                "require_parameters": True,
                "max_price": {"prompt": 0, "completion": 0, "request": 0, "image": 0},
            },
        }
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(body) > MAX_REQUEST_BYTES:
            raise ProviderError("REQUEST_TOO_LARGE")
        request = Request(
            self.config.base_url + "/chat/completions", data=body, method="POST",
            headers={"Authorization": "Bearer " + self.config.api_key,
                     "Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with self._open(request, timeout=self.config.timeout) as response:
                self.last_http_status = response.status
                if response.status != 200:
                    raise self._http_error(response.status)
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            self.last_http_status = error.code
            # Body and headers may echo credentials: never read or retain them.
            error.close()
            raise self._http_error(error.code) from None
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

    def _http_error(self, status):
        if status == 429:
            code = "PROVIDER_RATE_LIMIT"
        elif status in (401, 403):
            code = "PROVIDER_AUTH"
        elif 300 <= status < 400:
            code = "PROVIDER_REDIRECT"
        elif status >= 500:
            code = "PROVIDER_UNAVAILABLE"
        else:
            code = "PROVIDER_HTTP_ERROR"
        return ProviderError(code, status)


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
