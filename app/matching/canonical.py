"""Canonical Government Warning reference text.

Single responsibility: store the ONE trusted reference string the extracted
warning is matched against, char-for-char, by ``match_warning`` (MR-04). This
is the field where fuzzy matching would be wrong — a single altered word must
FAIL — so the reference must be exact and sourced, never typed from memory.

Scaffold pass: PLACEHOLDER ONLY. The statutory text (27 CFR 16.21) has been
confirmed stable, so a fixed constant is the correct design — no versioning
machinery needed — but the actual wording is sourced/verified at build time,
NOT pasted from memory now.
"""

from __future__ import annotations

# TODO: source exact 27 CFR 16.21 text at build time. Do NOT paste from memory.
CANONICAL_GOVERNMENT_WARNING: str = "<<PLACEHOLDER: canonical 27 CFR 16.21 GOVERNMENT WARNING text — source at build time>>"

# The prefix that must appear in ALL CAPS on the label (MR-05). Title case
# ("Government Warning") must FAIL. The check is implemented in match_warning.
REQUIRED_WARNING_PREFIX: str = "GOVERNMENT WARNING:"
