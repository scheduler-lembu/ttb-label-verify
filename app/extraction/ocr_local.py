"""Cheap / local OCR extractor (batch engine + production-compatible path).

Single responsibility: implement the ``Extractor`` interface using a
cheap/local OCR engine. Two roles:

  * Batch: the default engine for high-volume batch work (cost model — a
    transcribe-only task does not need the premium model for most items).
  * Production: the network-compatible path. TTB's firewall blocks some
    outbound ML endpoints, so a local/on-tenant OCR path (or Azure Document
    Intelligence over a private endpoint) is the production-safe alternative
    (ASM-02).

Like every extractor, it ONLY transcribes; it never judges.

Scaffold pass: class + signature only. No OCR call, no local-OCR dependency.
Local-OCR deps are added in a LATER phase — not this pass.
"""

from __future__ import annotations

from app.extraction.base import Extractor


class LocalOCRExtractor(Extractor):
    """Cheap/local OCR transcription. Config-selected via BATCH_MODEL."""

    def extract(self, image_bytes: bytes):
        """Transcribe the label via local OCR. Stub — no OCR this pass."""
        raise NotImplementedError
