# COWORK HANDOFF #3 — Test-Label Catalog + TEST_PLAN

## START HERE
Read these first, then this handoff:
- `C:\Users\finan\Documents\ttb-label-verify\REQUIREMENTS.md`  (§4 FR, §5 MR — the verdicts each label must prove)
- `C:\Users\finan\Documents\ttb-label-verify\app\matching\canonical.py`  (the exact warning text to render)
- `C:\Users\finan\Documents\ttb-label-verify\app\fields.py`  (the field keys the CSV columns must match)
- `C:\Users\finan\Documents\ttb-label-verify\sample_data\batch_template.csv`  (existing header)

---

## OBJECTIVE
Generate a **deterministic test-label catalog**: ~10 rendered label images (one
compliant, the rest each breaking exactly one rule), plus a `TEST_PLAN.md` mapping
each label to the requirement it proves and its expected per-field verdict, plus a
CSV of the matching application data. This is the known-input set the extraction pass
(#4) will be verified against. **No AI, no API key, no network** except installing
Pillow. **Do not build or call any extractor** — this pass only creates images + docs.

---

## APPROACH (locked)
- Use **Pillow (PIL)** to render each label as a PNG into `test_labels\`.
- **Render the compliant warning by importing `CANONICAL_GOVERNMENT_WARNING` from
  `app.matching.canonical`** — never retype it. Derive the broken warning variants
  from that constant (e.g. `.replace("GOVERNMENT WARNING", "Government Warning")`),
  so the compliant label is guaranteed to match the stored reference.
- Load a TrueType font if available (try `DejaVuSans.ttf` / `arial.ttf`); fall back to
  the PIL default gracefully so the script never crashes on a missing font.
- Labels should be legible: brand large near the top, then the other fields, then the
  warning block. Plain white background, black text is fine — these test content, not
  design.
- Keep the generator in `tools\generate_test_labels.py` (create the `tools\` folder).
  Running it must be idempotent (re-running overwrites cleanly).

---

## FILES TO CREATE
```
C:\Users\finan\Documents\ttb-label-verify\tools\generate_test_labels.py   # the Pillow generator (creates + runs)
C:\Users\finan\Documents\ttb-label-verify\test_labels\label_01..label_10 .png  # generated output (~10 PNGs)
C:\Users\finan\Documents\ttb-label-verify\sample_data\test_labels.csv     # one row per label: expected application data
C:\Users\finan\Documents\ttb-label-verify\TEST_PLAN.md                    # the catalog doc (see below)
```
Also: **add `Pillow` to `requirements.txt`** (append the line; keep the file otherwise unchanged).

---

## THE CATALOG (render exactly these ~10; label text on the image vs. the app-data in the CSV)
For each: the **label** column = what is printed on the rendered image; the **app data**
= the expected values that go in the CSV row (what an agent would enter). "Expected
verdict" = what the matcher should return *assuming the extractor reads the image
correctly* (this is what #4 will be checked against).

| id | product on the LABEL | the twist | app-data差 vs label | expected verdict (field) | proves |
|----|----|----|----|----|----|
| label_01_compliant | OLD TOM DISTILLERY · Kentucky Straight Bourbon Whiskey · 45% Alc./Vol. (90 Proof) · 750 mL · producer+addr · **exact canonical warning** | none — fully compliant | app data matches label | ALL **PASS** | baseline FR-02/03/04 |
| label_02_brand_case | brand printed **STONE'S THROW** · gin · 40% Alc./Vol. · 750 mL · warning | brand case/punct | app-data brand = "Stone's Throw" | brand **PASS** | MR-01 |
| label_03_proof_only | ABV printed as **"90 Proof"** only (no %) | proof-only strength | app-data ABV = "45%" | ABV **PASS** (equivalence) | MR-02 |
| label_04_abv_mismatch | ABV printed **40% Alc./Vol.** | wrong strength | app-data ABV = "45%" | ABV **FAIL** | MR-02 |
| label_05_beer_no_abv | a malt beverage, **no ABV printed** | legitimate omission | app-data ABV = blank | ABV **NEEDS_REVIEW** / `blank_expected` | MR-03 / D-12 |
| label_06_warning_titlecase | warning prefix printed **"Government Warning:"** (title case) | prefix case | app-data warning = blank (ignored) | warning **FAIL** / `warning_prefix_not_allcaps` | MR-05 |
| label_07_warning_altered | warning with **one word changed** (e.g. "birth defects"→"birth defect") | wording | — | warning **FAIL** / `warning_wording` | MR-04 |
| label_08_warning_missing | **no warning statement** on the label | omission | — | warning **NEEDS_REVIEW** / `unreadable` | FR-07/09 |
| label_09_warning_tiny | correct canonical warning but rendered in a **very small font** | buried/tiny text | — | warning **PASS** on text (MR-04/05); size FAIL is MR-06, **deferred** | MR-06 (deferred) |
| label_10_degraded | label_01 content, **rotated ~7° with light noise** | imperfect image | app data matches | ideally **PASS**; if unreadable → NEEDS_REVIEW | NFR-05 (bonus) |

(Exact brand/producer strings are your choice as long as they're internally consistent
between the image and the CSV. For label_02, the *label* must differ from the *app data*
only in case/punctuation.)

---

## `sample_data\test_labels.csv`
- Header row = the field-registry keys (same order as `batch_template.csv`):
  `image_filename,brand,alcohol_content,warning,class_type,net_contents,producer,country_of_origin`
- One row per label above, filled with the **application data** (not the label text) for
  that case. The `warning` column may be left blank (the matcher compares to the canonical
  constant, not this column — MA-8). `image_filename` = the PNG's filename.

---

## `TEST_PLAN.md` (the graded artifact + reviewer's guided tour)
Sections:
1. **Purpose** — one paragraph: this catalog is deliberately-constructed input that
   exercises every matching rule; it lets a reviewer confirm the app behaves correctly
   and shows which requirement each label proves.
2. **How to use it** — once the app is running (later phase), upload each label with the
   matching CSV row; the "expected verdict" column is what should appear.
3. **Catalog table** — reproduce the table above: id / filename / what it tests / the
   requirement ID / the expected per-field verdict (and reason code where relevant).
4. **Coverage map** — a short list showing each key requirement (MR-01, MR-02, MR-03/D-12,
   MR-04, MR-05, MR-06 deferred, FR-09, NFR-05) and which label(s) cover it.
5. **Notes** — label_09 (MR-06) currently passes the text check; the font-size/"buried"
   FAIL is a later, deferred phase. label_10 tests image robustness (bonus, NFR-05).

---

## DO NOT TOUCH
- `app/matching/*`, `app/models.py`, `app/fields.py`, `tests/*` — unchanged (the matcher
  is done; do not re-open it).
- `app/extraction/*`, `app/main.py`, `app/verify.py`, `app/batch.py`, `app/config.py`,
  UI files — still stubs; **do not build extraction or call any AI/API.**
- `README.md`, `ASSUMPTIONS_AND_TRADEOFFS.md`, `REQUIREMENTS.md`, `ARCHITECTURE.md`,
  `Working_Document_List.txt`, HANDOFF files — inputs; leave unchanged. (`TEST_PLAN.md`
  is new.)
- No network except `pip install Pillow`. No Docker, no deploy, no push.

---

## ACCEPTANCE TEST
1. `pip install -r requirements.txt` (now includes Pillow).
2. Run `python tools/generate_test_labels.py`.
3. `test_labels\` contains the ~10 PNGs; each opens and is legible as an alcohol label.
4. `sample_data\test_labels.csv` has a header + one row per label, keys matching the registry.
5. `TEST_PLAN.md` exists with all five sections and the catalog table.
6. Report back to the Testing Manager: the list of generated files (names + sizes), the
   `TEST_PLAN.md` catalog table, and confirmation the script ran without error. **Do not push.**
