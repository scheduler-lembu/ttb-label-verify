"""Exception buckets — grouping non-PASS results ONE PER FIELD.

Single responsibility: turn the per-field verdicts the engine already produced
into review "buckets", one per label field, so a finished batch surfaces as
"clean items auto-cleared / the rest grouped by which field needs a human". This
is pure, deterministic Python ("code judges" stays in code), unit-tested offline.

It NEVER reclassifies or changes a verdict — buckets only GROUP the non-PASS
results the matcher emitted. A clean label (all PASS) produces no tags; a
multi-flag label produces one tag per flagged field (so it appears in several
buckets). A whole-label extractor failure (every field NEEDS_REVIEW / UNREADABLE)
collapses to a SINGLE "couldn't read the label" bucket rather than all seven.

``BucketTag`` is defined HERE (not in app.models) so the graded models are not
touched. See BATCH_TRIAGE_DESIGN.md.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.fields import FIELD_REGISTRY
from app.models import LabelResult, ResultReason, ResultState

# Human bucket labels, per field key. Falls back to the registry label.
_REGISTRY_LABELS = {f.key: f.label for f in FIELD_REGISTRY}
_BUCKET_LABELS = {
    "brand": "Brand name",
    "alcohol_content": "Alcohol content",
    "warning": "Government warning",
    "class_type": "Class / type",
    "net_contents": "Net contents",
    "producer": "Producer name & address",
    "country_of_origin": "Country of origin",
}

# The whole-label "couldn't read" bucket (extractor-unavailable labels).
UNREADABLE_BUCKET_ID = "unreadable_label"
UNREADABLE_BUCKET_LABEL = "Couldn't read the label"


def bucket_label_for(field: str) -> str:
    """Human-readable bucket name for a field key."""
    return _BUCKET_LABELS.get(field) or _REGISTRY_LABELS.get(field, field)


class BucketTag(BaseModel):
    """One flagged field of one label, tagged into that field's bucket."""

    bucket_id: str
    bucket_label: str
    field: str
    reason: str
    extracted: str | None = None
    expected: str | None = None
    note: str | None = None


def is_clean(result: LabelResult) -> bool:
    """True iff every field verdict is PASS (the label auto-clears)."""
    return all(fr.verdict == ResultState.PASS for fr in result.fields)


def _is_whole_label_unreadable(result: LabelResult) -> bool:
    """True iff this is an extractor-unavailable label.

    verify marks that case by setting EVERY field to NEEDS_REVIEW / UNREADABLE.
    """
    return bool(result.fields) and all(
        fr.verdict == ResultState.NEEDS_REVIEW and fr.reason == ResultReason.UNREADABLE
        for fr in result.fields
    )


def bucket_tags_for(result: LabelResult) -> "list[BucketTag]":
    """Return the review buckets a label belongs in.

    Clean labels return ``[]``. A whole-label extractor failure returns a single
    ``unreadable_label`` tag. Otherwise one tag per flagged (non-PASS) field.
    """
    if is_clean(result):
        return []

    if _is_whole_label_unreadable(result):
        first = result.fields[0]
        return [
            BucketTag(
                bucket_id=UNREADABLE_BUCKET_ID,
                bucket_label=UNREADABLE_BUCKET_LABEL,
                field=UNREADABLE_BUCKET_ID,
                reason=first.reason.value,
                extracted=None,
                expected=None,
                note=first.note,
            )
        ]

    tags: list[BucketTag] = []
    for fr in result.fields:
        if fr.verdict == ResultState.PASS:
            continue
        tags.append(
            BucketTag(
                bucket_id=fr.field,
                bucket_label=bucket_label_for(fr.field),
                field=fr.field,
                reason=fr.reason.value,
                extracted=fr.extracted,
                expected=fr.expected,
                note=fr.note,
            )
        )
    return tags
