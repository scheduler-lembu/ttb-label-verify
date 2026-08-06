"""Abstract Extractor interface.

Single responsibility: define the one contract every extractor implements, so
providers are swappable via config and chainable for failover. The interface
exposes a single operation — transcribe an image into structured fields — plus
an ``ok`` flag the router/verify layer uses to decide accept vs. NEEDS_REVIEW.

Judgment lives elsewhere: an extractor ONLY reads. It never compares against
expected values and never decides PASS/FAIL. This is the interface-level
enforcement of "AI reads, code judges" (GA-1) — by giving every provider a
transcribe-only contract, the AI can never become the decider no matter which
engine config selects (D-1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """What an extractor returns.

    Attributes:
        fields: transcribed label fields keyed by the field-registry keys
            (brand, alcohol_content, warning, class_type, net_contents,
            producer, country_of_origin). A value is the transcribed string or
            ``None`` when the field is absent/unreadable — never a guess.
        ok: False if the engine could not read the label (timeout/error);
            downstream that maps every field to NEEDS_REVIEW.
        error: short error string when ``ok`` is False (for logs/harness).
    """

    fields: dict[str, "str | None"] = Field(default_factory=dict)
    ok: bool
    error: "str | None" = None


class Extractor(ABC):
    """Transcribe a label image into structured fields. Judgment lives elsewhere."""

    @abstractmethod
    def extract(self, image_bytes: bytes) -> ExtractionResult:
        """Transcribe ``image_bytes`` into an :class:`ExtractionResult`.

        Implementations MUST NOT compare against expected values — extraction
        only reads.
        """
        raise NotImplementedError
