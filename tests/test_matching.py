"""Test stubs for the deterministic matchers (the graded core).

Single responsibility: hold one placeholder test per matcher so the intended
behavior is documented now and filled in when ``app.matching.rules`` is
implemented. The named cases below come straight from the requirements and
interviews; they are deliberately listed so the matching logic is written to
satisfy them.

Scaffold pass: every test is skipped — no assertions, no logic yet.
"""

import pytest


@pytest.mark.skip(reason="scaffold: match_brand not implemented yet")
def test_match_brand_case_and_punctuation_insensitive():
    """MR-01: STONE'S THROW should match Stone's Throw; a different brand FAILs."""
    raise NotImplementedError


@pytest.mark.skip(reason="scaffold: match_abv not implemented yet")
def test_match_abv_proof_equivalence():
    """MR-02: 45% Alc./Vol. satisfies expected '45%' OR '90 proof'."""
    raise NotImplementedError


@pytest.mark.skip(reason="scaffold: match_abv not implemented yet")
def test_match_abv_legitimate_absence_not_a_failure():
    """MR-03: a beverage type that legitimately omits ABV is not a FAIL."""
    raise NotImplementedError


@pytest.mark.skip(reason="scaffold: match_warning not implemented yet")
def test_match_warning_exact_text():
    """MR-04: any wording change/omission vs the canonical warning FAILs."""
    raise NotImplementedError


@pytest.mark.skip(reason="scaffold: match_warning not implemented yet")
def test_match_warning_prefix_must_be_all_caps():
    """MR-05: 'Government Warning' (title case) FAILs; 'GOVERNMENT WARNING:' passes."""
    raise NotImplementedError


@pytest.mark.skip(reason="scaffold: match_supporting not implemented yet")
def test_match_supporting_present_normalized():
    """FR-08: class/type, net contents, producer, country of origin present/normalized."""
    raise NotImplementedError


@pytest.mark.skip(reason="scaffold: matchers not implemented yet")
def test_unreadable_field_is_needs_review_not_a_guess():
    """FR-09: a missing/unreadable extracted value -> NEEDS_REVIEW, never a guessed PASS/FAIL."""
    raise NotImplementedError
