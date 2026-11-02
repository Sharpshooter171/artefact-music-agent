"""Offline transport/configuration tests; all credentials are synthetic."""
from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from app.agent.config import (
    AUTHORIZED_MODELS,
    FREE_MODEL,
    NEMOTRON_FREE_MODEL,
    OPENROUTER_BASE_URL,
    Config,
    ConfigError,
)
from app.agent.llm_client import ChatClient, ProviderError, MAX_RESPONSE_BYTES, NoRedirect


KEY = "synthetic-test-credential"


def configuration(**overrides):
    return Config.from_env({"EMPORIO_LLM_API_KEY": KEY, **overrides}, dotenv_path=None)


def envelope(message=None, **overrides):
    return {"model": FREE_MODEL, "choices": [{"finish_reason": "stop", "message": message or {
        "role": "assistant", "content": "Olá! Posso ajudar com a loja?",
    }}], "usage": {"cost": 0}, **overrides}


class Response(io.BytesIO):
    status = 200


def make_client(payload=None, raw=None, config=None):
    captured = []
    def opener(request, *, timeout):
        captured.append((request, timeout))
        return Response(raw if raw is not None else json.dumps(payload or envelope()).encode())
    return ChatClient(config or configuration(), opener=opener), captured


def test_config_defaults_are_authorized_free_endpoint_and_model():
    config = configuration()
    assert config.base_url == OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"
    assert config.model == FREE_MODEL == "openrouter/free"
    assert config.timeout == 30
    assert KEY not in repr(config)
    assert AUTHORIZED_MODELS == {FREE_MODEL, NEMOTRON_FREE_MODEL}


def test_explicit_nemotron_free_model_is_authorized():
    config = configuration(EMPORIO_LLM_MODEL=NEMOTRON_FREE_MODEL)

    assert config.model == NEMOTRON_FREE_MODEL
    assert KEY not in repr(config)


def test_nemotron_request_pins_exact_model_and_accepts_exact_response():
    config = configuration(EMPORIO_LLM_MODEL=NEMOTRON_FREE_MODEL)
    client, captured = make_client(
        envelope(model=NEMOTRON_FREE_MODEL),
        config=config,
    )

    result = client.complete([{"role": "user", "content": "Olá"}], [])

    assert result["role"] == "assistant"
    assert json.loads(captured[0][0].data)["model"] == NEMOTRON_FREE_MODEL
    assert client.last_model == NEMOTRON_FREE_MODEL
    assert client.last_error_code is None


def test_explicit_nemotron_model_rejects_different_free_response_model():
    config = configuration(EMPORIO_LLM_MODEL=NEMOTRON_FREE_MODEL)
    client, _ = make_client(
        envelope(model="upstage/solar-pro-3:free"),
        config=config,
    )

    with pytest.raises(ProviderError) as caught:
        client.complete([], [])

    assert caught.value.code == "UNAUTHORIZED_RESPONSE_MODEL"
    assert client.last_model is None


@pytest.mark.parametrize("env,code", [
    ({}, "MISSING_API_KEY"),
    ({"EMPORIO_LLM_API_KEY": ""}, "MISSING_API_KEY"),
    ({"EMPORIO_LLM_API_KEY": "bad\nheader"}, "INVALID_API_KEY"),
    ({"EMPORIO_LLM_MODEL": "qwen/qwen3.8-27b"}, "UNAUTHORIZED_MODEL"),
    ({"EMPORIO_LLM_MODEL": "qwen/qwen3.8-27b:free"}, "UNAUTHORIZED_MODEL"),
    ({"EMPORIO_LLM_MODEL": "different:free"}, "UNAUTHORIZED_MODEL"),
    ({"EMPORIO_LLM_BASE_URL": "http://openrouter.ai/api/v1"}, "UNAUTHORIZED_ENDPOINT"),
    ({"EMPORIO_LLM_BASE_URL": "https://attacker.invalid/v1"}, "UNAUTHORIZED_ENDPOINT"),
    ({"EMPORIO_LLM_BASE_URL": "https://openrouter.ai/api/v1?key=secret"}, "UNAUTHORIZED_ENDPOINT"),
    ({"EMPORIO_LLM_TIMEOUT": "0"}, "INVALID_TIMEOUT"),
    ({"EMPORIO_LLM_TIMEOUT": "31"}, "INVALID_TIMEOUT"),
    ({"EMPORIO_LLM_TIMEOUT": "NaN"}, "INVALID_TIMEOUT"),
    ({"EMPORIO_LLM_TIMEOUT": "True"}, "INVALID_TIMEOUT"),
])
def test_invalid_configuration_is_sanitized(env, code):
    values = {"EMPORIO_LLM_API_KEY": KEY, **env} if env else env
    with pytest.raises(ConfigError) as caught:
        Config.from_env(values, dotenv_path=None)
    assert caught.value.code == code
    assert KEY not in str(caught.value)
    assert "attacker" not in str(caught.value)


def test_dotenv_literal_loading_preserves_file_and_process_precedence(tmp_path):
    path = tmp_path / ".env"
    contents = "# local config\nexport OPENROUTER_API_KEY='$(touch NEVER)'\nOPENROUTER_MODEL=openrouter/free\nEMPORIO_LLM_TIMEOUT=5 # seconds\n"
    path.write_text(contents)
    config = Config.from_env({}, dotenv_path=path)
    assert config.api_key == "$(touch NEVER)"
    assert config.timeout == 5
    config = Config.from_env({"EMPORIO_LLM_API_KEY": KEY}, dotenv_path=path)
    assert config.api_key == KEY
    assert path.read_text() == contents
    assert not (tmp_path / "NEVER").exists()


def test_explicit_environment_alias_beats_dotenv_primary(tmp_path):
    path = tmp_path / ".env"
    path.write_text("EMPORIO_LLM_API_KEY=file-value\n")
    assert Config.from_env({"OPENROUTER_API_KEY": KEY}, dotenv_path=path).api_key == KEY


def test_missing_dotenv_is_allowed(tmp_path):
    assert Config.from_env({"OPENROUTER_API_KEY": KEY}, dotenv_path=tmp_path/"absent").api_key == KEY


@pytest.mark.parametrize("text", ["EMPORIO_LLM_API_KEY='unterminated", "EMPORIO_LLM_API_KEY=one\nnot-an-assignment", "EMPORIO_LLM_API_KEY=one\x00two"])
def test_invalid_dotenv_fails_safely(tmp_path, text):
    path = tmp_path / ".env"
    path.write_text(text)
    with pytest.raises(ConfigError) as caught:
        Config.from_env({}, dotenv_path=path)
    assert caught.value.code == "INVALID_DOTENV"
    assert "unterminated" not in str(caught.value)


def test_request_protocol_free_caps_auth_timeout_and_observability():
    client, captured = make_client()
    messages = [{"role": "user", "content": "Olá"}]
    tools = [{"type": "function", "function": {"name": "list_categories", "parameters": {"type": "object"}}}]
    assert client.complete(messages, tools)["role"] == "assistant"
    request, timeout = captured[0]
    payload = json.loads(request.data)
    assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == f"Bearer {KEY}"
    assert payload["model"] == FREE_MODEL
    assert payload["messages"] == messages and payload["tools"] == tools
    assert payload["provider"]["max_price"] == {"prompt": 0, "completion": 0, "request": 0, "image": 0}
    assert payload["provider"]["allow_fallbacks"] is False
    assert payload["provider"]["require_parameters"] is True
    assert "models" not in payload and payload["stream"] is False
    # Requiring support for this optional provider flag excluded every free
    # endpoint in the observed live integration. The host already bounds and
    # validates batches, so routing must not depend on this optional capability.
    assert "parallel_tool_calls" not in payload
    assert 1 <= payload["max_tokens"] <= 4096
    assert timeout == 30
    assert client.last_model == FREE_MODEL and client.last_http_status == 200
    assert client.last_error_code is None
    assert client.last_cost == 0


def test_tool_call_message_is_preserved_without_private_reasoning():
    message = {"role": "assistant", "content": None, "reasoning": "internal", "tool_calls": [
        {"id": "call_1", "type": "function", "function": {"name": "list_categories", "arguments": "{}"}},
    ]}
    client, _ = make_client(envelope(message))
    result = client.complete([], [])
    assert result["tool_calls"] == message["tool_calls"]
    assert "reasoning" not in result


@pytest.mark.parametrize("actual_model", ["upstage/solar-pro-3:free", "qwen/qwen3-next-80b-a3b-instruct:free"])
def test_free_router_records_concrete_free_model_without_requiring_alias_echo(actual_model):
    client, captured = make_client(envelope(model=actual_model))
    result = client.complete([{"role": "user", "content": "Olá"}], [])
    assert result["role"] == "assistant"
    assert json.loads(captured[0][0].data)["model"] == "openrouter/free"
    assert client.last_model == actual_model
    assert client.last_cost == 0


@pytest.mark.parametrize("actual_model", [
    "paid/model", "upstage/solar-pro-3", "openrouter/auto", "/:free",
    "not-a-provider-model:free", "paid/model:free?paid=true", "provider/model:free\n",
])
def test_free_router_rejects_paid_aliases_and_invalid_returned_model_ids(actual_model):
    client, _ = make_client(envelope(model=actual_model))
    with pytest.raises(ProviderError) as caught:
        client.complete([], [])
    assert caught.value.code == "UNAUTHORIZED_RESPONSE_MODEL"
    assert client.last_model is None


@pytest.mark.parametrize("status,code", [(401,"PROVIDER_AUTH"),(403,"PROVIDER_AUTH"),(429,"PROVIDER_RATE_LIMIT"),(500,"PROVIDER_UNAVAILABLE"),(503,"PROVIDER_UNAVAILABLE"),(404,"PROVIDER_HTTP_ERROR"),(302,"PROVIDER_REDIRECT")])
def test_http_errors_do_not_retry_or_expose_body(status, code):
    calls = []
    def opener(request, *, timeout):
        calls.append(request)
        raise HTTPError(request.full_url, status, KEY, {}, io.BytesIO(KEY.encode()))
    client = ChatClient(configuration(), opener=opener)
    with pytest.raises(ProviderError) as caught:
        client.complete([], [])
    assert caught.value.code == code and caught.value.http_status == status
    assert client.last_http_status == status and client.last_error_code == code
    assert len(calls) == 1
    assert KEY not in str(caught.value) and KEY not in repr(caught.value)


@pytest.mark.parametrize("error", [TimeoutError(KEY), URLError(KEY), OSError(KEY), ValueError(KEY)])
def test_network_errors_are_sanitized(error):
    def opener(request, *, timeout):
        raise error
    client = ChatClient(configuration(), opener=opener)
    with pytest.raises(ProviderError) as caught:
        client.complete([], [])
    assert caught.value.code in {"PROVIDER_TIMEOUT", "PROVIDER_UNAVAILABLE"}
    assert KEY not in str(caught.value)
    assert client.last_http_status is None


@pytest.mark.parametrize("raw", [b"not JSON", b"[]", b"null", b"{}", b'{}'+b' '*MAX_RESPONSE_BYTES, b'\xff'])
def test_bad_or_oversized_response_fails_closed(raw):
    client, _ = make_client(raw=raw)
    with pytest.raises(ProviderError):
        client.complete([], [])


@pytest.mark.parametrize("changes", [
    {"choices": []}, {"choices": None}, {"choices": [None]},
    {"choices": [{"message": {"role": "user", "content": "bad"}}]},
    {"choices": [{"message": {"role": "assistant", "content": []}}]},
    {"choices": [{"message": {"role": "assistant", "content": None}}]},
    {"choices": [{"finish_reason": "length", "message": {"role": "assistant", "content": "truncated"}}]},
    {"choices": [{"message": {"role": "assistant", "tool_calls": "bad"}}]},
    {"choices": [{"message": {"role": "assistant", "tool_calls": [None]}}]},
    {"model": "paid/model"}, {"model": None}, {"usage": {"cost": 0.01}},
    {"usage": {"cost": "NaN"}}, {"usage": {"cost": True}},
])
def test_malformed_or_unauthorized_completions_fail_closed(changes):
    client, _ = make_client(envelope(**changes))
    with pytest.raises(ProviderError):
        client.complete([], [])


@pytest.mark.parametrize("key", [KEY, 'synthetic-"quote', "synthetic-\\slash"])
def test_key_echo_from_provider_cannot_escape(key):
    client, _ = make_client(envelope({"role": "assistant", "content": key}))
    client.config = configuration(EMPORIO_LLM_API_KEY=key)
    with pytest.raises(ProviderError) as caught:
        client.complete([], [])
    assert key not in str(caught.value)


def test_key_echo_in_routed_model_metadata_cannot_escape():
    client, _ = make_client(envelope(model=f"provider/{KEY}:free"))
    with pytest.raises(ProviderError) as caught:
        client.complete([], [])
    assert caught.value.code == "UNSAFE_RESPONSE"
    assert KEY not in str(caught.value)
    assert client.last_model is None


def test_redirect_handler_never_constructs_followup_request():
    assert NoRedirect().redirect_request(None, None, 302, None, {}, "https://attacker.invalid") is None


def test_no_network_on_config_or_client_construction(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("network unexpectedly called")
    monkeypatch.setattr("urllib.request.OpenerDirector.open", forbidden)
    ChatClient(configuration())


@pytest.mark.parametrize('enabled', [False, True])
def test_f05_provider_failover_keeps_exact_model_and_zero_cost(enabled):
    from dataclasses import replace
    config = replace(configuration(EMPORIO_LLM_MODEL=NEMOTRON_FREE_MODEL),
                     provider_failover=enabled, max_tokens=768)
    client, captured = make_client(envelope(model=NEMOTRON_FREE_MODEL), config=config)
    client.complete([], [])
    payload = json.loads(captured[0][0].data)
    assert payload['model'] == NEMOTRON_FREE_MODEL
    assert payload['provider'] == {
        'allow_fallbacks': enabled, 'require_parameters': True,
        'max_price': {'prompt': 0, 'completion': 0, 'request': 0, 'image': 0},
    }
    assert payload['max_tokens'] == 768
    assert 'models' not in payload


def test_f05_client_metadata_is_bounded_and_contains_no_customer_text():
    client, _ = make_client()
    customer_text = 'synthetic-private-question-do-not-log'
    client.complete([{'role': 'user', 'content': customer_text}], [])
    observation = client.last_diagnostic
    assert set(observation) == {'http_status', 'returned_model', 'latency_ms', 'error_code'}
    assert observation['http_status'] == 200
    assert observation['latency_ms'] >= 0
    assert customer_text not in repr(observation)
    assert KEY not in repr(observation)
