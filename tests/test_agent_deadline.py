"""Offline checks for budget arithmetic and the approved F-05 configuration."""
from __future__ import annotations

import math

import pytest

from app.agent.config import AUTHORIZED_MODELS, Config, ConfigError, FREE_MODEL
from app.agent.deadline import Deadline


def test_remaining_and_expiry():
    now = [10.0]
    budget = Deadline(3, clock=lambda: now[0])
    assert budget.expires_at == 13
    assert budget.remaining() == 3
    assert budget.expired is False
    now[0] = 12.75
    assert budget.remaining() == 0.25
    now[0] = 13
    assert budget.expired is True
    now[0] = 14
    assert budget.remaining() == 0


@pytest.mark.parametrize("seconds", [0, -1])
def test_expired_budget(seconds):
    budget = Deadline(seconds, clock=lambda: 2)
    assert budget.expired is True
    assert budget.remaining() == 0


@pytest.mark.parametrize("seconds", [True, False, "1", None, math.nan, math.inf, -math.inf])
def test_deadline_rejects_invalid_budget(seconds):
    with pytest.raises(ValueError):
        Deadline(seconds)


def test_f05_config_defaults_preserve_existing_free_model():
    config = Config(api_key="synthetic-key")
    assert config.request_deadline == 30
    assert config.turn_deadline == 120
    assert config.max_tokens == 768
    assert config.provider_failover is False
    assert config.model == FREE_MODEL
    assert len(AUTHORIZED_MODELS) == 2


@pytest.mark.parametrize(("field", "value", "code"), [
    ("request_deadline", 0, "INVALID_REQUEST_DEADLINE"),
    ("request_deadline", 31, "INVALID_REQUEST_DEADLINE"),
    ("request_deadline", True, "INVALID_REQUEST_DEADLINE"),
    ("request_deadline", math.nan, "INVALID_REQUEST_DEADLINE"),
    ("request_deadline", math.inf, "INVALID_REQUEST_DEADLINE"),
    ("request_deadline", 10**1000, "INVALID_REQUEST_DEADLINE"),
    ("request_deadline", "secret-value", "INVALID_REQUEST_DEADLINE"),
    ("turn_deadline", 4.99, "INVALID_TURN_DEADLINE"),
    ("turn_deadline", 121, "INVALID_TURN_DEADLINE"),
    ("turn_deadline", False, "INVALID_TURN_DEADLINE"),
    ("turn_deadline", math.inf, "INVALID_TURN_DEADLINE"),
    ("max_tokens", 127, "INVALID_MAX_TOKENS"),
    ("max_tokens", 2049, "INVALID_MAX_TOKENS"),
    ("max_tokens", 768.0, "INVALID_MAX_TOKENS"),
    ("max_tokens", True, "INVALID_MAX_TOKENS"),
    ("provider_failover", 1, "INVALID_PROVIDER_FAILOVER"),
    ("provider_failover", "true", "INVALID_PROVIDER_FAILOVER"),
])
def test_f05_config_rejects_bad_values_without_echo(field, value, code):
    with pytest.raises(ConfigError) as caught:
        Config(api_key="synthetic-key", **{field: value})
    assert caught.value.code == code
    assert "secret-value" not in str(caught.value)
    assert "synthetic-key" not in str(caught.value)


def test_request_budget_must_fit_turn():
    with pytest.raises(ConfigError) as caught:
        Config(api_key="synthetic-key", request_deadline=20, turn_deadline=10)
    assert caught.value.code == "INVALID_DEADLINE_ORDER"


@pytest.mark.parametrize(("request_seconds", "turn", "tokens"), [(1, 5, 128), (30, 120, 2048), (5, 5, 768)])
def test_config_accepts_approved_boundaries(request_seconds, turn, tokens):
    config = Config(api_key="synthetic-key", request_deadline=request_seconds,
                    turn_deadline=turn, max_tokens=tokens, provider_failover=True)
    assert config.provider_failover is True


def test_new_settings_load_from_literal_dotenv_and_process_overrides(tmp_path):
    path = tmp_path / "settings.env"
    path.write_text("EMPORIO_LLM_REQUEST_DEADLINE=12.5\n"
                    "EMPORIO_LLM_TURN_DEADLINE=50\n"
                    "EMPORIO_LLM_MAX_TOKENS=1024\n"
                    "EMPORIO_LLM_PROVIDER_FAILOVER=true\n", encoding="utf-8")
    config = Config.from_env({"EMPORIO_LLM_API_KEY": "synthetic-key",
                              "EMPORIO_LLM_MAX_TOKENS": "512"}, path)
    assert config.request_deadline == 12.5
    assert config.turn_deadline == 50
    assert config.max_tokens == 512
    assert config.provider_failover is True


@pytest.mark.parametrize(("key", "value", "code"), [
    ("REQUEST_DEADLINE", "secret-value", "INVALID_REQUEST_DEADLINE"),
    ("REQUEST_DEADLINE", "nan", "INVALID_REQUEST_DEADLINE"),
    ("TURN_DEADLINE", "inf", "INVALID_TURN_DEADLINE"),
    ("TURN_DEADLINE", "False", "INVALID_TURN_DEADLINE"),
    ("MAX_TOKENS", "128.0", "INVALID_MAX_TOKENS"),
    ("MAX_TOKENS", "true", "INVALID_MAX_TOKENS"),
    ("PROVIDER_FAILOVER", "1", "INVALID_PROVIDER_FAILOVER"),
    ("PROVIDER_FAILOVER", "yes", "INVALID_PROVIDER_FAILOVER"),
    ("PROVIDER_FAILOVER", "secret-value", "INVALID_PROVIDER_FAILOVER"),
])
def test_new_env_errors_are_sanitized(key, value, code):
    with pytest.raises(ConfigError) as caught:
        Config.from_env({"EMPORIO_LLM_API_KEY": "synthetic-key",
                         "EMPORIO_LLM_" + key: value}, dotenv_path=None)
    assert caught.value.code == code
    assert "synthetic-key" not in str(caught.value)
    assert "secret-value" not in str(caught.value)


def test_default_off_boolean_can_be_set_explicitly():
    config = Config.from_env({"EMPORIO_LLM_API_KEY": "synthetic-key",
                              "EMPORIO_LLM_PROVIDER_FAILOVER": "false"}, None)
    assert config.provider_failover is False
