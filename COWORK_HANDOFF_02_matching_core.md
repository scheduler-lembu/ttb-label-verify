# COWORK HANDOFF #2 — Deterministic Matching Core + Tests

## START HERE
Read these first (locked source of truth), then this handoff:
- `C:\Users\finan\Documents\ttb-label-verify\REQUIREMENTS.md`  (esp. §5 Matching Rules MR-01…MR-06, and FR-05…FR-09)
- `C:\Users\finan\Documents\ttb-label-verify\ASSUMPTIONS_AND_TRADEOFFS.md`  (Principle A: "AI reads, code judges")
- `C:\Users\finan\Documents\ttb-label-verify\ARCHITECTURE.md`  (§5 Result Model, §9 Extensible Field Set, §11 Technical Choices)

---

## OBJECTIVE
Turn the **matching** stubs into real, working, unit-tested code — the deterministic
"code judges" half of the app. This pass implements the field comparison logic and
its tests **only**. **No AI, no API calls, no network, no UI, no extraction, no
batch, no deployment.** Everything here runs offline and is proven by `pytest`.

This is the graded core (MR-01…MR-05, FR-05…FR-09). It must be correct and fully
tested before any extraction or UI is wired to it.

---

## LOCKED CONTEXT (build to these; already decided)
- **Three-state result:** every field → `PASS`, `FAIL`, or `NEEDS_REVIEW`. Bias
  against a false PASS: anything unreadable/uncertain → `NEEDS_REVIEW`, never a guess.
- **Brand** (MR-01): case- and punctuation-insensitive; `&`↔`and`; apostrophes,
  hyphens, spacing ignored. `STONE'S THROW` must MATCH `Stone's Throw`.
- **Alcohol content** (MR-02): proof = 2 × ABV%. `45% Alc./Vol. (90 Proof)` must
  satisfy expected `45%` **or** `90 proof`. (MR-03): a **legitimately absent** ABV
  (nothing expected, nothing on label) is **not** a FAIL.
- **Government Warning** (MR-04/05): matched **exactly**, character-for-character,
  against the **stored canonical constant** (below) after **whitespace-only**
  normalization. The `GOVERNMENT WARNING` prefix must be **all caps**; title case
  (`Government Warning`) must FAIL.
- **Supporting fields** (FR-08): class/type, net contents, producer, country of
  origin → present/normalized match. Country of origin is required only for imports.
- **Field registry** drives which fields are checked and by which rule (extensible).

---

## VERIFIED CANONICAL WARNING TEXT — paste EXACTLY, do not retype
Sourced from the eCFR, **27 CFR 16.21** (Title 27, current as of 2026-07-24).
Store it as a **single continuous line** (the regulation requires the statement to
appear as one continuous statement). Copy this string character-for-character:

```
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.
```

---

## FILES TO EDIT (turn these stubs into real code)
```
C:\Users\finan\Documents\ttb-label-verify\app\models.py
C:\Users\finan\Documents\ttb-label-verify\app\fields.py
C:\Users\finan\Documents\ttb-label-verify\app\matching\normalize.py
C:\Users\finan\Documents\ttb-label-verify\app\matching\canonical.py
C:\Users\finan\Documents\ttb-label-verify\app\matching\rules.py
C:\Users\finan\Documents\ttb-label-verify\tests\test_matching.py
C:\Users\finan\Documents\ttb-label-verify\.gitignore   (one-line addition — see CHANGES)
```

---

## CHANGES

### `app/models.py`
- `ResultState(str, Enum)` with members `PASS`, `FAIL`, `NEEDS_REVIEW`.
- `FieldResult` (pydantic): `field: str`, `expected: str | None`, `extracted: str | None`,
  `rule: str` (short human-readable rule label), `verdict: ResultState`, `note: str | None`.
- `LabelResult` (pydantic): `fields: list[FieldResult]` and `overall: ResultState`,
  where **overall = FAIL if any field FAILs; else NEEDS_REVIEW if any field is
  NEEDS_REVIEW; else PASS.** Provide a classmethod/helper that computes `overall`
  from a list of `FieldResult`.
- `BatchResult` (pydantic): minimal — `items: list[LabelResult]` plus integer counts
  `passed`, `failed`, `needs_review`. (Defined now, used in a later batch pass.)

### `app/matching/normalize.py`
- `normalize_general(s: str | None) -> str` — for brand & supporting. Lowercase;
  replace `&` with ` and `; convert curly apostrophes/quotes to ASCII; replace all
  non-alphanumeric characters with spaces; collapse whitespace to single spaces; strip.
  `None` → `""`.
- `normalize_whitespace_only(s: str | None) -> str` — for the warning. Collapse every
  run of whitespace (spaces, tabs, newlines) to a single space; strip ends.
  **Preserve case and punctuation exactly.** `None` → `""`.
- `normalize_measure(s: str | None) -> str` — for net contents. Lowercase; remove all
  spaces; standardize unit tokens (`milliliters`/`millilitre`→`ml`, `liter`/`litre`/`l`→`l`,
  `fl oz`/`fluidounces`/`oz`→`oz`). `None` → `""`. (Keep simple; regex is fine.)

### `app/matching/canonical.py`
- Set `CANONICAL_GOVERNMENT_WARNING` to the **verified string above** (paste exactly,
  single line). Keep `REQUIRED_WARNING_PREFIX = "GOVERNMENT WARNING:"`.
- Replace the `# TODO: source...` line with a sourcing comment:
  `# Source: eCFR 27 CFR 16.21, Title 27 current as of 2026-07-24. Verbatim; do not edit wording.`

### `app/matching/rules.py`
Implement four matchers, each returning a `FieldResult`, plus a runner. Use
`rapidfuzz` (already in requirements) for similarity where noted.

- `match_brand(expected, extracted) -> FieldResult`  *(rule label: "Brand — normalized/fuzzy (MR-01)")*
  - extracted empty/None → `NEEDS_REVIEW` (note: "no brand text read").
  - normalize both with `normalize_general`; if equal → `PASS`.
  - else `score = rapidfuzz.fuzz.token_sort_ratio(norm_expected, norm_extracted)`:
    `>= 90` → `PASS`; `75–89` → `NEEDS_REVIEW`; `< 75` → `FAIL`.

- `match_abv(expected, extracted) -> FieldResult`  *(rule label: "Alcohol content — ABV/proof equivalence (MR-02/03)")*
  - Helper `parse_strength(s) -> float | None`: return an **ABV %** value. Regex a
    percentage (`45%`, `45 % alc`) → that number; else regex proof (`90 proof`) →
    proof / 2; else `None`.
  - `ev = parse_strength(expected)`, `xv = parse_strength(extracted)`.
  - If `ev is None` (nothing expected): `xv is None` → `PASS` (note: "no alcohol
    content required/declared" — MR-03 legit absence); `xv` present → `NEEDS_REVIEW`
    (note: "value on label but none expected").
  - If `ev is not None`: `xv is None` → `NEEDS_REVIEW` (note: "couldn't read alcohol
    content"); else `PASS` if `abs(ev - xv) <= 0.15` else `FAIL`.

- `match_warning(expected, extracted) -> FieldResult`  *(rule label: "Government Warning — exact vs canonical + all-caps prefix (MR-04/05)")*
  - **Ignore `expected`**; the reference is `CANONICAL_GOVERNMENT_WARNING`.
  - extracted empty/None → `NEEDS_REVIEW` (note: "warning not read").
  - **Prefix check (MR-05):** find "government warning" case-insensitively in the raw
    extracted text. If found but the actual matched substring is **not** exactly
    `GOVERNMENT WARNING` (uppercase) → `FAIL` (note: "prefix not all caps"). If not
    found at all → `FAIL` (note: "warning prefix missing").
  - **Exact check (MR-04):** `normalize_whitespace_only(extracted) == CANONICAL...`
    → `PASS`; else `FAIL` (note: "text deviates from canonical wording").

- `match_supporting(field, expected, extracted, required) -> FieldResult`  *(rule label: "Supporting — present/normalized (FR-08)")*
  - expected empty/None → `PASS` (note: "not required / nothing to verify") — this
    covers domestic country-of-origin (`required=False`).
  - expected present, extracted empty/None → `NEEDS_REVIEW` (note: "couldn't read {field}").
  - else normalize both (`normalize_measure` for `net_contents`, else `normalize_general`);
    equal → `PASS`; else `token_sort_ratio >= 85` → `PASS`; `70–84` → `NEEDS_REVIEW`;
    `< 70` → `FAIL`.

- `run_matchers(expected: dict, extracted: dict) -> LabelResult` — iterate the
  `FIELD_REGISTRY` from `fields.py`, dispatch each field to the right matcher by its
  `RuleType`, collect `FieldResult`s, compute `overall`, return `LabelResult`.

### `app/fields.py`
- `RuleType(str, Enum)`: `BRAND`, `ABV`, `WARNING`, `SUPPORTING`.
- A `FieldDef` (pydantic or dataclass): `key: str`, `label: str`, `rule: RuleType`,
  `required: bool` (default True; `country_of_origin` default False = imports-only).
- `FIELD_REGISTRY: list[FieldDef]` covering: `brand` (BRAND), `alcohol_content` (ABV),
  `warning` (WARNING), `class_type` (SUPPORTING), `net_contents` (SUPPORTING),
  `producer` (SUPPORTING), `country_of_origin` (SUPPORTING, required=False).
  Keys must match the `batch_template.csv` columns.

### `.gitignore`
- Append a line: `.claude/`  (keeps the local Cowork settings folder out of the repo).

---

## DO NOT TOUCH
- `README.md`, `REQUIREMENTS.md`, `ASSUMPTIONS_AND_TRADEOFFS.md`,
  `Working_Document_List.txt`, `ARCHITECTURE.md`, and the HANDOFF files — inputs only.
- `app/extraction/*`, `app/main.py`, `app/verify.py`, `app/batch.py`, `app/cache.py`,
  `app/config.py`, `app/templates/*`, `app/static/*` — leave as stubs this pass.
- No AI/API calls, no network, no `httpx`/provider SDKs, no Docker, no deploy, no push.
- Do not alter the canonical warning wording. Do not hardcode any model or price.

---

## ACCEPTANCE TEST
Cowork performs these and reports the output:
1. Install deps: `pip install -r requirements.txt` (offline libs only — no keys).
2. Run the tests: `pytest -q`.
3. **All tests pass**, and the suite includes at least these graded cases:
   - Brand: `STONE'S THROW` vs `Stone's Throw` → PASS; `&` vs `and` → PASS; a
     different brand → FAIL; empty extracted → NEEDS_REVIEW.
   - ABV: expected `45%` vs `45% Alc./Vol. (90 Proof)` → PASS; expected `90 proof`
     vs the same → PASS; `40%` vs `45%` → FAIL; both absent → PASS (MR-03);
     expected present, extracted empty → NEEDS_REVIEW.
   - Warning: exact canonical → PASS; title-case prefix → FAIL; one altered word →
     FAIL; canonical with extra spaces/newlines → PASS; empty → NEEDS_REVIEW.
   - Supporting: `750 mL` vs `750 ml` → PASS; domestic country-of-origin blank/blank
     → PASS.
4. Paste the full `pytest` summary output back to the Testing Manager.

When tests pass and the output is captured, STOP and return the `pytest` output +
the final `rules.py` to the Testing Manager for review. Do not push to GitHub.
