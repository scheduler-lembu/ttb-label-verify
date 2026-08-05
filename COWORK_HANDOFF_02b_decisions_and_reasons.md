# COWORK HANDOFF #2b — Decisions, Review-Reason Taxonomy, Doc Sync

## START HERE
Read these first, then this handoff:
- `C:\Users\finan\Documents\ttb-label-verify\REQUIREMENTS.md`  (§4 FR, §5 MR)
- `C:\Users\finan\Documents\ttb-label-verify\ASSUMPTIONS_AND_TRADEOFFS.md`
- `C:\Users\finan\Documents\ttb-label-verify\app\matching\rules.py`  (current matchers)
- `C:\Users\finan\Documents\ttb-label-verify\app\models.py`  (current result models)

---

## OBJECTIVE
Apply two locked decisions, add a **review-reason taxonomy** to results, and **sync
the two docs** so paper matches code. Still **offline** — no AI, no network, no UI,
no extraction, no batch, no deploy. Proven by `pytest`.

---

## DECISIONS LOCKED (build to these exactly)
- **Decision 1 — Blank required field → `NEEDS_REVIEW`, categorized** (not PASS).
  When the **expected** value for a required field is empty, the field goes to
  `NEEDS_REVIEW` with reason `blank_expected`. Optional fields (country of origin,
  `required=False`) still PASS with reason `not_required`. (This still satisfies
  MR-03 — a review is not a failure.)
- **Decision 2 — Government Warning stays STRICT** (character-for-character incl.
  case in the body). **No change to warning strictness** — this pass only adds
  reason codes to it.

---

## PART A — CODE

### `app/models.py`
- Add an enum:
  ```python
  class ResultReason(str, Enum):
      MATCH = "match"                                  # PASS, clean
      NOT_REQUIRED = "not_required"                    # PASS, optional field, nothing to verify
      MISMATCH = "mismatch"                            # FAIL, value disagreement
      BLANK_EXPECTED = "blank_expected"                # NEEDS_REVIEW, required field left empty
      UNREADABLE = "unreadable"                         # NEEDS_REVIEW, couldn't read off the label
      UNEXPECTED_VALUE = "unexpected_value"            # NEEDS_REVIEW, label has value, none expected
      BORDERLINE = "borderline"                        # NEEDS_REVIEW, fuzzy gray band
      SPECIAL_CHARACTER = "special_character"          # NEEDS_REVIEW, non-ASCII/accented, can't safely match
      WARNING_PREFIX_MISSING = "warning_prefix_missing"    # FAIL
      WARNING_PREFIX_NOT_ALLCAPS = "warning_prefix_not_allcaps"  # FAIL
      WARNING_WORDING = "warning_wording"              # FAIL, body deviates from canonical
  ```
- Add a field to `FieldResult`: `reason: ResultReason`. Keep the existing
  human-readable `note: str | None` as well (reason = machine-sortable category,
  note = the sentence shown to the agent).

### `app/matching/normalize.py`
- Add a helper:
  ```python
  def has_non_ascii(s: "str | None") -> bool:
      """True if the string contains any non-ASCII character (accents, non-Latin).
      ASCII punctuation the normalizer already folds (apostrophes, &, hyphens)
      does NOT trigger this."""
      return bool(s) and any(ord(ch) > 127 for ch in str(s))
  ```

### `app/matching/rules.py`
Every matcher now sets `reason=` on the `FieldResult` it returns, per the mapping
below. Verdict logic is unchanged except where a decision changes it (flagged **[D1]**).

- **`match_brand(expected, extracted)`**
  - `expected` empty → `NEEDS_REVIEW`, reason `BLANK_EXPECTED`, note "brand left empty in application data". **[D1 — new check, add it]**
  - else `extracted` empty → `NEEDS_REVIEW`, reason `UNREADABLE`, note "no brand text read".
  - else normalize both; if equal → `PASS`, reason `MATCH`.
  - else if `has_non_ascii(expected) or has_non_ascii(extracted)` → `NEEDS_REVIEW`,
    reason `SPECIAL_CHARACTER`, note "non-standard characters — needs human check". **(new)**
  - else fuzzy `token_sort_ratio`: `>=90` → PASS/`MATCH`; `75–89` → NEEDS_REVIEW/`BORDERLINE`; `<75` → FAIL/`MISMATCH`.

- **`match_abv(expected, extracted)`**
  - `ev = parse_strength(expected)`, `xv = parse_strength(extracted)`.
  - `ev is None`:
    - `xv is None` → **`NEEDS_REVIEW`, reason `BLANK_EXPECTED`**, note "no alcohol content entered or on label — confirm if legitimately absent". **[D1 — CHANGED from PASS]**
    - else → `NEEDS_REVIEW`, reason `UNEXPECTED_VALUE`, note "value on label but none expected".
  - `ev is not None`:
    - `xv is None` → `NEEDS_REVIEW`, reason `UNREADABLE`.
    - `abs(ev-xv) <= 0.15` → `PASS`, reason `MATCH`.
    - else → `FAIL`, reason `MISMATCH`.

- **`match_warning(expected, extracted)`** — strictness unchanged (Decision 2), add reasons:
  - empty → `NEEDS_REVIEW`, reason `UNREADABLE`.
  - prefix missing → `FAIL`, reason `WARNING_PREFIX_MISSING`.
  - prefix present but not all-caps → `FAIL`, reason `WARNING_PREFIX_NOT_ALLCAPS`.
  - whitespace-normalized exact vs canonical: equal → `PASS`, reason `MATCH`; else → `FAIL`, reason `WARNING_WORDING`.

- **`match_supporting(field, expected, extracted, required=True)`** — make `required` **live** **[D1]**:
  - `expected` empty:
    - `required` → `NEEDS_REVIEW`, reason `BLANK_EXPECTED`, note "required field left empty in application data". **[D1 — CHANGED; the flag now drives this]**
    - not `required` → `PASS`, reason `NOT_REQUIRED`, note "not required / nothing to verify".
  - else `extracted` empty → `NEEDS_REVIEW`, reason `UNREADABLE`.
  - else normalize (`normalize_measure` for `net_contents`, else `normalize_general`); equal → `PASS`/`MATCH`.
  - else if `has_non_ascii(expected) or has_non_ascii(extracted)` → `NEEDS_REVIEW`/`SPECIAL_CHARACTER`. **(new)**
  - else fuzzy: `>=85` → PASS/`MATCH`; `70–84` → NEEDS_REVIEW/`BORDERLINE`; `<70` → FAIL/`MISMATCH`.

- **`run_matchers`** — unchanged control flow; it already passes `field_def.required`
  to `match_supporting`. Just carry the new `reason` through (it's on each `FieldResult`).

---

## PART B — TESTS (`tests/test_matching.py`)
- **Change** `test_abv_both_absent_passes` → `test_abv_both_absent_needs_review`:
  assert `match_abv(None, None).verdict == NEEDS_REVIEW` and `.reason == ResultReason.BLANK_EXPECTED`.
  (Also update the `""`/`""` case the same way.)
- **Add** `test_brand_blank_expected_needs_review`: `match_brand("", "Old Tom")` →
  NEEDS_REVIEW, reason `BLANK_EXPECTED`.
- **Add** `test_supporting_required_blank_needs_review`:
  `match_supporting("class_type", "", "Bourbon", required=True)` → NEEDS_REVIEW, reason `BLANK_EXPECTED`.
- **Keep/extend** `test_supporting_domestic_country_blank_blank_passes`: now also assert
  `.reason == ResultReason.NOT_REQUIRED`.
- **Add** `test_brand_special_character_needs_review`:
  `match_brand("Chateau", "Château")` → NEEDS_REVIEW, reason `SPECIAL_CHARACTER`.
- **Add reason assertions** to the warning tests already present (prefix-missing →
  `WARNING_PREFIX_MISSING`; title-case → `WARNING_PREFIX_NOT_ALLCAPS`; altered word →
  `WARNING_WORDING`; exact → `MATCH`).
- **Update** the runner tests only if a fixture field was relying on both-absent ABV
  passing (the "all pass" fixture uses `alcohol_content="45%"` expected, so it is
  unaffected — verify this).
- All previously-passing spec cases (STONE'S THROW, 90 proof/45%, strict warning, etc.)
  must still pass unchanged.

---

## PART C — DOC SYNC (make paper match code)

### `app/matching/rules.py` docstrings
Update the module docstring's brief rule list to mention the reason codes and the
blank-required-field behavior. (Prose only.)

### `ASSUMPTIONS_AND_TRADEOFFS.md`
- **§B table — append three rows:**
  - `D-12 | Blank required field | Empty required expected value → NEEDS_REVIEW (categorized), not PASS | Closes a false-PASS hole; makes the required flag meaningful | A little more review on incomplete entries | Form pre-validation; pull expected values from COLA`
  - `D-13 | Warning body strictness | Exact characters incl. case (strict) | MR-04 says "character-for-character"; over-strict beats under-strict on the one exact field | Re-cased/reformatted-but-correct warnings FAIL (false-FAIL); visible + overridable | Same; optional case-insensitive body mode`
  - `D-14 | Review reason taxonomy | Every result carries a machine-readable reason code | Lets agents triage/group reviews ("all blanks", by field) — efficiency for 47 agents, esp. batch | Small enum to maintain | Same + filterable review-queue UI`
- **§C table — append three rows:**
  - `MA-8 | Warning is matched to the stored canonical constant, not the agent's input value | MR-04 says "against the stored canonical" | Low — agents may expect their entry to matter; documented`
  - `MA-9 | "Exact" = exact characters including case in the body, not just wording | Strictest defensible reading of MR-04 (D-13) | Medium — re-cased/reformatted-but-correct warnings FAIL; overridable`
  - `MA-10 | The extractor delivers each field (esp. the warning) as a clean, bounded value — no trailing text scooped in | Exact-match assumes the warning field isn't polluted (e.g. "CONTAINS SULFITES") | Medium — pushed onto HANDOFF #3's extraction prompt`
- **§C — edit MA-3:** append: "Concrete thresholds (committed): brand fuzzy 90/75, supporting 85/70, ABV ±0.15% ABV."
- **§C — edit MA-5:** replace the risk note with: "Confirmed. English-only is implemented (the normalizer keeps a–z/0–9). Non-ASCII/accented values are detected and routed to NEEDS_REVIEW (special_character) rather than silently degraded. Risk: low."
- **§D — append three bullets:**
  - "Literal-spec fidelity vs. real-world robustness: matchers are built to the letter of MR-01/02/04; beyond-spec cases (subset brand names, volume-unit conversion) are deferred and documented, per CON-04."
  - "Strict warning → false-FAIL bias: correctly-worded but re-cased/reformatted warnings FAIL rather than pass. Consistent with recall-over-precision, but note it produces false FAILs, not just reviews. Each is shown with extracted-vs-canonical and is overridable."
  - "Determinism → no model fallback: real-world coverage is exactly what we encode; the deliberately-nasty test-label catalog is the safety net, not the matcher."
- **§E — append:** "9. Accented/non-ASCII values are detected and routed to a special_character review, not silently mis-matched (English-only boundary). 10. Every result carries a reason code enabling triage/grouping of reviews and failures."
- **§F — mark resolved:** Q-1 (English-only) → Confirmed. Add a line: "Decisions D-12 (blank→review) and D-13 (strict warning) resolved."

### `REQUIREMENTS.md`
- **§4 FR table — add a row:**
  `FR-13 | S | categorize each NEEDS_REVIEW / FAIL result with a machine-readable reason code (blank, unreadable, borderline, special-character, warning-prefix, wording, mismatch, ...) to support triage and grouping. | Test | stakeholder efficiency`
- **§5 — under the MR-03 row, add a note:** "Decided behavior (D-12): a blank/absent ABV (nothing expected, nothing on the label) → NEEDS_REVIEW with reason blank_expected, not PASS — which still satisfies MR-03 ('absence shall not be recorded as a failure'), since a review is not a failure. A human confirms whether the omission is legitimate."
- **§5 — under MR-01 acceptance detail, add:** "Values containing non-ASCII/accented characters that do not normalize to a match are routed to NEEDS_REVIEW (special_character), consistent with the English-only scope (OOS-04 / MA-5)."

---

## DO NOT TOUCH
- `README.md`, `Working_Document_List.txt`, `ARCHITECTURE.md`, the HANDOFF files.
- `app/extraction/*`, `app/main.py`, `app/verify.py`, `app/batch.py`, `app/cache.py`,
  `app/config.py`, `app/templates/*`, `app/static/*` — still stubs this pass.
- Do NOT change warning **strictness** (Decision 2 = strict stays).
- Do NOT alter the canonical warning wording. No AI/network/Docker/deploy/push. No prices.

---

## ACCEPTANCE TEST
1. `pip install -r requirements.txt`
2. `pytest -q` — **all pass**, including the changed/added cases:
   - ABV both-absent → NEEDS_REVIEW / `blank_expected` (was PASS).
   - Brand blank-expected → NEEDS_REVIEW / `blank_expected`.
   - Supporting required blank → NEEDS_REVIEW / `blank_expected`; domestic country blank → PASS / `not_required`.
   - Brand `Château` vs `Chateau` → NEEDS_REVIEW / `special_character`.
   - Warning reasons present (`warning_prefix_missing`, `warning_prefix_not_allcaps`, `warning_wording`, `match`); strictness unchanged.
   - All prior spec cases still pass.
3. Confirm the doc edits are in `ASSUMPTIONS_AND_TRADEOFFS.md` and `REQUIREMENTS.md`.
4. Paste the `pytest` summary + a short list of what changed in each doc back to the Testing Manager. **Do not push.**
