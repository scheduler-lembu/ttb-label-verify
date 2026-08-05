"""Data models for verification results.

Single responsibility: define the pydantic models and the three-state result
enum that flow through the app. This is the shared contract between the
extractor, the matcher, and the UI — "show the work" means every field result
carries the extracted value, the expected value, the rule applied, and the
verdict, never a bare PASS/FAIL.

Scaffold pass: shapes only. No validation logic, no behavior.
"""

from __future__ import annotations

from enum import Enum


class ResultState(str, Enum):
    """The three verdict states. See ARCHITECTURE.md §5.

    NEEDS_REVIEW is both the low-confidence verdict AND the resilience fallback
    (extractor unavailable / timed out) — never a guessed PASS or FAIL. The
    system is biased against a false PASS, the worst failure mode in compliance.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class FieldResult:
    """Verdict for a single label field.

    Intended attributes (implemented later as pydantic fields):
        field: str            # registry key, e.g. "brand", "abv", "warning"
        expected: str | None  # the application-data value the agent supplied
        extracted: str | None # what the extractor transcribed from the label
        rule: str             # the rule type applied (from the field registry)
        state: ResultState    # PASS / FAIL / NEEDS_REVIEW
        detail: str | None    # human-readable explanation ("show the work")
    """

    # Stub only — no fields declared this pass.


class LabelResult:
    """Aggregate result for one label (all fields).

    Intended attributes:
        fields: list[FieldResult]
        overall: ResultState  # rolled up from the per-field states
    """

    # Stub only.


class BatchResult:
    """Aggregate result for a batch submission.

    Intended attributes:
        items: list[LabelResult]         # per-item results (FR-11)
        summary: dict[ResultState, int]  # counts of PASS / FAIL / NEEDS_REVIEW
    """

    # Stub only.
