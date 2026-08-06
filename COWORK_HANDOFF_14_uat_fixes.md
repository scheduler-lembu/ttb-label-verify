OBJECTIVE
Fix the bugs and polish the UAT surfaced, so testing can continue and the app is deploy-ready:
(A) CRITICAL — label photos are broken AND re-ingest fails on a DEMO run; both are almost certainly the
same root cause (the image + reverify endpoints can't resolve a demo-run job's items). Diagnose and fix so
all 300 demo label photos render and re-ingest works. (B) hide the empty pink error banner. (C) restyle the
native file-input buttons to the design system. (D) remove the "View full label details" expander. (E) add
cache-busting to static asset links. Do NOT change the inline-vs-new-page bucket behavior or the label fonts
this pass — those are the NEXT handoff.

TARGET REPO (CONFIRMED): C:\Users\finan\Documents\ttb-label-verify\   (NOT "shaphal".)

BEFORE YOU START — READ THESE
- app\main.py                 (POST /batch demo path + job store; GET /batch/{job_id}/image/{filename}; POST /batch/{job_id}/reverify/{filename})
- app\batch.py                (build_demo_items; the job/item store; item_for / image_bytes_for accessors; how DEMO items hold their image vs UPLOADED items)
- app\static\batch.js         (review-screen <img> src construction; the re-ingest fetch + its error handler; the "View full label details" expander)
- app\templates\batch.html    (the error/alert banner; the "Use your own" file inputs; static <script>/<link> tags)
- app\templates\index.html    (its static <script>/<link> tags — for cache-busting)
- app\static\style.css        (design system + current batch styles)

CHANGES

PART A — CRITICAL: fix demo photos + re-ingest (one root cause)
  1. REPRODUCE via the REAL flow (not a hand-built job): start the server, POST the demo batch the way the UI
     does (demo mode), capture the returned job_id, then:
       - GET /batch/{job_id}/image/{a demo filename e.g. demo_0001.png}  -> observe the failure (likely 404).
       - POST /batch/{job_id}/reverify/{that filename}                   -> observe the failure.
     Confirm the root cause. The likely issue: the demo job (built via the real POST /batch demo path) stores
     its items so that item_for / image_bytes_for CANNOT return the image bytes (and/or expected values) for a
     DEMO item — whereas #12's isolated test hand-built the job differently, so it never caught this. Also check
     that the demo_labels directory path resolves as an ABSOLUTE path from the running server's working
     directory (a relative "demo_labels/" can miss depending on CWD).
  2. FIX so BOTH endpoints resolve DEMO items:
       - GET .../image/{filename}: returns the demo label's bytes (read from demo_labels\ on disk by exact
         filename match within the job's items; keep the safe exact-match lookup — no path built from the URL).
       - POST .../reverify/{filename}: item_for returns the demo item's image bytes + expected values so
         verify_label can run.
     PRESERVE the UPLOADED-batch path (those items hold bytes in memory) — the accessor must handle both demo
     (disk) and uploaded (memory) items.
  3. Do NOT change verify.py, triage.py, the matcher, or the extractor — this is a lookup/wiring fix only.

PART B — Hide the empty error banner (the "pink box")
  - The batch error/alert region renders with its pink styling even when there is no message. Make it HIDDEN by
    default and only shown when it actually has an error/pairing message; hide it again when cleared.

PART C — Restyle the file inputs ("Choose File" / "Choose Files")
  - Replace the raw native file-input buttons with controls styled to the #11 design system (hide the native
    <input type=file>, trigger it from a styled label/button, and show the chosen filename / count next to it).
    Applies to both the "Expected-values CSV" and "Label images" inputs in the "Use your own" card. Keep them
    fully functional (selecting files still works and submits the same way).

PART D — Remove "View full label details"
  - Remove the "View full label details" expander (control + panel) from the review screen, in both batch.html
    and batch.js. Nothing else in the review screen changes.

PART E — Cache-busting on static assets
  - Append a version query string to the static asset links (CSS/JS) in batch.html AND index.html (e.g.
    href="/static/style.css?v=14", src="/static/batch.js?v=14", etc.). Use a single version token bumped this
    pass. This forces browsers to load fresh files after changes (fixes stale-asset caching during re-test and
    after deploy).

DO NOT TOUCH (this pass)
- The bucket interaction model: do NOT change clicking-a-bucket from inline to a new page (that is the NEXT handoff).
- The label fonts / the demo corpus: do NOT regenerate demo_labels\ or edit tools\generate_demo_labels.py (NEXT handoff).
- The matching/verdict core: app\matching\*, app\models.py, app\fields.py, app\matching\canonical.py — UNCHANGED.
- app\triage.py, app\verify.py, app\extraction\* — UNCHANGED (PART A is a lookup/wiring fix; it CALLS verify_label).
- The single-label FLOW (index.html only gets the cache-bust version bump; no logic change); app.js — UNCHANGED.
- The graded catalog and demo generators/data — UNCHANGED.
- REQUIREMENTS.md, ARCHITECTURE.md, BATCH_TRIAGE_DESIGN.md, PROJECT_HANDOFF.md — UNCHANGED this pass.
- No git add/commit/push. No .env / API-key printing. No Docker/deploy.

ACCEPTANCE TEST
1. pip install -r requirements.txt
2. pytest -q — existing tests still pass, PLUS new tests that use the REAL demo job path (create the demo job
   the way POST /batch demo does, get its job_id), asserting:
     - GET /batch/{job_id}/image/{a demo filename} -> 200 image/png with real bytes (was failing);
     - POST /batch/{job_id}/reverify/{a demo filename} with the single extractor MONKEYPATCHED (no live model) ->
       200 with { fields, bucket_tags, clean } (was failing);
     - an unknown filename still -> 404.
   Report the pytest summary + new test count.
3. Boot: GET /batch -> 200; GET / -> 200.
4. Live visual confirm (start the server): run the demo, open a field bucket, and confirm the SUBMITTED LABEL
   PHOTO now RENDERS (real image, not the broken-image alt text). You may confirm re-ingest end-to-end with ONE
   real click on a single demo record (one label, pennies) OR rely on the mocked endpoint test in step 2 to
   prove the lookup — state which you did.
5. UI confirm: the pink error banner is GONE when there's no error; the file inputs are restyled to the design
   system and still select/submit files; "View full label details" is removed; the static links carry the ?v=
   version.
6. Scope: git status shows only main.py/batch.py (PART A), batch.js, batch.html, index.html, style.css (and any
   new test file). The matcher core, triage.py, verify.py, extraction, the single-label logic, the catalog, and
   the demo generators/data are unchanged; bucket-open is still inline (unchanged) and fonts are untouched.
7. Report back to the Testing Manager: the root cause you found for PART A and the fix, the pytest summary + new
   test count, the demo-photo/re-ingest confirmation (and which method for re-ingest), the UI confirmations, and
   that nothing was committed/pushed.
