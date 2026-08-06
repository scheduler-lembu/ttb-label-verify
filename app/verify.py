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

from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings
from app.extraction.ocr_local import (
    is_tesseract_available,
    read_warning,
    warning_reads_agree,
)
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


def _downgrade_warning_on_disagreement(label_result: LabelResult) -> LabelResult:
    """If the warning currently PASSes, drop it to NEEDS_REVIEW (reads disagree).
    Only touches a PASS -> more conservative only; never relaxes FAIL/REVIEW."""
    new_fields = []
    changed = False
    for fr in label_result.fields:
        if fr.field == "warning" and fr.verdict == ResultState.PASS:
            new_fields.append(FieldResult(
                field=fr.field, expected=fr.expected, extracted=fr.extracted,
                rule=fr.rule, verdict=ResultState.NEEDS_REVIEW,
                reason=ResultReason.UNREADABLE,
                note="vision and literal-OCR reads of the warning disagree — needs human review",
            ))
            changed = True
        else:
            new_fields.append(fr)
    return LabelResult.from_fields(new_fields) if changed else label_result


def verify_label_with(image_bytes: bytes, expected: dict, extract_fn) -> LabelResult:
    """Core pipeline: quality gate → ``extract_fn`` → matcher → warning cross-check.

    ``extract_fn(image_bytes) -> ExtractionResult`` is the ONLY thing that varies
    between single-label (primary model) and batch (cheap model + dedup cache).
    The quality gate, the literal-OCR warning cross-check, the (unchanged)
    matcher, and the failure branch (all fields NEEDS_REVIEW) are identical for
    both paths.
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

    # STAGE 2: parallel read — vision extract + (optional) literal OCR of the warning.
    xcheck_active = settings.WARNING_XCHECK_ENABLED and is_tesseract_available()
    with ThreadPoolExecutor(max_workers=2) as ex:
        vlm_future = ex.submit(extract_fn, image_bytes)
        ocr_future = ex.submit(read_warning, image_bytes) if xcheck_active else None
        result = vlm_future.result()
        ocr = ocr_future.result() if ocr_future is not None else None

    if not result.ok:
        return _all_needs_review(expected)

    # STAGE 3: the unchanged matcher judges the vision read.
    label_result = run_matchers(expected, result.fields)

    # STAGE 4: warning cross-check — literal OCR can only make a PASS more cautious.
    if xcheck_active and ocr is not None and ocr.available:
        vlm_warning = result.fields.get("warning")
        if not warning_reads_agree(vlm_warning, ocr.text, settings.WARNING_XCHECK_THRESHOLD):
            label_result = _downgrade_warning_on_disagreement(label_result)

    return label_result


def verify_label(image_bytes: bytes, expected: dict) -> LabelResult:
    """Verify one label image against its expected application-data values.

    The single-label (~5s interactive) path: uses the primary extractor
    (``extract_single``). Signature and behavior are unchanged — this is a thin
    wrapper over :func:`verify_label_with`.

    Returns:
        A ``LabelResult`` with a ``FieldResult`` per registry field. If the
        image fails the quality gate or the extractor is unavailable, every
        field is NEEDS_REVIEW and overall rolls up to NEEDS_REVIEW — the app
        degrades gracefully rather than crashing.
    """
    return verify_label_with(image_bytes, expected, extract_single)
