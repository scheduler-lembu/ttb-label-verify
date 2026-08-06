"""Single-label orchestrator (the ~5s interactive path).

Single responsibility: run one label through the pipeline
    router -> extractor -> matchers -> assemble LabelResult
under the fail-fast ~5s budget (NFR-01). "AI reads, code judges": this module
calls the extractor to transcribe, then hands the transcription to the UNCHANGED
``run_matchers`` for every verdict. It never judges a field itself.

On extractor failure/timeout the affected fields resolve to NEEDS_REVIEW — no
serial cross-provider retry (that would violate the 5-second bar), never a crash
(NFR-05/06), never a guess.
"""

from __future__ import annotations

from app.extraction.router import extract_single
from app.fields import FIELD_REGISTRY
from app.matching.rules import run_matchers
from app.models import FieldResult, LabelResult, ResultReason, ResultState

_UNAVAILABLE_NOTE = "extractor unavailable — needs human review"


def _all_needs_review(expected: dict) -> LabelResult:
    """Every registry field → NEEDS_REVIEW / UNREADABLE (graceful degradation)."""
    fields = [
        FieldResult(
            field=field_def.key,
            expected=expected.get(field_def.key),
            extracted=None,
            rule="extraction unavailable",
            verdict=ResultState.NEEDS_REVIEW,
            reason=ResultReason.UNREADABLE,
            note=_UNAVAILABLE_NOTE,
        )
        for field_def in FIELD_REGISTRY
    ]
    return LabelResult.from_fields(fields)


def verify_label(image_bytes: bytes, expected: dict) -> LabelResult:
    """Verify one label image against its expected application-data values.

    Args:
        image_bytes: the uploaded label image.
        expected: field-key → expected value (from the on-screen form).

    Returns:
        A ``LabelResult`` with a ``FieldResult`` per registry field. If the
        extractor is unavailable, every field is NEEDS_REVIEW and overall rolls
        up to NEEDS_REVIEW — the app degrades gracefully rather than crashing.
    """
    result = extract_single(image_bytes)
    if result.ok:
        return run_matchers(expected, result.fields)
    return _all_needs_review(expected)
