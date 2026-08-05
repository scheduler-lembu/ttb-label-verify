"""Data models for verification results.

Single responsibility: define the pydantic models and the three-state result
enum that flow through the app. This is the shared contract between the
extractor, the matcher, and the UI — "show the work" means every field result
carries the extracted value, the expected value, the rule applied, and the
verdict, never a bare PASS/FAIL.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ResultState(str, Enum):
    """The three verdict states. See ARCHITECTURE.md §5.

    NEEDS_REVIEW is both the low-confidence verdict AND the resilience fallback
    (extractor unavailable / timed out) — never a guessed PASS or FAIL. The
    system is biased against a false PASS, the worst failure mode in compliance.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ResultReason(str, Enum):
    """Machine-readable category behind a verdict.

    ``reason`` is the sortable/groupable code (lets 47 agents triage "all
    blanks" or filter a batch by field); ``note`` on ``FieldResult`` is the
    human sentence shown alongside it. See ASSUMPTIONS_AND_TRADEOFFS.md D-14.
    """

    MATCH = "match"                                        # PASS, clean
    NOT_REQUIRED = "not_required"                          # PASS, optional field, nothing to verify
    MISMATCH = "mismatch"                                  # FAIL, value disagreement
    BLANK_EXPECTED = "blank_expected"                      # NEEDS_REVIEW, required field left empty
    UNREADABLE = "unreadable"                              # NEEDS_REVIEW, couldn't read off the label
    UNEXPECTED_VALUE = "unexpected_value"                  # NEEDS_REVIEW, label has value, none expected
    BORDERLINE = "borderline"                              # NEEDS_REVIEW, fuzzy gray band
    SPECIAL_CHARACTER = "special_character"                # NEEDS_REVIEW, non-ASCII/accented, can't safely match
    WARNING_PREFIX_MISSING = "warning_prefix_missing"      # FAIL
    WARNING_PREFIX_NOT_ALLCAPS = "warning_prefix_not_allcaps"  # FAIL
    WARNING_WORDING = "warning_wording"                    # FAIL, body deviates from canonical


class FieldResult(BaseModel):
    """Verdict for a single label field ("show the work")."""

    field: str
    expected: str | None = None
    extracted: str | None = None
    rule: str
    verdict: ResultState
    reason: ResultReason
    note: str | None = None


def compute_overall(fields: "list[FieldResult]") -> ResultState:
    """Roll a list of per-field verdicts up to one overall verdict.

    Biased to safety: FAIL if any field FAILs; else NEEDS_REVIEW if any field is
    NEEDS_REVIEW; else PASS. An empty field list rolls up to NEEDS_REVIEW (there
    was nothing we could confidently pass).
    """
    if not fields:
        return ResultState.NEEDS_REVIEW
    if any(f.verdict == ResultState.FAIL for f in fields):
        return ResultState.FAIL
    if any(f.verdict == ResultState.NEEDS_REVIEW for f in fields):
        return ResultState.NEEDS_REVIEW
    return ResultState.PASS


class LabelResult(BaseModel):
    """Aggregate result for one label (all fields)."""

    fields: list[FieldResult]
    overall: ResultState

    @classmethod
    def from_fields(cls, fields: "list[FieldResult]") -> "LabelResult":
        """Build a ``LabelResult`` from field results, computing ``overall``."""
        return cls(fields=list(fields), overall=compute_overall(fields))


class BatchResult(BaseModel):
    """Aggregate result for a batch submission (used in a later batch pass)."""

    items: list[LabelResult]
    passed: int
    failed: int
    needs_review: int

    @classmethod
    def from_items(cls, items: "list[LabelResult]") -> "BatchResult":
        """Build a ``BatchResult`` from per-label results, tallying the counts."""
        passed = sum(1 for it in items if it.overall == ResultState.PASS)
        failed = sum(1 for it in items if it.overall == ResultState.FAIL)
        needs_review = sum(1 for it in items if it.overall == ResultState.NEEDS_REVIEW)
        return cls(
            items=list(items),
            passed=passed,
            failed=failed,
            needs_review=needs_review,
        )
