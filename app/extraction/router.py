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

from app.extraction.base import ExtractionResult, Extractor
from app.extraction.vision_llm import OpenAIVisionExtractor


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
