"""Offline unit tests for the per-FIELD bucket triage mapping."""

from __future__ import annotations

import pytest

from app.models import FieldResult, LabelResult, ResultReason, ResultState
from app.triage import bucket_tags_for, is_clean


def _field(field, reason, verdict=ResultState.FAIL, extracted="X", expected="Y"):
    return FieldResult(
        field=field, expected=expected, extracted=extracted,
        rule="test-rule", verdict=verdict, reason=reason, note="test note",
    )


def _pass_field(field):
    return _field(field, ResultReason.MATCH, verdict=ResultState.PASS)


# Every field -> its own bucket (bucket_id == field key), with a human label.
FIELD_BUCKETS = [
    ("brand", "Brand name"),
    ("alcohol_content", "Alcohol content"),
    ("warning", "Government warning"),
    ("class_type", "Class / type"),
    ("net_contents", "Net contents"),
    ("producer", "Producer name & address"),
    ("country_of_origin", "Country of origin"),
]


@pytest.mark.parametrize("field,label", FIELD_BUCKETS)
def test_non_pass_field_lands_in_its_field_bucket(field, label):
    # guards FR-11/FR-13: each non-PASS field routes to its own field bucket, carrying the field key, human label, and reason code.
    result = LabelResult.from_fields([_field(field, ResultReason.MISMATCH)])
    tags = bucket_tags_for(result)
    assert len(tags) == 1
    assert tags[0].bucket_id == field
    assert tags[0].bucket_label == label
    assert tags[0].field == field
    assert tags[0].reason == ResultReason.MISMATCH.value


def test_clean_result_has_no_tags_and_is_clean():
    # An all-PASS label produces zero bucket tags and reports is_clean == True.
    result = LabelResult.from_fields([_pass_field("brand"), _pass_field("warning")])
    assert bucket_tags_for(result) == []
    assert is_clean(result) is True


def test_pass_field_is_never_bucketed():
    # Only the failing field is bucketed; PASS fields are never added to a triage bucket.
    result = LabelResult.from_fields([
        _pass_field("brand"),
        _field("alcohol_content", ResultReason.MISMATCH),
    ])
    tags = bucket_tags_for(result)
    assert {t.bucket_id for t in tags} == {"alcohol_content"}


def test_multi_flag_result_tags_one_bucket_per_field():
    # guards FR-11: a label wrong on two fields yields one bucket tag per failing field and is_clean == False.
    result = LabelResult.from_fields([
        _field("brand", ResultReason.MISMATCH),
        _field("alcohol_content", ResultReason.MISMATCH),
        _pass_field("net_contents"),
    ])
    tags = bucket_tags_for(result)
    assert {t.bucket_id for t in tags} == {"brand", "alcohol_content"}
    assert is_clean(result) is False


def test_whole_label_unreadable_collapses_to_single_bucket():
    # guards FR-09/D-19: when the whole label is unreadable it collapses to ONE "unreadable_label" bucket, not seven noisy per-field tags.
    # Every field NEEDS_REVIEW / UNREADABLE == extractor-unavailable label.
    fields = [
        _field(k, ResultReason.UNREADABLE, verdict=ResultState.NEEDS_REVIEW,
               extracted=None, expected=None)
        for k in ["brand", "alcohol_content", "warning", "class_type",
                  "net_contents", "producer", "country_of_origin"]
    ]
    result = LabelResult.from_fields(fields)
    tags = bucket_tags_for(result)
    assert len(tags) == 1  # NOT seven
    assert tags[0].bucket_id == "unreadable_label"
    assert tags[0].bucket_label == "Couldn't read the label"


def test_partial_unreadable_is_not_the_whole_label_bucket():
    # Boundary of the collapse: a partial read (not every field unreadable) stays on per-field buckets.
    # A mix (some PASS, one UNREADABLE) uses per-field buckets, not the collapse.
    result = LabelResult.from_fields([
        _pass_field("brand"),
        _field("warning", ResultReason.UNREADABLE, verdict=ResultState.NEEDS_REVIEW),
    ])
    tags = bucket_tags_for(result)
    assert {t.bucket_id for t in tags} == {"warning"}
