"""Extractor router — engine selection + failover chain.

Single responsibility: pick the right engine and chain providers behind the
``Extractor`` interface. Two behaviors (see ARCHITECTURE.md §6/§7):

  * Engine selection: single-label -> premium cloud vision; batch -> cheap/local
    OCR, with ambiguous batch items allowed to escalate to premium.
  * Failover chain: primary -> backup -> NEEDS_REVIEW.
      - SINGLE fails FAST: one primary attempt within the timeout, then
        NEEDS_REVIEW. No serial cross-provider retry (honors the ~5s bar).
      - BATCH MAY retry SERIALLY across providers (per-item latency relaxed).

Providers are config-selected (PRIMARY_MODEL / BACKUP_MODEL / BATCH_MODEL),
never hardcoded.

Scaffold pass: signatures only. No selection or failover logic this pass.
"""

from __future__ import annotations


def select_for_single():
    """Return the extractor to use for a single interactive label. Stub."""
    raise NotImplementedError


def select_for_batch():
    """Return the extractor to use for batch items (cheap/local). Stub."""
    raise NotImplementedError


def extract_with_failover(image_bytes: bytes, *, allow_serial_retry: bool):
    """Run extraction through the failover chain.

    ``allow_serial_retry`` is False for single (fail fast to NEEDS_REVIEW) and
    True for batch (primary -> backup before NEEDS_REVIEW). On exhausting the
    chain, the terminal state is NEEDS_REVIEW — never a guess. Stub.
    """
    raise NotImplementedError
