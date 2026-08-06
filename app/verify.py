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

from app.config import get_settings
from app.extraction.router import extract_single
from app.fields import FIELD_REGISTRY
from app.matching.rules import run_matchers
from app.models import FieldResult, LabelResult, ResultReason, ResultState
from app.quality_gate import check_quality

_UNAVAILABLE_NOTE = "extractor unavailable — needs human review"


def _all_needs_review(
    expected: dict,
    note: str = _UNAVAILABLE_NOTE,
    reason: ResultReason = ResultReason.UNREADABLE,
) -> LabelResult:
    """Every registry field → NEEDS_REVIEW (graceful degradation).

    ``note``/``reason`` default to the extractor-unavailable case so existing
    behavior is unchanged; the quality gate passes its own note.
    """
    fields = [
        FieldResult(
            field=field_def.key,
            expected=expected.get(field_def.key),
            extracted=None,
            rule="extraction unavailable",
            verdict=ResultState.NEEDS_REVIEW,
            reason=reason,
            note=note,
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
        image fails the quality gate or the extractor is unavailable, every
        field is NEEDS_REVIEW and overall rolls up to NEEDS_REVIEW — the app
        degrades gracefully rather than crashing.
    """
    # STAGE 1: image quality gate — reject unreadable uploads BEFORE any API call.
    settings = get_settings()
    if settings.QUALITY_GATE_ENABLED:
        q = check_quality(
            image_bytes,
            blur_threshold=settings.QUALITY_BLUR_THRESHOLD,
            blank_stddev=settings.QUALITY_BLANK_STDDEV,
        )
        if not q.ok:
            return _all_needs_review(
                expected,
                note=f"image failed quality check ({q.reason}) — please upload a clearer photo",
            )

    # STAGE 2: extract, then let the (unchanged) matcher judge.
    result = extract_single(image_bytes)
    if result.ok:
        return run_matchers(expected, result.fields)
    return _all_needs_review(expected)
