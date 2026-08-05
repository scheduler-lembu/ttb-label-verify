"""Text-normalization helpers for matching.

Single responsibility: small, pure string helpers used by the matchers —
case folding, punctuation stripping, whitespace collapsing, ampersand/"and"
equivalence, etc. These implement the tolerance behind MR-01 (brand match is
case- and punctuation-insensitive) and the whitespace-only normalization used
before the EXACT Government Warning comparison (MR-04/05).

Scaffold pass: signatures only. No behavior this pass.
"""

from __future__ import annotations


def normalize_loose(value: str) -> str:
    """Aggressive normalization for fuzzy fields (brand).

    Intended: lowercase; strip/standardize punctuation (apostrophes, hyphens,
    ampersand-vs-"and"); collapse internal whitespace. Used by ``match_brand``.
    Stub.
    """
    raise NotImplementedError


def normalize_whitespace(value: str) -> str:
    """Whitespace-only normalization for the exact warning comparison.

    Intended: collapse runs of whitespace and trim, WITHOUT touching case,
    punctuation, or wording — the warning must otherwise match char-for-char.
    Used by ``match_warning``. Stub.
    """
    raise NotImplementedError
