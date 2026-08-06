"""Unit tests for the literal-OCR warning cross-check PURE functions.

Fully offline — no Tesseract binary, no API key, no network. Only the pure
functions (``extract_warning_region`` and ``warning_reads_agree``) are exercised;
the Tesseract-dependent paths are integration-tested by the catalog harness.
"""

from app.extraction.ocr_local import extract_warning_region, warning_reads_agree

# The canonical warning wording (all-caps prefix), used as the reference text.
W = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)


# --------------------------------------------------------------------------- #
# extract_warning_region
# --------------------------------------------------------------------------- #
def test_extract_region_found():
    # Slices the warning block out of surrounding OCR text, starting at the prefix.
    text = "OLD TOM DISTILLERY\n750 mL\n" + W
    region = extract_warning_region(text)
    assert region is not None
    assert region.startswith("GOVERNMENT WARNING:")


def test_extract_region_titlecase():
    # Backs D-16: region extraction preserves case so the caps check can later see a title-case prefix.
    title = W.replace("GOVERNMENT WARNING", "Government Warning", 1)
    text = "Some Brand\n" + title
    region = extract_warning_region(text)
    assert region is not None
    assert region.startswith("Government Warning:")  # case preserved


def test_extract_region_absent():
    # No warning in the OCR text -> None (nothing to cross-check).
    assert extract_warning_region("Just a brand name and 750 mL, no warning here") is None


def test_extract_region_none_input():
    # None input (e.g. Tesseract unavailable) -> None, no crash.
    assert extract_warning_region(None) is None


# --------------------------------------------------------------------------- #
# warning_reads_agree
# --------------------------------------------------------------------------- #
def test_agree_identical():
    # D-16: identical vision and OCR reads agree (no PASS->NEEDS_REVIEW downgrade).
    assert warning_reads_agree(W, W, 90.0) is True


def test_agree_minor_ocr_noise():
    # A single-character typo in one word — fuzzy body compare tolerates it.
    noisy = W.replace("machinery", "machinory", 1)
    assert warning_reads_agree(W, noisy, 90.0) is True


def test_disagree_prefix_case():
    # D-16: a prefix-case difference between the two reads counts as disagreement -> downgrade to review.
    title = W.replace("GOVERNMENT WARNING", "Government Warning", 1)
    assert warning_reads_agree(W, title, 90.0) is False


def test_disagree_one_absent():
    # Exactly one side read the warning -> disagreement (the two sources conflict).
    assert warning_reads_agree(W, None, 90.0) is False
    assert warning_reads_agree(None, W, 90.0) is False


def test_agree_both_absent():
    # Neither side read a warning -> vacuously agree (no cross-check signal to act on).
    assert warning_reads_agree(None, None, 90.0) is True
    assert warning_reads_agree("", "", 90.0) is True


def test_disagree_wording():
    # Wholly different wording between the two reads -> disagreement.
    other = "This label contains absolutely no health warning of any kind whatsoever."
    assert warning_reads_agree(W, other, 90.0) is False
