"""Extractor router — engine selection + failover chain.

Single responsibility: pick the right engine and (later) chain providers behind
the ``Extractor`` interface. This pass wires the **single-label** path only:

  * Engine selection: single-label → premium cloud vision (OpenAI).
  * Failover: single fails FAST — one primary attempt within the timeout, then
    the caller degrades to NEEDS_REVIEW. No serial cross-provider retry here
    (honors the ~5s bar). Backup-provider failover and the cheap batch engine
    are LATER passes.

Providers are config-selected (PRIMARY_MODEL / BACKUP_MODEL / BATCH_MODEL),
never hardcoded.
"""

from __future__ import annotations

import time

from app.config import get_settings
from app.extraction.base import ExtractionResult, Extractor
from app.extraction.vision_llm import OpenAIVisionExtractor

# Tiny backoff between batch retry attempts (batch is off the ~5s clock).
_RETRY_BACKOFF_S = 0.25


def get_single_extractor() -> Extractor:
    """Return the extractor to use for a single interactive label (primary)."""
    return OpenAIVisionExtractor()


def extract_single(image_bytes: bytes) -> ExtractionResult:
    """Run single-label extraction through the primary engine (fail-fast).

    On ``ok=False`` the result is returned as-is — the caller (verify) maps it to
    NEEDS_REVIEW.

    TODO (later pass): backup-provider failover. When BACKUP_MODEL is configured,
    a failed primary MAY fall through to the backup for BATCH only (serial retry
    is allowed there); single-label stays fail-fast and must not add serial
    cross-provider retries, to honor the ~5s bar.
    """
    extractor = get_single_extractor()
    return extractor.extract(image_bytes)


def get_batch_extractor() -> Extractor:
    """Return the batch extractor — the cheap BATCH_MODEL (Luna) tier + longer timeout."""
    settings = get_settings()
    return OpenAIVisionExtractor(
        settings=settings,
        model=settings.BATCH_MODEL,
        timeout_s=settings.BATCH_LABEL_TIMEOUT_S,
    )


def extract_batch(image_bytes: bytes, cache) -> ExtractionResult:
    """Batch extraction with image-hash dedup + bounded retry on transient failure.

    A cache HIT returns the stored ``ExtractionResult`` with NO API call and NO
    retry. A MISS calls the batch engine; because batch is off the ~5s clock, a
    failed read (ok=False / hiccup) is retried up to ``BATCH_MAX_RETRIES`` times
    (with a tiny backoff) before giving up and returning the not-ok result (which
    verify turns into NEEDS_REVIEW). Only a successful read is cached (a failure
    is never cached, so a transient error isn't stuck). ``cache`` is passed in so
    the caller owns one shared instance — no module global.
    """
    key = cache.key(image_bytes)
    cached = cache.get(key)
    if cached is not None:
        return cached

    settings = get_settings()
    attempts = 1 + max(0, int(settings.BATCH_MAX_RETRIES))
    extractor = get_batch_extractor()
    result: ExtractionResult | None = None
    for attempt in range(attempts):
        result = extractor.extract(image_bytes)
        if result.ok:
            cache.put(key, result)
            return result
        if attempt < attempts - 1:
            time.sleep(_RETRY_BACKOFF_S)  # transient — brief pause, then retry
    return result  # exhausted attempts; not-ok -> caller degrades to NEEDS_REVIEW
