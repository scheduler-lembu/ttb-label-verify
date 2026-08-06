OBJECTIVE
Complete the record system: add "Re-ingest" (AI re-evaluate) to the record-bucket rows and a backend
endpoint that re-runs ONE label through the AI fresh; the new result clears that application's prior
disposition and re-buckets it (clean -> Approved/Cleared; flagged -> the relevant field-error buckets).
Each re-ingest posts a NAVIGABLE NOTIFICATION to a header BELL, whose "Navigate" button walks the agent
to each bucket the fresh read currently places the app in (opening it for review), and finally to its
terminal record bucket (Approved/Cleared or Rejected) once it has settled. Re-ingest uses the accurate
single-label engine, one label per click. Builds directly on #13a. Verified OFFLINE (endpoint with a
mocked reader; the bell/Navigate flow with a stubbed response) — no live model calls in the build.

TARGET REPO (CONFIRMED): C:\Users\finan\Documents\ttb-label-verify\   (NOT "shaphal".)

BEFORE YOU START — READ THESE
- app\static\batch.js         (#12 review flow + #13a record buckets/list/search; the per-app state + records model)
- app\templates\batch.html    (header, records section, list screen, sprite symbols)
- app\static\style.css        (#11 design system + #12/#13a styles)
- app\main.py                 (POST /batch, the SSE item payload builder, the #12 image endpoint, triage import)
- app\batch.py                (job store + item accessors incl. #12 image_bytes_for; how each item holds image + expected)
- app\verify.py               (verify_label(image_bytes, expected) -> LabelResult — single-label path, reuse it)
- app\triage.py               (bucket_tags_for / is_clean — reuse; do NOT change)
- BATCH_TRIAGE_DESIGN.md       (status banner + model section to update)

FILES TO EDIT
EDIT: app\main.py             (ADD the reverify endpoint)
EDIT: app\batch.py            (ADD a safe accessor for an item's image bytes + expected values by filename)
EDIT: app\static\batch.js     (Re-ingest call + re-bucketing; notification model; bell; Navigate cycling)
EDIT: app\templates\batch.html (header BELL + notification panel; Re-ingest button in record rows; bell/nav sprite icons)
EDIT: app\static\style.css     (bell + unread badge, notification panel, Navigate button — #11 system)
EDIT: BATCH_TRIAGE_DESIGN.md   (status banner + model: re-ingest + navigable notification — feature complete)

CHANGES

PART 1 — Backend: the reverify endpoint (app\main.py + app\batch.py)
  - app\batch.py: add a safe accessor to fetch an item's IMAGE BYTES + EXPECTED VALUES from a job by exact
    image_filename (extend/mirror the #12 image_bytes_for lookup — exact match within the job's items; never
    build a path from the URL). Unknown job/filename -> None so the endpoint can 404.
  - app\main.py: ADD `POST /batch/{job_id}/reverify/{image_filename}`:
      * look up the item (image bytes + expected) via the accessor; unknown -> 404 (no crash);
      * run `verify_label(image_bytes, expected)` (the existing SINGLE-label path — accurate fresh read);
      * build the SAME JSON shape as an SSE item: { image_filename, fields, bucket_tags (triage.bucket_tags_for),
        clean (triage.is_clean) };
      * return it as JSON.
    This is a LIVE single-label model call (one label). Do NOT change verify.py, triage.py, or the extractor —
    reuse them. Cost guard is the account-level spend cap (per the owner's decision); no per-visitor limit.

PART 2 — Front-end: Re-ingest on record rows (app\static\batch.js + batch.html + style.css)
  - Add a "Re-ingest" button to each row in BOTH record buckets (Approved/Cleared and Rejected).
  - On click: DISABLE the button and show a brief "re-checking…" state on that row (prevents double-fire),
    then POST to `/batch/{job_id}/reverify/{image_filename}`.
  - On response, apply the FRESH result to that application:
      * clear its PRIOR disposition (remove it from its current record bucket; drop its approvedFields and any
        rejectionInfo — it is being evaluated fresh);
      * update its stored fields / bucket_tags / clean / searchText from the response;
      * RE-BUCKET it: if clean -> Approved/Cleared (badged "Auto-cleared"); else -> the field-error buckets named
        by its new bucket_tags (awaiting approve/reject, exactly like a first ingest);
      * update all counts/tallies;
      * POST a NOTIFICATION (PART 3).
  - On endpoint error: re-enable the button and show a small inline "couldn't re-check — try again" (no crash).

PART 3 — The navigable notification bell (batch.js + batch.html + style.css)
  - A BELL in the page header with a count of notifications. Clicking the bell opens a NOTIFICATION PANEL
    listing notifications newest-first.
  - Each notification is tied to ONE application (image_filename) and shows a COMPACT outcome (must handle the
    multi-field case without a wall of text), e.g.:
      clean      -> "{brand} — re-checked: cleared."
      one field  -> "{brand} — re-checked: needs review on {field label}."
      N fields   -> "{brand} — re-checked: needs review on {N} fields."
  - Each notification has a "Navigate" button. NAVIGATE CYCLING (compute CURRENT membership on each click, so it
    stays correct as the agent works the app):
      * determine the field-error buckets the app is CURRENTLY in (its unresolved flagged fields — not approved,
        not rejected);
      * go to the NEXT such bucket not yet visited in this notification's cycle, OPEN that bucket's review screen
        positioned ON THIS application (bring it up for evaluation), and mark that bucket visited;
      * when the app is in NO field-error bucket (fully approved -> Approved/Cleared, or rejected -> Rejected, or
        re-check came back clean), Navigate goes to that TERMINAL record bucket and shows/highlights the app's row;
      * if all current field buckets have been visited but the app is still pending in them, wrap to the first
        again (so repeated clicks keep cycling its live locations until it settles).
  - REVIEW-SCREEN SUPPORT: extend the existing "open a bucket for review" so it can start ON a specific
    application (needed by Navigate), in addition to the normal start-at-first behavior. Do not otherwise change
    the #12 review flow.
  - Everything stays SESSION-ONLY (in-memory); a reload clears notifications and all state.

PART 4 — BATCH_TRIAGE_DESIGN.md
  - Update the status banner + model description: the record buckets now support Re-ingest (a fresh single-label
    AI re-read that re-buckets the app) and a navigable notification bell whose Navigate button walks the agent
    through the app's current buckets until it settles in Approved/Cleared or Rejected. Note this completes the
    triage/record feature (deploy is next). Keep it concise.

DO NOT TOUCH
- The matching/verdict core: app\matching\*, app\models.py, app\fields.py, app\matching\canonical.py — UNCHANGED.
- app\triage.py and app\verify.py — UNCHANGED (the reverify endpoint CALLS them; it does not modify them).
- app\extraction\* — UNCHANGED (reverify reuses the existing single-label extractor).
- The single-label page + flow: index.html, app.js, GET /, POST /verify — UNCHANGED.
- The #12 field-error review flow and the #13a record buckets/search — preserved; you ADD re-ingest + the bell,
  and only extend "open review" to allow starting on a specific app.
- The graded catalog and the #7 demo generators/data — UNCHANGED.
- REQUIREMENTS.md, ARCHITECTURE.md, PROJECT_HANDOFF.md — UNCHANGED this pass.
- No git add/commit/push. No .env / API-key access or printing. No Docker/deploy. Do NOT run a live re-ingest
  against the model during the build — verify OFFLINE per the acceptance test (mock the reader / stub the fetch).

ACCEPTANCE TEST
1. pip install -r requirements.txt
2. pytest -q — the existing tests still pass, PLUS a reverify-endpoint test (OFFLINE — monkeypatch the single
   extractor to return a KNOWN ExtractionResult, so NO real model call): POST /batch/{job_id}/reverify/{a real
   demo filename} -> 200 with { fields, bucket_tags, clean } matching the mocked read; unknown job/filename -> 404.
   Report the pytest summary and the new test count.
3. Boot check: GET /batch -> 200; GET / -> 200.
4. DOM walkthrough (OFFLINE — stub the reverify fetch to return a fabricated fresh result; no model call). Set up:
   an app sitting in a record bucket; stub its reverify response to come back FLAGGED ON TWO fields (e.g. brand +
   alcohol_content). Confirm:
     - clicking "Re-ingest" disables the button, then the app LEAVES the record bucket and appears in BOTH the
       Brand and Alcohol content field buckets; a NOTIFICATION posts ("…needs review on 2 fields") and the bell
       count increments;
     - clicking the bell shows the notification with a Navigate button;
     - Navigate #1 opens the Brand bucket's review screen positioned ON THIS app; Navigate #2 opens the Alcohol
       content bucket ON THIS app;
     - after approving/rejecting so the app settles (e.g. reject it), Navigate lands on the TERMINAL bucket
       (Rejected), showing the app there;
     - a second scenario: stub a reverify that comes back CLEAN -> the app moves to Approved/Cleared ("Auto-cleared"),
       the notification reads "…cleared", and Navigate goes straight to Approved/Cleared;
     - reload clears notifications and all state (session-only).
5. Scope check: git status shows only main.py, batch.py, batch.js, batch.html, style.css, and the design doc
   changed; the matcher core, triage.py, verify.py, extraction, the single-label page, the catalog, and the demo
   data are unchanged.
6. Report back to the Testing Manager: pytest summary + new test count, the reverify-endpoint result, a
   step-by-step of the DOM walkthrough (Re-ingest -> re-bucket + notification; Navigate cycling through both
   buckets; landing on the terminal bucket; and the clean-re-check case), confirmation of scope, and that nothing
   was committed/pushed and no live model call occurred.
