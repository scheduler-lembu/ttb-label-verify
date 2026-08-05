"""Abstract Extractor interface.

Single responsibility: define the one contract every extractor implements, so
providers are swappable via config and chainable for failover. The interface
exposes a single operation — transcribe an image into structured fields — plus
an ok/confidence flag the router uses to decide accept / fail over / escalate.

Scaffold pass: interface only. No extraction logic in any implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ExtractionResult:
    """What an extractor returns.

    Intended attributes:
        fields: dict[str, str]  # transcribed label fields (brand, abv, warning, ...)
        ok: bool                # False if the engine could not read the label
        confidence: float       # 0..1; low confidence -> router may fail over / NEEDS_REVIEW
        engine: str             # which provider produced this (for auditing)
    """

    # Stub only.


class Extractor(ABC):
    """Transcribe a label image into structured fields. Judgment lives elsewhere."""

    @abstractmethod
    def extract(self, image_bytes: bytes) -> "ExtractionResult":
        """Transcribe ``image_bytes`` into an :class:`ExtractionResult`.

        Implementations MUST NOT compare against expected values — extraction
        only reads. Stub: no behavior this pass.
        """
        raise NotImplementedError
