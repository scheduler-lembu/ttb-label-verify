"""Application configuration.

Single responsibility: read environment variables (see ``.env.example``) and
expose them as a single typed settings object. Providers and cost/concurrency
knobs are **config-selected, never hardcoded** — including model choice, which
determines whether the primary engine is the public cloud API or its Azure
OpenAI twin in production.

No model prices are ever stored here — the provider/price is chosen at build
time. The API key is never printed or logged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    """Typed view over the environment knobs defined in ``.env.example``."""

    # Provider selection (config-selected; never hardcoded in logic).
    PRIMARY_MODEL: str = "gpt-5.6-terra"
    BACKUP_MODEL: str = ""
    BATCH_MODEL: str = "gpt-5.6-luna"
    API_KEY: str = ""

    # Concurrency & cost guards (batch knobs used in a later pass).
    MAX_CONCURRENCY: int = 4
    MAX_BATCH_ITEMS: int = 300
    PER_BATCH_COST_CEILING: float = 0.0
    MAX_UPLOAD_MB: int = 10
    SINGLE_LABEL_TIMEOUT_S: float = 5.0

    # Access (optional, OFF by default).
    DEMO_PASSWORD: str = ""

    def has_api_key(self) -> bool:
        """True if an API key is configured (never exposes the value)."""
        return bool(self.API_KEY.strip())


def _get(name: str, default: str) -> str:
    """Return env var ``name`` if set and non-empty, else ``default``."""
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _get_int(name: str, default: int) -> int:
    try:
        return int(float(_get(name, str(default))))
    except (TypeError, ValueError):
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(_get(name, str(default)))
    except (TypeError, ValueError):
        return default


def get_settings() -> Settings:
    """Return the process-wide :class:`Settings`, read from the environment.

    Loads ``.env`` (via python-dotenv) if present, then reads each knob with a
    safe default. Malformed numeric values fall back to their default rather
    than crashing.
    """
    load_dotenv()  # populates os.environ from .env if the file exists
    return Settings(
        PRIMARY_MODEL=_get("PRIMARY_MODEL", "gpt-5.6-terra"),
        BACKUP_MODEL=_get("BACKUP_MODEL", ""),
        BATCH_MODEL=_get("BATCH_MODEL", "gpt-5.6-luna"),
        API_KEY=_get("API_KEY", ""),
        MAX_CONCURRENCY=_get_int("MAX_CONCURRENCY", 4),
        MAX_BATCH_ITEMS=_get_int("MAX_BATCH_ITEMS", 300),
        PER_BATCH_COST_CEILING=_get_float("PER_BATCH_COST_CEILING", 0.0),
        MAX_UPLOAD_MB=_get_int("MAX_UPLOAD_MB", 10),
        SINGLE_LABEL_TIMEOUT_S=_get_float("SINGLE_LABEL_TIMEOUT_S", 5.0),
        DEMO_PASSWORD=_get("DEMO_PASSWORD", ""),
    )
