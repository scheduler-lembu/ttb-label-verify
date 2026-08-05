"""Unit tests for the deterministic matchers (the graded core).

Everything here runs offline — no AI, no network. The named cases come straight
from REQUIREMENTS.md §5 (MR-01…MR-05, FR-08/09) and the interviews, and prove the
matching logic behaves as specified.
"""

from app.matching.canonical import CANONICAL_GOVERNMENT_WARNING
from app.matching.normalize import (
    normalize_general,
    normalize_measure,
    normalize_whitespace_only,
)
from app.matching.rules import (
    match_abv,
    match_brand,
    match_supporting,
    match_warning,
    parse_strength,
    run_matchers,
)
from app.models import ResultReason, ResultState


# --------------------------------------------------------------------------- #
# Brand (MR-01)
# --------------------------------------------------------------------------- #
def test_brand_apostrophe_and_case_insensitive():
    """STONE'S THROW vs Stone's Throw -> PASS."""
    assert match_brand("Stone's Throw", "STONE'S THROW").verdict == ResultState.PASS


def test_brand_ampersand_equals_and():
    """'&' vs 'and' -> PASS."""
    assert match_brand("Smith & Sons", "Smith and Sons").verdict == ResultState.PASS


def test_brand_hyphen_and_spacing_ignored():
    assert match_brand("Old-Tom Distillery", "Old Tom  Distillery").verdict == ResultState.PASS


def test_brand_different_brand_fails():
    """A genuinely different brand -> FAIL."""
    assert match_brand("Old Tom Distillery", "Captain Morgan").verdict == ResultState.FAIL


def test_brand_empty_extracted_needs_review():
    """Nothing read from the label -> NEEDS_REVIEW, never a guess."""
    r = match_brand("Old Tom Distillery", "")
    assert r.verdict == ResultState.NEEDS_REVIEW
    assert r.reason == ResultReason.UNREADABLE
    r_none = match_brand("Old Tom Distillery", None)
    assert r_none.verdict == ResultState.NEEDS_REVIEW


def test_brand_blank_expected_needs_review():
    """[D-12] Blank required expected -> NEEDS_REVIEW / blank_expected."""
    r = match_brand("", "Old Tom")
    assert r.verdict == ResultState.NEEDS_REVIEW
    assert r.reason == ResultReason.BLANK_EXPECTED


def test_brand_special_character_needs_review():
    """Accented/non-ASCII value that doesn't normalize -> special_character review."""
    r = match_brand("Chateau", "Château")
    assert r.verdict == ResultState.NEEDS_REVIEW
    assert r.reason == ResultReason.SPECIAL_CHARACTER


def test_brand_near_miss_is_needs_review():
    """A close-but-not-exact brand lands in the review band, not an auto-pass/fail."""
    r = match_brand("Old Tom Distillery", "Old Tom Distillary Co")
    assert r.verdict in (ResultState.NEEDS_REVIEW, ResultState.PASS)


# --------------------------------------------------------------------------- #
# Alcohol content (MR-02/03)
# --------------------------------------------------------------------------- #
def test_parse_strength_percent_and_proof():
    assert parse_strength("45% Alc./Vol.") == 45.0
    assert parse_strength("90 proof") == 45.0
    assert parse_strength("bourbon whiskey") is None


def test_abv_percent_expected_matches_label_with_proof():
    """Expected 45% vs '45% Alc./Vol. (90 Proof)' -> PASS."""
    assert match_abv("45%", "45% Alc./Vol. (90 Proof)").verdict == ResultState.PASS


def test_abv_proof_expected_matches_label():
    """Expected '90 proof' vs '45% Alc./Vol. (90 Proof)' -> PASS."""
    assert match_abv("90 proof", "45% Alc./Vol. (90 Proof)").verdict == ResultState.PASS


def test_abv_mismatch_fails():
    """40% vs 45% -> FAIL."""
    assert match_abv("40%", "45%").verdict == ResultState.FAIL


def test_abv_both_absent_needs_review():
    """[D-12] Nothing expected, nothing on label -> NEEDS_REVIEW / blank_expected.

    Still satisfies MR-03 (absence is not a FAIL); a human confirms legitimacy.
    """
    r_none = match_abv(None, None)
    assert r_none.verdict == ResultState.NEEDS_REVIEW
    assert r_none.reason == ResultReason.BLANK_EXPECTED
    r_empty = match_abv("", "")
    assert r_empty.verdict == ResultState.NEEDS_REVIEW
    assert r_empty.reason == ResultReason.BLANK_EXPECTED


def test_abv_expected_present_extracted_empty_needs_review():
    r = match_abv("45%", "")
    assert r.verdict == ResultState.NEEDS_REVIEW


def test_abv_value_on_label_but_none_expected_needs_review():
    r = match_abv(None, "45% Alc./Vol.")
    assert r.verdict == ResultState.NEEDS_REVIEW


# --------------------------------------------------------------------------- #
# Government Warning (MR-04/05)
# --------------------------------------------------------------------------- #
def test_warning_exact_canonical_passes():
    r = match_warning(None, CANONICAL_GOVERNMENT_WARNING)
    assert r.verdict == ResultState.PASS
    assert r.reason == ResultReason.MATCH


def test_warning_title_case_prefix_fails():
    """MR-05: 'Government Warning' (title case) -> FAIL."""
    title_case = CANONICAL_GOVERNMENT_WARNING.replace(
        "GOVERNMENT WARNING", "Government Warning"
    )
    r = match_warning(None, title_case)
    assert r.verdict == ResultState.FAIL
    assert r.reason == ResultReason.WARNING_PREFIX_NOT_ALLCAPS
    assert r.note == "prefix not all caps"


def test_warning_one_altered_word_fails():
    """MR-04: a single wording change -> FAIL."""
    altered = CANONICAL_GOVERNMENT_WARNING.replace(
        "birth defects", "birth defect"
    )
    r = match_warning(None, altered)
    assert r.verdict == ResultState.FAIL
    assert r.reason == ResultReason.WARNING_WORDING


def test_warning_extra_whitespace_still_passes():
    """Whitespace-only differences (extra spaces / newlines) -> PASS."""
    noisy = CANONICAL_GOVERNMENT_WARNING.replace(". ", ".  \n  ")
    assert match_warning(None, "   " + noisy + "  ").verdict == ResultState.PASS


def test_warning_prefix_missing_fails():
    r = match_warning(None, "According to the Surgeon General, women should not...")
    assert r.verdict == ResultState.FAIL
    assert r.reason == ResultReason.WARNING_PREFIX_MISSING
    assert r.note == "warning prefix missing"


def test_warning_empty_needs_review():
    r = match_warning(None, "")
    assert r.verdict == ResultState.NEEDS_REVIEW
    assert r.reason == ResultReason.UNREADABLE
    assert match_warning(None, None).verdict == ResultState.NEEDS_REVIEW


def test_warning_linebroken_prefix_passes():
    """A correctly all-caps prefix wrapped across a line break -> PASS (not a caps failure)."""
    line_broken = CANONICAL_GOVERNMENT_WARNING.replace(
        "GOVERNMENT WARNING", "GOVERNMENT\nWARNING", 1
    )
    r = match_warning(None, line_broken)
    assert r.verdict == ResultState.PASS
    assert r.reason == ResultReason.MATCH


def test_warning_double_space_prefix_passes():
    """A correctly all-caps prefix with an extra space -> PASS."""
    double_space = CANONICAL_GOVERNMENT_WARNING.replace(
        "GOVERNMENT WARNING", "GOVERNMENT  WARNING", 1
    )
    r = match_warning(None, double_space)
    assert r.verdict == ResultState.PASS
    assert r.reason == ResultReason.MATCH


def test_canonical_text_matches_handoff_verbatim():
    """Guard: the stored canonical string is byte-for-byte the sourced text."""
    expected = (
        "GOVERNMENT WARNING: (1) According to the Surgeon General, women should "
        "not drink alcoholic beverages during pregnancy because of the risk of "
        "birth defects. (2) Consumption of alcoholic beverages impairs your "
        "ability to drive a car or operate machinery, and may cause health "
        "problems."
    )
    assert CANONICAL_GOVERNMENT_WARNING == expected


# --------------------------------------------------------------------------- #
# Supporting fields (FR-08)
# --------------------------------------------------------------------------- #
def test_supporting_net_contents_unit_normalization():
    """'750 mL' vs '750 ml' -> PASS."""
    r = match_supporting("net_contents", "750 mL", "750 ml")
    assert r.verdict == ResultState.PASS


def test_supporting_domestic_country_blank_blank_passes():
    """Domestic country-of-origin blank/blank -> PASS (not required)."""
    r = match_supporting("country_of_origin", "", "", required=False)
    assert r.verdict == ResultState.PASS
    assert r.reason == ResultReason.NOT_REQUIRED


def test_supporting_required_blank_needs_review():
    """[D-12] A blank required supporting field -> NEEDS_REVIEW / blank_expected."""
    r = match_supporting("class_type", "", "Bourbon", required=True)
    assert r.verdict == ResultState.NEEDS_REVIEW
    assert r.reason == ResultReason.BLANK_EXPECTED


def test_supporting_expected_present_extracted_empty_needs_review():
    r = match_supporting("class_type", "Kentucky Straight Bourbon Whiskey", "")
    assert r.verdict == ResultState.NEEDS_REVIEW


def test_supporting_clear_mismatch_fails():
    r = match_supporting("class_type", "Kentucky Straight Bourbon Whiskey", "Vodka")
    assert r.verdict == ResultState.FAIL


def test_supporting_normalized_producer_match():
    r = match_supporting(
        "producer",
        "Old Tom Distillery, Louisville, KY",
        "OLD TOM DISTILLERY, LOUISVILLE KY",
    )
    assert r.verdict == ResultState.PASS


# --------------------------------------------------------------------------- #
# Normalizers (direct)
# --------------------------------------------------------------------------- #
def test_normalize_general_none_and_punctuation():
    assert normalize_general(None) == ""
    assert normalize_general("Stone's Throw!!") == "stone s throw"
    assert normalize_general("A & B") == "a and b"


def test_normalize_whitespace_only_preserves_case_and_punct():
    assert normalize_whitespace_only("  A,  B \n C  ") == "A, B C"
    assert normalize_whitespace_only(None) == ""


def test_normalize_measure_units():
    assert normalize_measure("750 mL") == "750ml"
    assert normalize_measure("1 Liter") == "1l"
    assert normalize_measure(None) == ""


# --------------------------------------------------------------------------- #
# Runner + overall rollup
# --------------------------------------------------------------------------- #
def _compliant_expected():
    return {
        "brand": "Old Tom Distillery",
        "alcohol_content": "45%",
        "warning": "",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "net_contents": "750 mL",
        "producer": "Old Tom Distillery, Louisville, KY",
        "country_of_origin": "",
    }


def _compliant_extracted():
    return {
        "brand": "OLD TOM DISTILLERY",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "warning": CANONICAL_GOVERNMENT_WARNING,
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "net_contents": "750 ml",
        "producer": "Old Tom Distillery, Louisville KY",
        "country_of_origin": "",
    }


def test_run_matchers_all_pass_overall_pass():
    result = run_matchers(_compliant_expected(), _compliant_extracted())
    assert result.overall == ResultState.PASS
    assert len(result.fields) == 7


def test_run_matchers_any_fail_overall_fail():
    expected = _compliant_expected()
    extracted = _compliant_extracted()
    extracted["alcohol_content"] = "40%"  # mismatch -> FAIL
    result = run_matchers(expected, extracted)
    assert result.overall == ResultState.FAIL


def test_run_matchers_needs_review_when_no_fail_but_unread():
    expected = _compliant_expected()
    extracted = _compliant_extracted()
    extracted["brand"] = ""  # unread -> NEEDS_REVIEW, no FAIL anywhere
    result = run_matchers(expected, extracted)
    assert result.overall == ResultState.NEEDS_REVIEW
