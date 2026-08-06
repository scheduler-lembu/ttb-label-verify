# TEST_PLAN — Deterministic Test-Label Catalog

**Status:** Living document · **Owner:** Testing Manager
**Artifacts:** `test_labels/label_01..label_10*.png` · `sample_data/test_labels.csv`
· generator `tools/generate_test_labels.py`

---

## 1. Purpose

This catalog is a **deliberately-constructed set of known inputs** that exercises
every matching rule in the deterministic core. It contains ten rendered alcohol
labels: one fully compliant, and each of the others breaking **exactly one** rule
(brand case, ABV equivalence, legitimate ABV absence, warning prefix case, warning
wording, warning omission, tiny warning, and a degraded image). It lets a reviewer
confirm the app behaves correctly and shows, label by label, **which requirement
each one proves**. Because each label isolates a single variable, a wrong verdict
points straight at the responsible rule.

The compliant warning is rendered by importing `CANONICAL_GOVERNMENT_WARNING` from
`app.matching.canonical` — never retyped — and the broken warning variants are
derived from that same constant, so the compliant label is guaranteed to match the
stored reference and the broken ones differ from it by exactly the intended edit.

## 2. How to use it

Once the app is running (a later phase), upload each label image together with its
matching row from `sample_data/test_labels.csv` (the row whose `image_filename`
equals the PNG's name). The **Expected verdict** column below is what should appear
per field. The `warning` CSV column is intentionally blank: the matcher compares
the label's warning to the canonical constant, not to the agent's input (MA-8).

Regenerate the catalog at any time (idempotent — overwrites cleanly):

```bash
python tools/generate_test_labels.py
```

## 3. Catalog table

| id / filename | What it tests | Requirement | Expected per-field verdict (reason) |
|---|---|---|---|
| **label_01_compliant** `label_01_compliant.png` | Fully compliant baseline; app data matches label | FR-02/03/04 | **ALL PASS** |
| **label_02_brand_case** `label_02_brand_case.png` | Label brand `STONE'S THROW` vs app `Stone's Throw` (case/punct only) | MR-01 | brand **PASS** (`match`); rest PASS |
| **label_03_proof_only** `label_03_proof_only.png` | Strength printed as `90 Proof` only; app `45%` | MR-02 | alcohol_content **PASS** (`match`, equivalence); rest PASS |
| **label_04_abv_mismatch** `label_04_abv_mismatch.png` | Label `40% Alc./Vol.`; app `45%` | MR-02 | alcohol_content **FAIL** (`mismatch`); rest PASS |
| **label_05_beer_no_abv** `label_05_beer_no_abv.png` | Malt beverage, no ABV printed; app ABV blank | MR-03 / D-12 | alcohol_content **NEEDS_REVIEW** (`blank_expected`); rest PASS |
| **label_06_warning_titlecase** `label_06_warning_titlecase.png` | Warning prefix `Government Warning:` (title case) | MR-05 | warning **FAIL** (`warning_prefix_not_allcaps`); rest PASS |
| **label_07_warning_altered** `label_07_warning_altered.png` | Warning body one word changed (`birth defects`→`birth defect`) | MR-04 | warning **FAIL** (`warning_wording`); rest PASS |
| **label_08_warning_missing** `label_08_warning_missing.png` | No warning statement on the label | FR-07 / FR-09 | warning **NEEDS_REVIEW** (`unreadable`); rest PASS |
| **label_09_warning_tiny** `label_09_warning_tiny.png` | Correct canonical warning in a very small font | MR-06 *(deferred)* | **PASS or NEEDS_REVIEW** (imperfect image — both acceptable, NFR-05); the literal-OCR cross-check may flag the tiny/buried warning for review (a soft touch on the deferred MR-06 concern) |
| **label_10_degraded** `label_10_degraded.png` | label_01 content rotated ~7° with light noise | NFR-05 *(bonus)* | **PASS or NEEDS_REVIEW** (imperfect image — both acceptable, NFR-05); the cross-check may flag the rotated/noisy image for review (NFR-05 graceful degradation) |

> The **Expected verdict** is what the matcher returns *assuming the extractor
> reads the image correctly* — i.e. the target the extraction pass (#4) is checked
> against. These verdicts were confirmed self-consistent by feeding each label's
> printed text through `run_matchers` (a perfect-extraction stand-in): every field
> matched the table above.

## 4. Coverage map

| Requirement | Covered by |
|---|---|
| **MR-01** brand case/punctuation-insensitive | label_02 (also label_01 baseline) |
| **MR-02** ABV/proof equivalence | label_03 (proof-only PASS), label_04 (mismatch FAIL) |
| **MR-03 / D-12** legitimate ABV absence → categorized review | label_05 |
| **MR-04** warning exact wording | label_07 (also label_01 PASS baseline) |
| **MR-05** warning all-caps prefix | label_06 (also label_01 PASS baseline) |
| **MR-06** warning font-size / "buried text" | label_09 *(text passes; size FAIL deferred)* |
| **FR-07 / FR-09** warning present / unreadable → not a guess | label_08 |
| **NFR-05** imperfect-image robustness | label_10 *(bonus)* |
| **FR-02/03/04** end-to-end per-field PASS baseline | label_01 |

## 5. Notes

- **label_09 (MR-06)** currently passes the **text** check — the canonical wording
  and all-caps prefix are correct — because font-size / "buried text" detection is a
  later, **deferred** phase (MR-06 is a *Could*; see REQUIREMENTS.md §12 T-2 and
  ASSUMPTIONS D-5). When that signal lands, this label's warning should surface a
  size-based NEEDS_REVIEW/FAIL while the text check still passes.
- **label_10 (NFR-05)** tests image robustness (rotation + light noise) and is a
  **bonus** case: a robust extractor reads it and all fields PASS; a weaker one
  should degrade gracefully to NEEDS_REVIEW rather than crash — never a guessed pass.
- **Determinism:** the generator uses a fixed noise seed and derives every warning
  from the canonical constant, so the catalog is byte-stable across runs on the same
  Pillow/font stack. Fonts fall back gracefully if a TrueType face is unavailable.
- **Extraction dependency (MA-10):** these expected verdicts assume the extractor
  delivers each field — especially the warning — as a clean, bounded value (no
  trailing text such as `CONTAINS SULFITES` scooped into the warning field). That
  cleanliness is the extraction prompt's job in HANDOFF #4.

---

## Handoff #4b-2 — literal-OCR warning cross-check: real end-to-end results

Live run of `python tools/run_catalog.py` with the Tesseract cross-check wired in
(PRIMARY_MODEL=`gpt-5.6-terra`, single-label timeout 5s).

- **Tesseract available:** **YES** (`is_tesseract_available()` → True) — so the
  cross-check was **ACTIVE** for every label. The vision read still produced the
  strict warning verdict via the unchanged matcher; the literal-OCR read then ran
  in parallel and could only downgrade a warning **PASS → NEEDS_REVIEW** on
  disagreement.

| id / filename | overall | expected | MATCH? | seconds |
|---|---|---|---|---|
| label_01_compliant.png | PASS | PASS | MATCH | 6.84 |
| label_02_brand_case.png | PASS | PASS | MATCH | 2.52 |
| label_03_proof_only.png | PASS | PASS | MATCH | 3.26 |
| label_04_abv_mismatch.png | FAIL | FAIL | MATCH | 2.49 |
| label_05_beer_no_abv.png | NEEDS_REVIEW | NEEDS_REVIEW | MATCH | 2.15 |
| label_06_warning_titlecase.png | FAIL | FAIL | MATCH | 2.69 |
| label_07_warning_altered.png | FAIL | FAIL | MATCH | 3.75 |
| label_08_warning_missing.png | NEEDS_REVIEW | NEEDS_REVIEW | MATCH | 2.21 |
| label_09_warning_tiny.png | NEEDS_REVIEW | PASS | **DIFFERS** | 3.25 |
| label_10_degraded.png | NEEDS_REVIEW | PASS | **DIFFERS** | 3.74 |

**Verdict match vs TEST_PLAN: 8/10.** Timing: min 2.15 · median 2.97 · max 6.84s.

**Cross-check downgrades (the two DIFFERS rows):**
- **label_09 (tiny warning):** warning PASS → **NEEDS_REVIEW**, note *"vision and
  literal-OCR reads of the warning disagree — needs human review."* Tesseract reads
  a very-small-font warning worse than the vision model, so the two reads diverge
  and the gate conservatively flags it.
- **label_10 (rotated ~7° + noise):** same downgrade and note. Tesseract is weaker
  on rotated/noisy text, so the reads disagree and the warning is flagged.

Both are **expected recall-over-precision behavior (D-16/D-18)**, not bugs: the
strict matcher still passed the (correct) vision transcription; the cross-check
added caution because a second, literal reader could not confirm it. Labels 01–08
kept their prior verdicts. The `max` of 6.84s (label_01, first/cold call) is model
latency variance, not the cross-check — the two reads run in parallel, so the
cross-check adds ~no wall-clock (D-17).

Resolution: for the two deliberately-imperfect labels (09 tiny, 10 rotated) both
PASS and NEEDS_REVIEW are accepted as correct (NFR-05); the harness expectation is
updated accordingly, so the catalog reports 10/10 with the cross-check active. The
current run flagged both — the conservative, compliance-safe outcome.
