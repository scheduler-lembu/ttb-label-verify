OBJECTIVE
Generate a ~300-label demo corpus (30x the current 10) — deterministic synthetic
label images plus matching application data — and point the one-click demo batch at
it, so batch (and the coming exception-folder triage view) can be demonstrated at
realistic importer scale (200-300 labels). Generation is OFFLINE ONLY: Pillow + Python
stdlib, no AI, no network, no API calls. The graded 10-label catalog and the matching
core are NOT touched — this is a separate, larger demo set.

BEFORE YOU START — READ THESE (do not modify them yet)
- C:\Users\finan\Documents\shaphal\app\data_source.py       (the demo application source)
- C:\Users\finan\Documents\shaphal\app\batch.py             (build_demo_items pairs demo DB to images)
- C:\Users\finan\Documents\shaphal\app\matching\canonical.py (CANONICAL_GOVERNMENT_WARNING)
- C:\Users\finan\Documents\shaphal\tools\generate_test_labels.py (the catalog generator — mirror its font-loading + render style; DO NOT edit it)
- C:\Users\finan\Documents\shaphal\sample_data\test_labels.csv (match this column header exactly)
- C:\Users\finan\Documents\shaphal\tests\test_data_source.py and tests\test_batch.py (find the hardcoded "10" counts you'll update)
- C:\Users\finan\Documents\shaphal\app\config.py + .env.example (find MAX_BATCH_ITEMS)

FILES TO CREATE / EDIT
CREATE:  C:\Users\finan\Documents\shaphal\tools\generate_demo_labels.py
CREATE:  C:\Users\finan\Documents\shaphal\demo_labels\  (output: demo_0001.png ... ~demo_0300.png)
CREATE:  C:\Users\finan\Documents\shaphal\sample_data\demo_applications.csv  (written BY the generator)
EDIT:    C:\Users\finan\Documents\shaphal\app\data_source.py   (point the demo source at the 300-set)
EDIT:    C:\Users\finan\Documents\shaphal\app\batch.py         (build_demo_items uses the 300-set)
EDIT:    C:\Users\finan\Documents\shaphal\tests\test_data_source.py  (update count assertions)
EDIT:    C:\Users\finan\Documents\shaphal\tests\test_batch.py        (update demo-count assertions)
EDIT (only if needed): C:\Users\finan\Documents\shaphal\app\config.py and .env.example
         — ensure MAX_BATCH_ITEMS does not truncate the built-in ~300 demo (see CHANGES E)

CHANGES

A) tools\generate_demo_labels.py — the generator (Pillow + stdlib only)
   - Seed Python's random with a FIXED constant so runs are reproducible/idempotent
     (re-running overwrites cleanly; same labels every time).
   - Import CANONICAL_GOVERNMENT_WARNING from app.matching.canonical. Render compliant
     warnings from it VERBATIM. Derive broken variants FROM it (never retype):
       * title-case prefix: .replace("GOVERNMENT WARNING", "Government Warning", 1)
       * altered wording: swap exactly one word (e.g. "birth defects" -> "birth defect")
   - Font: try DejaVuSans.ttf / arial.ttf; fall back to PIL default without crashing
     (mirror generate_test_labels.py).
   - Variety pools (internally consistent between image and CSV row): ~25 brand names,
     beverage class/type strings (bourbon, rye, gin, vodka, rum, tequila, IPA, lager,
     cabernet, chardonnay, etc.), producer names + addresses, net contents (750 mL,
     355 mL, 1 L, 500 mL, 1.75 L), ABV values, countries (mostly domestic; some imports).
   - Layout per label: brand large near top, then class/type, ABV/proof line, net
     contents, producer + address, country of origin (imports only), then the government
     warning block near the bottom. Plain white background, black text, legible.
   - Emit BOTH outputs together per label so image and app-data stay in lockstep: write
     the PNG to demo_labels\ AND append the matching row to sample_data\demo_applications.csv.
   - TARGET DISTRIBUTION out of ~300 (keep close; the goal is realistic-mostly-clean with
     EVERY exception type represented so every future folder has contents):
       200  fully compliant (label == app-data, exact canonical warning)  -> PASS
        20  brand differs ONLY in case/punctuation (label vs app-data)     -> PASS (MR-01)
        15  brand genuinely different OR accented/non-ASCII                -> FAIL / NEEDS_REVIEW
        15  ABV printed differs from app-data (e.g. 40% vs 45%)            -> FAIL (abv mismatch)
        10  proof-only on label (90 Proof) vs app-data 45%                -> PASS (equivalence)
        10  beer, NO ABV printed, app-data ABV blank                      -> NEEDS_REVIEW (blank_expected)
        10  warning prefix in Title Case ("Government Warning:")          -> FAIL (warning_prefix_not_allcaps)
        10  warning wording altered by one word                           -> FAIL (warning_wording)
         5  warning missing entirely                                       -> NEEDS_REVIEW (unreadable)
         5  compliant content rotated ~7 deg + light noise (degraded)      -> PASS if read, else NEEDS_REVIEW
     For every "exception" item the twist is the DIFFERENCE between what's printed on the
     image and the app-data row — exactly one field off, everything else matching.

B) sample_data\demo_applications.csv (written by the generator)
   - Header = EXACTLY the same columns/order as sample_data\test_labels.csv (registry keys
     + image_filename; include beverage_type only if data_source.py already reads it).
   - One row per demo label = the APPLICATION data (what an agent entered). Compliant items:
     row matches the label. Exception items: row differs from the label in exactly the one
     twisted field. Leave the `warning` column BLANK (matcher compares to canonical, MA-8).
     Fill country_of_origin only for imports. image_filename = that PNG's filename.

C) app\data_source.py — point the demo application source at demo_applications.csv (the
   300-set) instead of the 10-row demo. Keep the existing interface/shape and the
   registry-driven loading unchanged; only the backing dataset grows. Pairing stays by
   image_filename.

D) app\batch.py — build_demo_items must pair the 300 demo applications to the on-disk
   demo_labels\ images (by image_filename), same logic as today, just the larger set.

E) MAX_BATCH_ITEMS — ensure the built-in one-click demo of ~300 is NOT truncated or
   rejected by the upload cap. Least-invasive fix: exempt the trusted bundled demo from
   the per-upload MAX_BATCH_ITEMS cap (keep the cap for user CSV uploads). If that's
   awkward, instead raise the MAX_BATCH_ITEMS default to >= 300 in config.py + .env.example.
   Report which you did.

F) Tests — update ONLY the demo-count assertions in test_data_source.py and test_batch.py
   that currently hardcode 10 (e.g. "prints 10 lines", "demo pairs 10", demo job returns 10).
   Prefer making them count-agnostic (assert the demo item count == number of rows in
   demo_applications.csv) over hardcoding the new number. All other tests unchanged.

DO NOT TOUCH
- The graded catalog: C:\Users\finan\Documents\shaphal\test_labels\*,
  sample_data\test_labels.csv, TEST_PLAN.md, tools\generate_test_labels.py — UNCHANGED.
- The matching core + engine: app\matching\*, app\models.py, app\fields.py, app\verify.py,
  app\quality_gate.py, app\extraction\*, app\cache.py (stub), app\main.py, app\templates\*,
  app\static\* — UNCHANGED (except MAX_BATCH_ITEMS per E if config touch is chosen).
- The canonical warning wording — never edit it; import and derive only.
- Docs: README.md, REQUIREMENTS.md, ASSUMPTIONS_AND_TRADEOFFS.md, ARCHITECTURE.md,
  BATCH_TRIAGE_DESIGN.md, PROJECT_HANDOFF.md — unchanged this pass (doc sync comes later).
- No AI, no network, no live model calls. No Docker, no deploy. Do NOT git add/commit/push.
  Do NOT touch or print .env / the API key. Generation and the updated tests are fully offline.

ACCEPTANCE TEST
1. pip install -r requirements.txt   (Pillow already present from the catalog work)
2. python tools/generate_demo_labels.py
   -> creates ~300 PNGs in demo_labels\ and writes sample_data\demo_applications.csv.
      Report the exact PNG count and CSV row count.
3. Spot-check 4 images by eye: one fully-compliant, one Title-Case-warning, one ABV-mismatch,
   one missing-warning — each legible and consistent with its CSV row's intent.
4. pytest -q  -> all pass (existing suite + the updated demo-count tests). Paste the summary.
5. Offline demo build check (NO model call): confirm build_demo_items produces ~300 paired
   items, and TestClient GET /batch still returns 200.
6. Report back to the Testing Manager: the generated file count, the demo_applications.csv
   row count WITH the per-category breakdown (how many of each intended verdict), which
   MAX_BATCH_ITEMS approach you took (E), the pytest summary, confirmation the graded catalog
   (test_labels\, TEST_PLAN.md, generate_test_labels.py) is untouched, and that nothing was
   committed or pushed. Do NOT run the live 300-label batch through the model — that's a cost
   step handled in the next handoff.
