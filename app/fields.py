"""Field registry — the extensible field set.

Single responsibility: declare WHICH label fields are checked and WHICH rule
type each one uses. This registry drives the matcher, so adding a new label
element later (e.g. TTB's proposed Alcohol Facts panel or an allergen
disclosure) is **data, not a code rewrite** — you add a registry entry, not a
new branch in the orchestrator.

Field keys MUST match the columns in ``sample_data/batch_template.csv``.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class RuleType(str, Enum):
    """How a given field is compared. Maps to a matcher in ``matching.rules``.

    BRAND      -> match_brand      (case/punctuation-insensitive; MR-01)
    ABV        -> match_abv        (proof = 2 x ABV%; MR-02/03)
    WARNING    -> match_warning    (char-for-char vs canonical + all-caps; MR-04/05)
    SUPPORTING -> match_supporting (class/type, net contents, producer,
                                    country of origin; FR-08)
    """

    BRAND = "brand"
    ABV = "abv"
    WARNING = "warning"
    SUPPORTING = "supporting"


class FieldDef(BaseModel):
    """One entry in the field registry."""

    key: str
    label: str
    rule: RuleType
    required: bool = True  # country_of_origin overrides to False (imports-only)


# The ordered set of fields the app verifies. Keys mirror the batch CSV columns.
FIELD_REGISTRY: list[FieldDef] = [
    FieldDef(key="brand", label="Brand Name", rule=RuleType.BRAND),
    FieldDef(key="alcohol_content", label="Alcohol Content", rule=RuleType.ABV),
    FieldDef(key="warning", label="Government Warning", rule=RuleType.WARNING),
    FieldDef(key="class_type", label="Class/Type", rule=RuleType.SUPPORTING),
    FieldDef(key="net_contents", label="Net Contents", rule=RuleType.SUPPORTING),
    FieldDef(key="producer", label="Producer Name/Address", rule=RuleType.SUPPORTING),
    FieldDef(
        key="country_of_origin",
        label="Country of Origin",
        rule=RuleType.SUPPORTING,
        required=False,  # required only for imports
    ),
]
