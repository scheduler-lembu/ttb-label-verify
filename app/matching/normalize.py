"""Text-normalization helpers for matching.

Single responsibility: small, pure string helpers used by the matchers. Three
distinct normalizers, because the fields need different tolerances:

  * normalize_general      — brand & most supporting fields (aggressive: case,
                             punctuation, ``&``/``and`` all folded away).
  * normalize_whitespace_only — the Government Warning (whitespace collapsed
                             ONLY; case and punctuation preserved exactly, so the
                             exact-match check MR-04/05 stays exact).
  * normalize_measure      — net contents (unit tokens standardized, spaces
                             removed) so ``750 mL`` and ``750 ml`` compare equal.

All are pure functions with no side effects. ``None`` maps to ``""``.
"""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_general(s: "str | None") -> str:
    """Aggressive normalization for brand & supporting fields (MR-01).

    Lowercase; ``&`` -> `` and ``; curly apostrophes/quotes -> ASCII; every
    non-alphanumeric character -> space; collapse whitespace to single spaces;
    strip. ``None`` -> ``""``.
    """
    if s is None:
        return ""
    text = str(s).lower()
    # Normalize curly quotes/apostrophes to ASCII before stripping punctuation.
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
    )
    text = text.replace("&", " and ")
    text = _NON_ALNUM.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def has_non_ascii(s: "str | None") -> bool:
    """True if the string contains any non-ASCII character (accents, non-Latin).

    ASCII punctuation the normalizer already folds (apostrophes, ``&``, hyphens)
    does NOT trigger this — only characters that fall outside the English-only
    scope and cannot be safely matched (e.g. ``é`` in ``Château``).
    """
    return bool(s) and any(ord(ch) > 127 for ch in str(s))


def normalize_whitespace_only(s: "str | None") -> str:
    """Whitespace-only normalization for the exact warning comparison (MR-04).

    Collapse every run of whitespace (spaces, tabs, newlines) to a single space
    and strip the ends. Case and punctuation are preserved exactly — the warning
    must otherwise match the canonical text character-for-character. ``None`` ->
    ``""``.
    """
    if s is None:
        return ""
    return _WHITESPACE.sub(" ", str(s)).strip()


def normalize_measure(s: "str | None") -> str:
    """Normalization for net contents (FR-08).

    Lowercase; standardize common unit tokens (milliliters -> ml, liters -> l,
    fluid ounces / fl oz -> oz); remove all spaces and periods so ``750 mL`` and
    ``750 ml`` compare equal. ``None`` -> ``""``.
    """
    if s is None:
        return ""
    text = str(s).lower()
    # Multi-word / spaced units first (before spaces are stripped).
    text = re.sub(r"milli\s*lit(?:re|er)s?", "ml", text)
    text = re.sub(r"\bfl\.?\s*oz\b", "oz", text)
    text = re.sub(r"fluid\s*ounces?", "oz", text)
    text = re.sub(r"\bounces?\b", "oz", text)
    text = re.sub(r"lit(?:re|er)s?", "l", text)
    # Remove all remaining spaces and periods.
    text = re.sub(r"[\s.]+", "", text)
    return text
