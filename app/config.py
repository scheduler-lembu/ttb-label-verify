"""Application configuration.

Single responsibility: read environment variables (see ``.env.example``) and
expose them as a single typed settings object. Providers and cost/concurrency
knobs are **config-selected, never hardcoded** — including model choice, which
determines whether the primary engine is the public cloud API or its Azure
OpenAI twin in production.

Scaffold pass: declare the settings shape only. No behavior, no validation
logic, no side effects.
"""

from __future__ import annotations


class Settings:
    """Typed view over the environment knobs defined in ``.env.example``.

    Fields (see ``.env.example`` for the authoritative comments):
        Extraction providers (config-selected):
            PRIMARY_MODEL, BACKUP_MODEL, BATCH_MODEL, API_KEY
        Concurrency & cost guards:
            MAX_CONCURRENCY, MAX_BATCH_ITEMS, PER_BATCH_COST_CEILING,
            MAX_UPLOAD_MB, SINGLE_LABEL_TIMEOUT_S
        Access (optional, OFF by default):
            DEMO_PASSWORD

    No model prices are ever stored here — the provider/price is chosen at
    build time.
    """

    # Provider selection (config-selected; no logic this pass)
    PRIMARY_MODEL: str
    BACKUP_MODEL: str
    BATCH_MODEL: str
    API_KEY: str

    # Concurrency & cost guards
    MAX_CONCURRENCY: int
    MAX_BATCH_ITEMS: int
    PER_BATCH_COST_CEILING: float
    MAX_UPLOAD_MB: int
    SINGLE_LABEL_TIMEOUT_S: float

    # Access (optional, OFF by default)
    DEMO_PASSWORD: str


def get_settings() -> Settings:
    """Return the process-wide :class:`Settings`, read from the environment.

    Stub: real implementation reads env vars (via python-dotenv) and returns a
    populated, validated ``Settings``. No behavior this pass.
    """
    raise NotImplementedError
