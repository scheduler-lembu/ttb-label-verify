"""Exception-folder triage — grouping non-PASS results by problem type.

Single responsibility: turn the per-field verdicts the engine already produced
into "folders" by reason code, so a finished batch surfaces as
"clean items auto-cleared / exceptions grouped by the one problem". This is pure,
deterministic Python ("code judges" stays in code) and is unit-tested offline.

It NEVER reclassifies or changes a verdict — folders only GROUP the non-PASS
results the matcher emitted. A clean label (all fields PASS) produces no tags; a
multi-flaw label produces one tag per distinct folder (so it appears in several).

``FolderTag`` is defined HERE (not in app.models) so the graded models are not
touched. See BATCH_TRIAGE_DESIGN.md.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.fields import FIELD_REGISTRY, RuleType
from app.models import LabelResult, ResultReason, ResultState

# Supporting field keys (registry-driven, not hardcoded).
_SUPPORTING = {f.key for f in FIELD_REGISTRY if f.rule == RuleType.SUPPORTING}

# Fallback folder — guarantees no non-PASS result is ever silently dropped.
_FALLBACK = ("other_review", "Other — needs review")

R = ResultReason


def folder_for(field: str, reason: ResultReason) -> "tuple[str, str]":
    """Map a non-PASS (field, reason) to a stable (folder_id, human label).

    Anything not explicitly mapped lands in the "Other — needs review" fallback.
    """
    if field == "warning":
        return {
            R.WARNING_WORDING: ("warning_wording", "Warning — wording changed"),
            R.WARNING_PREFIX_NOT_ALLCAPS: ("warning_prefix_case", "Warning — prefix not all caps"),
            R.WARNING_PREFIX_MISSING: ("warning_prefix_missing", "Warning — prefix missing"),
            R.UNREADABLE: ("warning_unreadable", "Warning — couldn't read"),
        }.get(reason, _FALLBACK)

    if field == "alcohol_content":
        if reason == R.MISMATCH:
            return ("abv_mismatch", "Alcohol content — mismatch")
        if reason == R.BLANK_EXPECTED:
            return ("abv_blank", "Alcohol content — confirm absence")
        if reason in (R.UNREADABLE, R.UNEXPECTED_VALUE):
            return ("abv_unreadable", "Alcohol content — couldn't read")
        return _FALLBACK

    if field == "brand":
        return {
            R.MISMATCH: ("brand_mismatch", "Brand — mismatch"),
            R.BORDERLINE: ("brand_borderline", "Brand — borderline match"),
            R.SPECIAL_CHARACTER: ("brand_special", "Brand — special characters"),
            R.UNREADABLE: ("brand_unreadable", "Brand — couldn't read"),
        }.get(reason, _FALLBACK)

    if field in _SUPPORTING:
        if reason == R.BLANK_EXPECTED:
            return ("required_blank", "Required field left blank")
        if reason in (R.MISMATCH, R.BORDERLINE, R.UNREADABLE, R.SPECIAL_CHARACTER):
            return ("supporting_review", "Supporting field — needs review")
        return _FALLBACK

    return _FALLBACK


class FolderTag(BaseModel):
    """One flaw of one label, tagged into the folder that groups its problem."""

    folder_id: str
    folder_label: str
    field: str
    reason: str
    extracted: str | None = None
    expected: str | None = None
    note: str | None = None


def is_clean(result: LabelResult) -> bool:
    """True iff every field verdict is PASS (the label auto-clears)."""
    return all(fr.verdict == ResultState.PASS for fr in result.fields)


def folder_tags_for(result: LabelResult) -> "list[FolderTag]":
    """Return one FolderTag per distinct problem folder for a label.

    Clean labels return ``[]``. Multi-flaw labels return several tags (into
    several folders). Identical folder_ids are de-duped so a label appears once
    per folder.
    """
    tags: list[FolderTag] = []
    seen: set[str] = set()
    for fr in result.fields:
        if fr.verdict == ResultState.PASS:
            continue
        folder_id, folder_label = folder_for(fr.field, fr.reason)
        if folder_id in seen:
            continue
        seen.add(folder_id)
        tags.append(
            FolderTag(
                folder_id=folder_id,
                folder_label=folder_label,
                field=fr.field,
                reason=fr.reason.value,
                extracted=fr.extracted,
                expected=fr.expected,
                note=fr.note,
            )
        )
    return tags
