"""Deterministic field matchers — the graded core.

Single responsibility: given an extracted value and an expected value, return a
per-field verdict (PASS / FAIL / NEEDS_REVIEW) under that field's rule. All
logic is deterministic Python against stored rules — no AI. Matchers are
dispatched by the field registry (``app.fields``) via each field's ``RuleType``.

Rules (see REQUIREMENTS.md §5):
    match_brand      -> MR-01: case/punctuation-insensitive (fuzzy/normalized)
    match_abv        -> MR-02/03: proof = 2 x ABV%; legitimate absence not a FAIL
    match_warning    -> MR-04/05: char-for-char vs canonical + all-caps prefix
    match_supporting -> FR-08: present/normalized (class/type, net contents,
                        producer name/address, country of origin)

A missing/unreadable extracted value resolves to NEEDS_REVIEW, never a guess.

Scaffold pass: signatures only. No comparison logic this pass — this is the
graded core and gets its own tests (see ``tests/test_matching.py``).
"""

from __future__ import annotations


def match_brand(extracted: "str | None", expected: str):
    """MR-01: normalized/fuzzy brand comparison. Stub."""
    raise NotImplementedError


def match_abv(extracted: "str | None", expected: str):
    """MR-02/03: ABV/proof equivalence (proof = 2 x ABV%); legit absence != FAIL. Stub."""
    raise NotImplementedError


def match_warning(extracted: "str | None", expected: "str | None" = None):
    """MR-04/05: exact match to the canonical warning + all-caps prefix check. Stub."""
    raise NotImplementedError


def match_supporting(extracted: "str | None", expected: str):
    """FR-08: present/normalized match for supporting fields. Stub."""
    raise NotImplementedError
