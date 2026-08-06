"""Offline unit tests for the exception-folder triage mapping + tagging."""

from __future__ import annotations

import pytest

from app.models import FieldResult, LabelResult, ResultReason, ResultState
from app.triage import folder_tags_for, is_clean


def _field(field, reason, verdict=ResultState.FAIL, extracted="X", expected="Y"):
    return FieldResult(
        field=field,
        expected=expected,
        extracted=extracted,
        rule="test-rule",
        verdict=verdict,
        reason=reason,
        note="test note",
    )


def _pass_field(field):
    return _field(field, ResultReason.MATCH, verdict=ResultState.PASS)


# Every explicitly-mapped (field, reason) -> its folder_id / label.
MAPPED = [
    ("warning", ResultReason.WARNING_WORDING, "warning_wording", "Warning — wording changed"),
    ("warning", ResultReason.WARNING_PREFIX_NOT_ALLCAPS, "warning_prefix_case", "Warning — prefix not all caps"),
    ("warning", ResultReason.WARNING_PREFIX_MISSING, "warning_prefix_missing", "Warning — prefix missing"),
    ("warning", ResultReason.UNREADABLE, "warning_unreadable", "Warning — couldn't read"),
    ("alcohol_content", ResultReason.MISMATCH, "abv_mismatch", "Alcohol content — mismatch"),
    ("alcohol_content", ResultReason.BLANK_EXPECTED, "abv_blank", "Alcohol content — confirm absence"),
    ("alcohol_content", ResultReason.UNREADABLE, "abv_unreadable", "Alcohol content — couldn't read"),
    ("alcohol_content", ResultReason.UNEXPECTED_VALUE, "abv_unreadable", "Alcohol content — couldn't read"),
    ("brand", ResultReason.MISMATCH, "brand_mismatch", "Brand — mismatch"),
    ("brand", ResultReason.BORDERLINE, "brand_borderline", "Brand — borderline match"),
    ("brand", ResultReason.SPECIAL_CHARACTER, "brand_special", "Brand — special characters"),
    ("brand", ResultReason.UNREADABLE, "brand_unreadable", "Brand — couldn't read"),
    ("class_type", ResultReason.BLANK_EXPECTED, "required_blank", "Required field left blank"),
    ("country_of_origin", ResultReason.BLANK_EXPECTED, "required_blank", "Required field left blank"),
    ("net_contents", ResultReason.MISMATCH, "supporting_review", "Supporting field — needs review"),
    ("producer", ResultReason.UNREADABLE, "supporting_review", "Supporting field — needs review"),
]


@pytest.mark.parametrize("field,reason,folder_id,label", MAPPED)
def test_each_mapped_field_reason_lands_in_expected_folder(field, reason, folder_id, label):
    result = LabelResult.from_fields([_field(field, reason)])
    tags = folder_tags_for(result)
    assert len(tags) == 1
    assert tags[0].folder_id == folder_id
    assert tags[0].folder_label == label
    # The flaw's context travels with the tag (for the folder row display).
    assert tags[0].field == field
    assert tags[0].reason == reason.value


def test_clean_result_has_no_tags_and_is_clean():
    result = LabelResult.from_fields([_pass_field("brand"), _pass_field("warning")])
    assert folder_tags_for(result) == []
    assert is_clean(result) is True


def test_multi_flaw_result_tags_into_multiple_folders():
    result = LabelResult.from_fields([
        _field("brand", ResultReason.MISMATCH),
        _field("warning", ResultReason.WARNING_WORDING),
        _pass_field("net_contents"),
    ])
    tags = folder_tags_for(result)
    assert {t.folder_id for t in tags} == {"brand_mismatch", "warning_wording"}
    assert is_clean(result) is False


def test_identical_folder_ids_are_deduped():
    # Two supporting fields both map to "supporting_review" -> one tag.
    result = LabelResult.from_fields([
        _field("net_contents", ResultReason.MISMATCH),
        _field("producer", ResultReason.MISMATCH),
    ])
    tags = folder_tags_for(result)
    assert len(tags) == 1
    assert tags[0].folder_id == "supporting_review"


def test_unmapped_non_pass_falls_back_to_other():
    # brand + BLANK_EXPECTED is not explicitly mapped -> fallback (nothing dropped).
    result = LabelResult.from_fields([
        _field("brand", ResultReason.BLANK_EXPECTED, verdict=ResultState.NEEDS_REVIEW),
    ])
    tags = folder_tags_for(result)
    assert len(tags) == 1
    assert tags[0].folder_id == "other_review"
    assert tags[0].folder_label == "Other — needs review"
