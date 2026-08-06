OBJECTIVE
Three focused improvements to the batch experience: (1) clicking a bucket opens a DEDICATED FULL-PAGE view
with its own URL and a working browser Back button (instead of swapping inline on the same screen);
(2) regenerate the 300 demo labels with SHARPER, more label-like typography; (3) make ~5 of them deliberately
MULTI-FLAG (wrong on TWO fields) so the built-in demo showcases the multi-flag workflow without needing an
upload. The matching/verdict core and the graded catalog are UNTOUCHED — this only touches the batch UI and
the demo generator. Verified offline; no live 300-run required.

TARGET REPO (CONFIRMED): C:\Users\finan\Documents\ttb-label-verify\   (NOT "shaphal".)

BEFORE YOU START — READ THESE
- app\static\batch.js         (the overview + inline review/list screens; how a bucket currently opens inline)
- app\templates\batch.html    (the results/overview + review + list markup)
- app\static\style.css         (#11 design system + batch styles)
- app\main.py                 (how /batch is served — for any route needed by page-style URLs)
- tools\generate_demo_labels.py (the Pillow generator: fonts, layout, the exception distribution)
- sample_data\demo_applications.csv (current 300 rows; header/schema to preserve)
- tools\generate_test_labels.py (the GRADED catalog generator — DO NOT touch; only for reference on font loading)
- BATCH_TRIAGE_DESIGN.md        (banner/model to update)

CHANGES

PART 1 — Clicking a bucket opens its own PAGE (not inline)
  - Requirement: from the bucket OVERVIEW, clicking a field-error bucket opens a DEDICATED full-page REVIEW view
    (banner/photo/application value/why-flagged/Approve/Reject/advance); clicking a record bucket (Approved/Cleared
    or Rejected) opens a DEDICATED full-page searchable LIST view. The overview and each opened bucket are DISTINCT
    pages: each has its own URL, and the browser BACK button (and forward) moves between them correctly, returning
    to the overview.
  - Implement with client-side history routing (the batch results live in client memory, streamed via SSE), using
    the History API (pushState/popstate). Choose the cleanest of:
       * hash-based URLs (e.g. /batch#bucket/brand) — no server change, refresh serves /batch, OR
       * path-based URLs (e.g. /batch/bucket/brand) — add a minimal catch-all in main.py so /batch/* serves the
         batch page.
    Either is fine; the hard requirement is: distinct URL per view + working Back/Forward. A HARD REFRESH resetting
    the session (results gone) is acceptable and expected (the app is session-only) — on refresh, show the overview
    (empty state) cleanly, do NOT error.
  - Preserve all existing behavior inside the views (the #12 review flow, #13a search, #13b re-ingest/notification,
    the #14 photo rendering). This changes HOW a bucket opens (as a page), not what's inside it. The notification
    "Navigate" must still land the agent on the right bucket's page positioned on the app.
  - Keep NFR-03: large targets, obvious Back control on each page in addition to the browser button.

PART 2 — Sharper label typography (tools\generate_demo_labels.py) + regenerate
  - Improve the rendered labels to look cleaner and more like real labels: a clear hierarchy (brand large and
    BOLD near the top, class/type and the other lines in a readable size, the warning block smaller at the bottom),
    comfortable margins/spacing, and crisp fonts. Use TrueType fonts that are AVAILABLE OFFLINE (e.g. DejaVuSans /
    DejaVuSans-Bold / DejaVuSerif, which ship with Pillow/matplotlib) — NO network font downloads. If you add a
    font file, commit it under a fonts\ dir; otherwise use the bundled DejaVu family. Keep the graceful fallback to
    the PIL default so it never crashes.
  - Keep the generator DETERMINISTIC (fixed seed) and IDEMPOTENT (re-running overwrites cleanly). Keep the SAME
    filenames and the SAME CSV schema/header so nothing downstream breaks.
  - Regenerate all demo labels into demo_labels\ and rewrite sample_data\demo_applications.csv in lockstep.

PART 3 — ~5 deliberate MULTI-FLAG demo labels (within the 300)
  - Adjust the distribution so ~5 items are MULTI-FLAG: the application data disagrees with the printed label on
    EXACTLY TWO fields (everything else matches), so each lands in TWO field-error buckets. Use a mix of combos,
    e.g. brand + alcohol_content, brand + warning-prefix, alcohol_content + net_contents. Keep the TOTAL at 300 by
    reducing the fully-compliant count from ~200 to ~195 (so: ~195 compliant + ~100 existing single-flag exceptions
    + ~5 new multi-flag = 300). Do not change the other exception categories.
  - Make these ~5 easy to find for testing: give them recognizable brand names, and have the generator PRINT their
    filenames + the two fields each breaks at the end of its run (so we can point the user straight to them).

PART 4 — BATCH_TRIAGE_DESIGN.md
  - Update the banner/model note: buckets now open as dedicated pages (own URL, Back works); the demo includes a
    few deliberate multi-flag labels. Keep it concise; change nothing unrelated.

DO NOT TOUCH
- The matching/verdict core: app\matching\*, app\models.py, app\fields.py, app\triage.py, app\matching\canonical.py — UNCHANGED.
- app\verify.py, app\extraction\* — UNCHANGED.
- The GRADED catalog: test_labels\*, sample_data\test_labels.csv, TEST_PLAN.md, tools\generate_test_labels.py — UNCHANGED.
- The single-label page (index.html, app.js) and the top nav — UNCHANGED this pass (single-label removal + Dashboard/History
  are the NEXT handoff, #16). Do NOT remove the single-label page here.
- REQUIREMENTS.md, ARCHITECTURE.md, PROJECT_HANDOFF.md — UNCHANGED this pass.
- No git add/commit/push. No .env / API-key access. No Docker/deploy. Do NOT run the live 300-model batch — verify offline.

ACCEPTANCE TEST
1. pip install -r requirements.txt
2. python tools/generate_demo_labels.py -> regenerates ~300 PNGs + rewrites sample_data\demo_applications.csv.
   Report the PNG count, the CSV row count (should be 300), and the printed list of the ~5 MULTI-FLAG filenames + the
   two fields each breaks.
3. Spot-check 3 regenerated images by eye: one compliant, one single-flag, one multi-flag — each legible, sharper
   typography than before, and consistent with its CSV row.
4. pytest -q -> the existing suite still passes (the demo-count tests should still see 300). Report the summary.
5. Boot: GET /batch -> 200; GET / -> 200.
6. DOM walkthrough (OFFLINE — fabricated stream over real regenerated images) confirming PART 1:
     - from the overview, clicking a field bucket navigates to a DEDICATED review PAGE (its own URL); the browser
       BACK button returns to the overview; forward re-enters;
     - clicking a record bucket opens a dedicated searchable LIST page; Back returns to the overview;
     - the review flow, search, re-ingest, and the notification "Navigate" still work and land on the correct page;
     - a hard refresh shows the overview empty state without erroring.
7. Scope: git status shows only batch.js, batch.html, style.css, (optional main.py for routing),
   tools\generate_demo_labels.py, demo_labels\*, sample_data\demo_applications.csv, and BATCH_TRIAGE_DESIGN.md.
   The matcher core, triage.py, verify.py, extraction, the graded catalog, the single-label page, and the top nav
   are unchanged.
8. Report back to the Testing Manager: the generated counts + the multi-flag filenames/fields, the pytest summary,
   a step-by-step of the bucket-as-page walkthrough (with Back/Forward behavior), a note on the sharper labels, scope
   confirmation, and that nothing was committed/pushed and no live 300-run occurred.
