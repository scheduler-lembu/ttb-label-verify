"""Canonical Government Warning reference text.

Single responsibility: store the ONE trusted reference string the extracted
warning is matched against, char-for-char, by ``match_warning`` (MR-04). This
is the field where fuzzy matching would be wrong — a single altered word must
FAIL — so the reference must be exact and sourced, never typed from memory.

The statute (27 CFR 16.21) requires the statement to appear as one continuous
statement, so it is stored as a single continuous line.
"""

from __future__ import annotations

# The single verified reference constant (MA-2), sourced from the statute — not
# typed from memory. match_warning compares against THIS char-for-char (MR-04),
# so any edit to the wording, casing, or punctuation below would silently change
# what "compliant" means for every label. Do NOT edit this string.
# Source: eCFR 27 CFR 16.21, Title 27 current as of 2026-07-24. Verbatim; do not edit wording.
CANONICAL_GOVERNMENT_WARNING: str = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)

# The prefix that must appear in ALL CAPS on the label (MR-05). Title case
# ("Government Warning") must FAIL. The check is implemented in match_warning.
REQUIRED_WARNING_PREFIX: str = "GOVERNMENT WARNING:"
