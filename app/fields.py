"""Field registry — the extensible field set.

Single responsibility: declare WHICH label fields are checked and WHICH rule
type each one uses. This registry drives the matcher, so adding a new label
element later (e.g. TTB's proposed Alcohol Facts panel or an allergen
disclosure) is **data, not a code rewrite** — you add a registry entry, not a
new branch in the orchestrator.

Scaffold pass: declare the rule-type vocabulary and the registry shape. No
population logic, no behavior.
"""

from __future__ import annotations

from enum import Enum


class RuleType(str, Enum):
    """How a given field is compared. Maps to a matcher in ``matching.rules``.

    FUZZY              -> match_brand      (case/punctuation-insensitive; MR-01)
    ABV_EQUIVALENCE    -> match_abv        (proof = 2 x ABV%; MR-02/03)
    EXACT_WARNING      -> match_warning    (char-for-char + all-caps prefix; MR-04/05)
    PRESENT_NORMALIZED -> match_supporting (class/type, net contents, producer,
                                            country of origin; FR-08)
    """

    FUZZY = "fuzzy"
    ABV_EQUIVALENCE = "abv_equivalence"
    EXACT_WARNING = "exact_warning"
    PRESENT_NORMALIZED = "present_normalized"


class FieldSpec:
    """One entry in the registry.

    Intended attributes:
        key: str            # stable identifier, e.g. "brand"
        label: str          # human display name, e.g. "Brand Name"
        rule: RuleType      # which matcher adjudicates this field
        required: bool      # whether absence is itself a failure
    """

    # Stub only.


def get_field_registry() -> "list[FieldSpec]":
    """Return the ordered list of fields to verify.

    Stub: real implementation returns the registry (brand, alcohol content,
    government warning, and supporting fields) so the orchestrator can iterate
    fields generically. No behavior this pass.
    """
    raise NotImplementedError
