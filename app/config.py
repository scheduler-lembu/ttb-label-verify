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
    # per-request hard timeout (hang ceiling); typical latency is ~2-3s, the ~5s
    # target is met by normal model latency — this only catches genuine stalls.
    SINGLE_LABEL_TIMEOUT_S: float = 10.0

    # Vision-call hardening (latency + cost).
    VISION_MAX_IMAGE_DIM: int = 1536
    MAX_OUTPUT_TOKENS: int = 700

    # Batch reliability: batch is off the ~5s clock, so give reads a longer
    # timeout and retry transient failures (single-label stays fail-fast).
    BATCH_LABEL_TIMEOUT_S: float = 15.0
    BATCH_MAX_RETRIES: int = 2

    # Application data source (expected values a label is checked against).
    DATA_SOURCE: str = "demo"  # "demo" or "azure"
    DEMO_DB_PATH: str = "sample_data/demo_applications.csv"

    # Access (optional, OFF by default).
    DEMO_PASSWORD: str = ""

    # Pre-extraction image quality gate (cost guard + NFR-05).
    QUALITY_GATE_ENABLED: bool = True
    QUALITY_BLUR_THRESHOLD: float = 60.0
    QUALITY_BLANK_STDDEV: float = 8.0

    # Literal-OCR (Tesseract) warning cross-check.
    WARNING_XCHECK_ENABLED: bool = True
    WARNING_XCHECK_THRESHOLD: float = 90.0

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


def _get_bool(name: str, default: bool) -> bool:
    """Read a boolean env var. "0"/"false"/"no"/"" → False; anything else → True."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("", "0", "false", "no")


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
        SINGLE_LABEL_TIMEOUT_S=_get_float("SINGLE_LABEL_TIMEOUT_S", 10.0),
        VISION_MAX_IMAGE_DIM=_get_int("VISION_MAX_IMAGE_DIM", 1536),
        MAX_OUTPUT_TOKENS=_get_int("MAX_OUTPUT_TOKENS", 700),
        BATCH_LABEL_TIMEOUT_S=_get_float("BATCH_LABEL_TIMEOUT_S", 15.0),
        BATCH_MAX_RETRIES=_get_int("BATCH_MAX_RETRIES", 2),
        DATA_SOURCE=_get("DATA_SOURCE", "demo"),
        DEMO_DB_PATH=_get("DEMO_DB_PATH", "sample_data/demo_applications.csv"),
        DEMO_PASSWORD=_get("DEMO_PASSWORD", ""),
        QUALITY_GATE_ENABLED=_get_bool("QUALITY_GATE_ENABLED", True),
        QUALITY_BLUR_THRESHOLD=_get_float("QUALITY_BLUR_THRESHOLD", 60.0),
        QUALITY_BLANK_STDDEV=_get_float("QUALITY_BLANK_STDDEV", 8.0),
        WARNING_XCHECK_ENABLED=_get_bool("WARNING_XCHECK_ENABLED", True),
        WARNING_XCHECK_THRESHOLD=_get_float("WARNING_XCHECK_THRESHOLD", 90.0),
    )
