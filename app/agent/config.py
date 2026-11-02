"""Local configuration with literal .env parsing and a free-only provider lock."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import re
from collections.abc import Mapping


FREE_MODEL = "openrouter/free"
NEMOTRON_FREE_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
AUTHORIZED_MODELS = frozenset({FREE_MODEL, NEMOTRON_FREE_MODEL})
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_CONFIG_KEYS = {
    "EMPORIO_LLM_API_KEY", "EMPORIO_LLM_MODEL", "EMPORIO_LLM_BASE_URL",
    "EMPORIO_LLM_TIMEOUT", "OPENROUTER_API_KEY", "OPENROUTER_MODEL",
    "OPENROUTER_BASE_URL", "EMPORIO_CATALOG_DB", "EMPORIO_POLICY_INDEX",
    "EMPORIO_LLM_REQUEST_DEADLINE", "EMPORIO_LLM_TURN_DEADLINE",
    "EMPORIO_LLM_MAX_TOKENS", "EMPORIO_LLM_PROVIDER_FAILOVER",
}


class ConfigError(Exception):
    """Only a fixed code is exposed; never include configuration values."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Configuração inválida ({code}).")


@dataclass(frozen=True)
class Config:
    api_key: str = field(repr=False)
    model: str = FREE_MODEL
    base_url: str = OPENROUTER_BASE_URL
    timeout: float = 30
    request_deadline: float = 20
    turn_deadline: float = 45
    max_tokens: int = 768
    provider_failover: bool = False

    def __post_init__(self):
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise ConfigError("MISSING_API_KEY")
        if any(ord(char) < 32 or ord(char) == 127 for char in self.api_key):
            raise ConfigError("INVALID_API_KEY")
        if self.model not in AUTHORIZED_MODELS:
            raise ConfigError("UNAUTHORIZED_MODEL")
        if self.base_url != OPENROUTER_BASE_URL:
            raise ConfigError("UNAUTHORIZED_ENDPOINT")
        if (isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float))
                or not math.isfinite(self.timeout) or not 1 <= self.timeout <= 30):
            raise ConfigError("INVALID_TIMEOUT")
        for value, lower, upper, code in (
            (self.request_deadline, 1, 30, "INVALID_REQUEST_DEADLINE"),
            (self.turn_deadline, 5, 120, "INVALID_TURN_DEADLINE"),
        ):
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not lower <= value <= upper or not math.isfinite(value)):
                raise ConfigError(code)
        if self.request_deadline > self.turn_deadline:
            raise ConfigError("INVALID_DEADLINE_ORDER")
        if type(self.max_tokens) is not int or not 128 <= self.max_tokens <= 2048:
            raise ConfigError("INVALID_MAX_TOKENS")
        if type(self.provider_failover) is not bool:
            raise ConfigError("INVALID_PROVIDER_FAILOVER")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None,
                 dotenv_path: Path | None = Path(".env")) -> Config:
        """Read assignments as data. Process settings override file aliases too.

        No shell, eval, variable expansion, escaping, network access, or writes.
        Only recognized non-secret artifact paths are copied to process env for
        the unchanged F-01/F-02 tools, and only in the normal process-env mode.
        """
        process = dict(os.environ if env is None else env)
        local = _read_dotenv(dotenv_path) if dotenv_path is not None else {}

        def setting(primary, alias=None, default=None):
            names = (primary, alias) if alias else (primary,)
            for source in (process, local):
                for name in names:
                    if name in source:
                        return source[name]
            return default

        try:
            timeout = float(setting("EMPORIO_LLM_TIMEOUT", default="30"))
        except (ValueError, TypeError):
            raise ConfigError("INVALID_TIMEOUT") from None

        def number(name, default, code, convert=float):
            raw = setting(name, default=default)
            try:
                if not isinstance(raw, str):
                    raise ValueError
                return convert(raw)
            except (ValueError, TypeError, OverflowError):
                raise ConfigError(code) from None

        failover = setting("EMPORIO_LLM_PROVIDER_FAILOVER", default="false")
        if failover not in ("true", "false"):
            raise ConfigError("INVALID_PROVIDER_FAILOVER")
        config = cls(
            api_key=setting("EMPORIO_LLM_API_KEY", "OPENROUTER_API_KEY", ""),
            model=setting("EMPORIO_LLM_MODEL", "OPENROUTER_MODEL", FREE_MODEL),
            base_url=setting("EMPORIO_LLM_BASE_URL", "OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
            timeout=timeout,
            request_deadline=number("EMPORIO_LLM_REQUEST_DEADLINE", "20", "INVALID_REQUEST_DEADLINE"),
            turn_deadline=number("EMPORIO_LLM_TURN_DEADLINE", "45", "INVALID_TURN_DEADLINE"),
            max_tokens=number("EMPORIO_LLM_MAX_TOKENS", "768", "INVALID_MAX_TOKENS", int),
            provider_failover=failover == "true",
        )
        if env is None:
            for name in ("EMPORIO_CATALOG_DB", "EMPORIO_POLICY_INDEX"):
                if name in local:
                    os.environ.setdefault(name, local[name])
        return config


def _read_dotenv(path: Path) -> dict[str, str]:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            text = handle.read(65537)
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError):
        raise ConfigError("INVALID_DOTENV") from None
    if len(text) > 65536 or "\x00" in text:
        raise ConfigError("INVALID_DOTENV")
    values = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if match is None:
            raise ConfigError("INVALID_DOTENV")
        name, value = match.groups()
        if value.startswith(("'", '"')):
            quote = value[0]
            end = value.find(quote, 1)
            if end < 0 or (value[end+1:].strip() and not value[end+1:].strip().startswith("#")):
                raise ConfigError("INVALID_DOTENV")
            value = value[1:end]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        if name in _CONFIG_KEYS:
            values[name] = value
    return values
