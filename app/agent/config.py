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
        config = cls(
            api_key=setting("EMPORIO_LLM_API_KEY", "OPENROUTER_API_KEY", ""),
            model=setting("EMPORIO_LLM_MODEL", "OPENROUTER_MODEL", FREE_MODEL),
            base_url=setting("EMPORIO_LLM_BASE_URL", "OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
            timeout=timeout,
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
