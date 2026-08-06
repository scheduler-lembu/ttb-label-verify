"""Deterministic field matchers — the graded core.

Single responsibility: given an expected value and an extracted value, return a
per-field ``FieldResult`` (PASS / FAIL / NEEDS_REVIEW) under that field's rule.
All logic is deterministic Python against stored rules — no AI. Matchers are
dispatched by the field registry (``app.fields``) via each field's ``RuleType``.

Every result carries BOTH a ``verdict`` and a machine-readable ``reason`` code
(``app.models.ResultReason``) so agents can triage/group reviews and failures
("all blanks", by field). ``note`` remains the human sentence.

Rules (see REQUIREMENTS.md §5):
    match_brand      -> MR-01: case/punctuation-insensitive (normalized + fuzzy)
    match_abv        -> MR-02/03: proof = 2 x ABV%; absence -> categorized review
    match_warning    -> MR-04/05: char-for-char vs canonical + all-caps prefix (STRICT)
    match_supporting -> FR-08: present/normalized (class/type, net contents,
                        producer name/address, country of origin)

Bias against a false PASS: a missing/unreadable extracted value, or a **blank
required expected** value (D-12), resolves to NEEDS_REVIEW — never a guess.
Non-ASCII/accented values that don't normalize to a match route to a
``special_character`` review (English-only scope). See ASSUMPTIONS D-12…D-14.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from app.fields import FIELD_REGISTRY, RuleType
from app.matching.canonical import CANONICAL_GOVERNMENT_WARNING
from app.matching.normalize import (
    has_non_ascii,
    normalize_general,
    normalize_measure,
    normalize_whitespace_only,
)
from app.models import FieldResult, LabelResult, ResultReason, ResultState

# Short, human-readable rule labels (shown in the UI / result payload).
BRAND_RULE = "Brand — normalized/fuzzy (MR-01)"
ABV_RULE = "Alcohol content — ABV/proof equivalence (MR-02/03)"
WARNING_RULE = "Government Warning — exact vs canonical + all-caps prefix (MR-04/05)"
SUPPORTING_RULE = "Supporting — present/normalized (FR-08)"

# Regex fragments for alcohol strength parsing.
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_PROOF_RE = re.compile(r"(\d+(?:\.\d+)?)\s*proof")
# Case-insensitive locator for the warning prefix (flexible internal whitespace).
_WARNING_PREFIX_RE = re.compile(r"government\s+warning", re.IGNORECASE)


def _is_empty(value: "str | None") -> bool:
    """True if ``value`` is None or blank after stripping."""
    return value is None or str(value).strip() == ""


# --------------------------------------------------------------------------- #
# Brand (MR-01)
# --------------------------------------------------------------------------- #
def match_brand(expected: "str | None", extracted: "str | None") -> FieldResult:
    """MR-01: case- and punctuation-insensitive brand comparison.

    WHY normalized + fuzzy (not exact): a brand is the same brand whether the
    label prints "STONE'S THROW", "Stone's Throw", or "Stones Throw" — case and
    punctuation carry no legal meaning here, so we fold them away
    (``normalize_general``) and then allow a fuzzy gray band for OCR noise.
    WHY non-ASCII short-circuits to review: accented/non-Latin text is outside
    the English-only scope (MA-5); rather than risk a wrong PASS/FAIL on a
    character we can't safely compare, a human decides (D-3 bias against a false
    PASS).
    """
    if _is_empty(expected):  # [D1] blank required field -> categorized review
        return FieldResult(
            field="brand",
            expected=expected,
            extracted=extracted,
            rule=BRAND_RULE,
            verdict=ResultState.NEEDS_REVIEW,
            reason=ResultReason.BLANK_EXPECTED,
            note="brand left empty in application data",
        )

    if _is_empty(extracted):
        return FieldResult(
            field="brand",
            expected=expected,
            extracted=extracted,
            rule=BRAND_RULE,
            verdict=ResultState.NEEDS_REVIEW,
            reason=ResultReason.UNREADABLE,
            note="no brand text read",
        )

    norm_expected = normalize_general(expected)
    norm_extracted = normalize_general(extracted)

    if norm_expected == norm_extracted:
        verdict, reason, note = ResultState.PASS, ResultReason.MATCH, "normalized exact match"
    elif has_non_ascii(expected) or has_non_ascii(extracted):
        verdict, reason, note = (
            ResultState.NEEDS_REVIEW,
            ResultReason.SPECIAL_CHARACTER,
            "non-standard characters — needs human check",
        )
    else:
        score = fuzz.token_sort_ratio(norm_expected, norm_extracted)
        # Brand thresholds per MA-3: pass >=90, review >=75, else FAIL. The wide
        # review band (75-89) is deliberate — a near-miss brand is exactly the
        # case where a confident wrong PASS would be worst, so it goes to a human.
        if score >= 90:
            verdict, reason, note = ResultState.PASS, ResultReason.MATCH, f"fuzzy match (score {score:.0f})"
        elif score >= 75:
            verdict, reason, note = (
                ResultState.NEEDS_REVIEW,
                ResultReason.BORDERLINE,
                f"borderline (score {score:.0f})",
            )
        else:
            verdict, reason, note = ResultState.FAIL, ResultReason.MISMATCH, f"brand mismatch (score {score:.0f})"

    return FieldResult(
        field="brand",
        expected=expected,
        extracted=extracted,
        rule=BRAND_RULE,
        verdict=verdict,
        reason=reason,
        note=note,
    )


# --------------------------------------------------------------------------- #
# Alcohol content (MR-02/03)
# --------------------------------------------------------------------------- #
def parse_strength(s: "str | None") -> "float | None":
    """Parse an alcohol strength into an **ABV %** value.

    A percentage (``45%``, ``45 % alc``) returns that number directly; otherwise
    a proof value (``90 proof``) returns proof / 2; otherwise ``None``.
    """
    if _is_empty(s):
        return None
    text = str(s).lower()
    m = _PERCENT_RE.search(text)
    if m:
        return float(m.group(1))
    m = _PROOF_RE.search(text)
    if m:
        return float(m.group(1)) / 2
    return None


def match_abv(expected: "str | None", extracted: "str | None") -> FieldResult:
    """MR-02/03: ABV/proof equivalence; absence -> categorized review (D-12).

    WHY equivalence (not string match): "45%" and "90 proof" describe the same
    strength (proof = 2 x ABV%), so both are parsed to an ABV number before
    comparing (MR-02). WHY a tolerance: rounding/print variance is normal, so
    values within +-0.15 ABV are treated equal (MA-3). WHY absence is NOT a FAIL:
    ABV may legitimately be omitted on some labels (MR-03); an expected-side
    blank is a data gap for a human to confirm, not a compliance failure, so it
    routes to NEEDS_REVIEW (D-12) rather than PASS (never guess) or FAIL.
    """
    ev = parse_strength(expected)
    xv = parse_strength(extracted)

    if ev is None:
        if xv is None:  # [D1] CHANGED from PASS -> categorized review
            verdict, reason, note = (
                ResultState.NEEDS_REVIEW,
                ResultReason.BLANK_EXPECTED,
                "no alcohol content entered or on label — confirm if legitimately absent",
            )
        else:
            verdict, reason, note = (
                ResultState.NEEDS_REVIEW,
                ResultReason.UNEXPECTED_VALUE,
                "value on label but none expected",
            )
    else:
        if xv is None:
            verdict, reason, note = (
                ResultState.NEEDS_REVIEW,
                ResultReason.UNREADABLE,
                "couldn't read alcohol content",
            )
        elif abs(ev - xv) <= 0.15:  # MA-3 fixed tolerance: +-0.15 ABV absorbs rounding/print variance
            verdict, reason, note = (
                ResultState.PASS,
                ResultReason.MATCH,
                f"ABV/proof equivalent (expected {ev:g}% ≈ read {xv:g}%)",
            )
        else:
            verdict, reason, note = (
                ResultState.FAIL,
                ResultReason.MISMATCH,
                f"ABV mismatch (expected {ev:g}%, read {xv:g}%)",
            )

    return FieldResult(
        field="alcohol_content",
        expected=expected,
        extracted=extracted,
        rule=ABV_RULE,
        verdict=verdict,
        reason=reason,
        note=note,
    )


# --------------------------------------------------------------------------- #
# Government Warning (MR-04/05) — STRICT (Decision 2, unchanged)
# --------------------------------------------------------------------------- #
def match_warning(expected: "str | None", extracted: "str | None") -> FieldResult:
    """MR-04/05: exact match to the canonical warning + all-caps prefix check.

    WHY strict here and nowhere else: the warning is the ONE field where fuzzy
    matching is *wrong* — a single altered/dropped word (e.g. "may cause" ->
    "can cause") is a real compliance defect that must FAIL, not be smoothed
    over (MR-04, D-13, MA-9). So the body is compared char-for-char against the
    stored canonical constant after whitespace-ONLY normalization (D-4): line
    breaks/OCR spacing are noise, but case and punctuation are load-bearing.
    WHY ``expected`` is ignored: the reference is the verified statute text
    (``CANONICAL_GOVERNMENT_WARNING``), not the applicant's typed value — the
    applicant cannot redefine the required wording.
    WHY the prefix is checked separately (MR-05): "GOVERNMENT WARNING" must be
    all-caps by regulation, so title-case "Government Warning" FAILs even if the
    rest of the sentence is perfect — checked on the literal read before the
    body comparison.
    """
    if _is_empty(extracted):
        return FieldResult(
            field="warning",
            expected=CANONICAL_GOVERNMENT_WARNING,
            extracted=extracted,
            rule=WARNING_RULE,
            verdict=ResultState.NEEDS_REVIEW,
            reason=ResultReason.UNREADABLE,
            note="warning not read",
        )

    raw = str(extracted)

    # --- Prefix check (MR-05): must be present AND all caps. ---
    m = _WARNING_PREFIX_RE.search(raw)
    if not m:
        return FieldResult(
            field="warning",
            expected=CANONICAL_GOVERNMENT_WARNING,
            extracted=extracted,
            rule=WARNING_RULE,
            verdict=ResultState.FAIL,
            reason=ResultReason.WARNING_PREFIX_MISSING,
            note="warning prefix missing",
        )
    prefix_norm = re.sub(r"\s+", " ", m.group(0))
    if prefix_norm != "GOVERNMENT WARNING":
        return FieldResult(
            field="warning",
            expected=CANONICAL_GOVERNMENT_WARNING,
            extracted=extracted,
            rule=WARNING_RULE,
            verdict=ResultState.FAIL,
            reason=ResultReason.WARNING_PREFIX_NOT_ALLCAPS,
            note="prefix not all caps",
        )

    # --- Exact check (MR-04): whitespace-normalized, char-for-char. ---
    if normalize_whitespace_only(extracted) == CANONICAL_GOVERNMENT_WARNING:
        verdict, reason, note = ResultState.PASS, ResultReason.MATCH, "matches canonical wording"
    else:
        verdict, reason, note = (
            ResultState.FAIL,
            ResultReason.WARNING_WORDING,
            "text deviates from canonical wording",
        )

    return FieldResult(
        field="warning",
        expected=CANONICAL_GOVERNMENT_WARNING,
        extracted=extracted,
        rule=WARNING_RULE,
        verdict=verdict,
        reason=reason,
        note=note,
    )


# --------------------------------------------------------------------------- #
# Supporting fields (FR-08)
# --------------------------------------------------------------------------- #
def match_supporting(
    field: str,
    expected: "str | None",
    extracted: "str | None",
    required: bool = True,
) -> FieldResult:
    """FR-08: present/normalized match for a supporting field.

    ``required`` is live (D-12): a blank required field routes to NEEDS_REVIEW;
    a blank optional field (imports-only country of origin) still PASSES.
    """
    if _is_empty(expected):
        if required:  # [D1] the flag now drives this
            return FieldResult(
                field=field,
                expected=expected,
                extracted=extracted,
                rule=SUPPORTING_RULE,
                verdict=ResultState.NEEDS_REVIEW,
                reason=ResultReason.BLANK_EXPECTED,
                note="required field left empty in application data",
            )
        return FieldResult(
            field=field,
            expected=expected,
            extracted=extracted,
            rule=SUPPORTING_RULE,
            verdict=ResultState.PASS,
            reason=ResultReason.NOT_REQUIRED,
            note="not required / nothing to verify",
        )

    if _is_empty(extracted):
        return FieldResult(
            field=field,
            expected=expected,
            extracted=extracted,
            rule=SUPPORTING_RULE,
            verdict=ResultState.NEEDS_REVIEW,
            reason=ResultReason.UNREADABLE,
            note=f"couldn't read {field}",
        )

    normalizer = normalize_measure if field == "net_contents" else normalize_general
    norm_expected = normalizer(expected)
    norm_extracted = normalizer(extracted)

    if norm_expected == norm_extracted:
        verdict, reason, note = ResultState.PASS, ResultReason.MATCH, "normalized match"
    elif has_non_ascii(expected) or has_non_ascii(extracted):
        verdict, reason, note = (
            ResultState.NEEDS_REVIEW,
            ResultReason.SPECIAL_CHARACTER,
            "non-standard characters — needs human check",
        )
    else:
        score = fuzz.token_sort_ratio(norm_expected, norm_extracted)
        # Supporting thresholds per MA-3: pass >=85, review >=70, else FAIL. Set
        # slightly looser than brand (90/75) because these free-text fields
        # (producer address, class/type) carry more benign print variation.
        if score >= 85:
            verdict, reason, note = ResultState.PASS, ResultReason.MATCH, f"fuzzy match (score {score:.0f})"
        elif score >= 70:
            verdict, reason, note = (
                ResultState.NEEDS_REVIEW,
                ResultReason.BORDERLINE,
                f"borderline (score {score:.0f})",
            )
        else:
            verdict, reason, note = ResultState.FAIL, ResultReason.MISMATCH, f"mismatch (score {score:.0f})"

    return FieldResult(
        field=field,
        expected=expected,
        extracted=extracted,
        rule=SUPPORTING_RULE,
        verdict=verdict,
        reason=reason,
        note=note,
    )


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def run_matchers(expected: dict, extracted: dict) -> LabelResult:
    """Dispatch every registry field to its matcher and assemble a LabelResult.

    ``expected`` and ``extracted`` are dicts keyed by the field-registry keys
    (see ``fields.FIELD_REGISTRY``). Missing keys are treated as absent values.
    """
    results: list[FieldResult] = []
    for field_def in FIELD_REGISTRY:
        exp = expected.get(field_def.key)
        ext = extracted.get(field_def.key)

        if field_def.rule == RuleType.BRAND:
            result = match_brand(exp, ext)
        elif field_def.rule == RuleType.ABV:
            result = match_abv(exp, ext)
        elif field_def.rule == RuleType.WARNING:
            result = match_warning(exp, ext)
        else:  # RuleType.SUPPORTING
            result = match_supporting(field_def.key, exp, ext, field_def.required)

        results.append(result)

    return LabelResult.from_fields(results)
