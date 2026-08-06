OBJECTIVE
Add the two "record" buckets that hold decided applications: a COMBINED "Approved / Cleared"
bucket and a "Rejected" bucket. Auto-cleared applications now land IN the Approved/Cleared bucket
(instead of only a hidden tally); approving an application (all its flagged fields) moves it there
too; rejecting moves it to the Rejected bucket. Each record bucket opens to a SEARCHABLE LIST (not
the one-at-a-time review screen), filtered by any field value. This is the structural foundation
that #13b's "Re-ingest" + notification bell will build on. FRONT-END ONLY: no backend, no AI, no
model calls. The #12 field-error review flow (approve-per-field / reject-whole-app / rollup) is
UNCHANGED — this only adds where decided applications go and how you find them. Verified offline.

TARGET REPO (CONFIRMED): C:\Users\finan\Documents\ttb-label-verify\   (NOT "shaphal".)

BEFORE YOU START — READ THESE (build precisely on #12)
- app\static\batch.js         (the #12 triage client: bucket cards, review screen, approve/reject,
                               the "cleared automatically" tally, the "All caught up" completion,
                               and the per-app state incl. the reject rollup / rejectionInfo)
- app\templates\batch.html    (the results-area markup: bucket container + review screen)
- app\static\style.css        (the #11 design system + #12 bucket/review styles)
- app\models.py               (FieldResult fields — for the row display + search source)
- BATCH_TRIAGE_DESIGN.md       (status banner + model section to update)

FILES TO EDIT (front-end + one doc)
EDIT: app\static\batch.js        (status buckets, routing decided apps into them, searchable list view)
EDIT: app\templates\batch.html   (status-bucket containers + the list/search markup)
EDIT: app\static\style.css       (status-bucket cards, list rows, status badges, search box — #11 system)
EDIT: BATCH_TRIAGE_DESIGN.md      (status banner + model description — see PART 5)

CHANGES

PART 1 — Two record buckets, always present alongside the field-error buckets
  - "Approved / Cleared" (ONE combined bucket) and "Rejected" (one bucket). Render them as their own
    cards with a name, icon, and live count — visually consistent with the field-error bucket cards,
    but placed as a SECONDARY "record" row/section BENEATH the field-error ("needs attention") buckets,
    so the primary focus stays on what needs review (NFR-03: uncluttered, obvious).
  - Each application is identified by its image_filename (as in #12).

PART 2 — Route applications into the record buckets
  - AUTO-CLEARED on ingest: a clean item (clean == true) now goes INTO the Approved/Cleared bucket as a
    row tagged "Auto-cleared" — instead of only incrementing a hidden tally. (The summary bar may still
    show a cleared count, but the bucket is now openable and lists these apps.)
  - APPROVED by the agent: when an application has ALL its flagged fields approved (the existing #12
    per-field approve that fully clears it), move it into the Approved/Cleared bucket as a row tagged
    "Approved by you". (Do NOT change the per-field approve mechanics themselves.)
  - REJECTED by the agent: when rejected (existing #12 whole-app reject), move it into the Rejected
    bucket, carrying its existing "Rejected for / Please check" record (reuse #12's rejectionInfo).
  - Keep the #12 field-error review flow exactly as-is (banner, photo, approve-per-field, reject-whole-app,
    advance, "This bucket is clear", "All caught up"). The records simply persist in the status buckets;
    "All caught up" still fires when the field-error buckets are empty.

PART 3 — Searchable LIST view for the record buckets (NOT the review screen)
  - Clicking the Approved/Cleared or Rejected bucket opens a LIST (not the one-at-a-time review screen):
      * one row per application, showing its brand (fall back to image_filename if no brand) and a status
        badge — "Auto-cleared" / "Approved by you" for the combined bucket; for Rejected, show the
        "Rejected for: {field}" and the "Please check: {list}" record.
      * a SEARCH box at the top that filters the list live (client-side, instant) — case-insensitive
        substring match against ANY of that application's field values (each field's extracted AND
        expected, from the item's `fields`) plus its brand/filename. Empty query shows all.
      * a way back to the bucket overview.
  - NO approve/reject buttons in the record buckets. (Re-ingest is added in #13b — do NOT add it now;
    do not add a dead/disabled button.)

PART 4 — Ordering
  - Within each record bucket, list most-recently-touched first (auto-cleared on ingest order is fine;
    an app that was just approved/rejected should appear at/near the top). Track a simple per-app
    "last touched" marker client-side for ordering. (This sets up #13b's "most recent action" view.)

PART 5 — BATCH_TRIAGE_DESIGN.md
  - Update the status banner and the model description to reflect THREE bucket types: field-error buckets
    (per field, Approve/Reject review), a combined Approved/Cleared record bucket (auto-cleared + agent-
    approved, searchable), and a Rejected record bucket (searchable, carries the reject rollup). Note that
    Re-ingest + the navigable notification are the next step (#13b). Keep it concise; don't rewrite
    unrelated sections.

DO NOT TOUCH
- The matching/verdict core: app\matching\*, app\models.py, app\fields.py, app\matching\canonical.py — UNCHANGED.
- app\triage.py — UNCHANGED (field-error bucketing is done; status buckets are a client-side concept).
- app\verify.py, app\extraction\* — UNCHANGED (no re-ingest/AI this pass — that's #13b).
- app\main.py, app\batch.py — UNCHANGED this pass (no new endpoint; #13a is front-end only).
- The single-label page + flow: index.html, app.js, GET /, POST /verify — UNCHANGED.
- The graded catalog and the #7 demo generators/data — UNCHANGED.
- REQUIREMENTS.md, ARCHITECTURE.md, PROJECT_HANDOFF.md — UNCHANGED this pass.
- Do NOT add the Re-ingest button, the reverify endpoint, or the notification bell (all #13b).
- No git add/commit/push. No .env / API-key access. No Docker/deploy. No live model run — verify OFFLINE.

ACCEPTANCE TEST
1. pip install -r requirements.txt
2. pytest -q — the existing tests (91) still pass unchanged (this pass adds no Python logic). Report the summary.
3. Boot check: GET /batch -> 200; GET / -> 200.
4. DOM walkthrough (OFFLINE — path a, fabricated stream, no model call): create a real demo job (so any
   photos resolve) and inject fabricated items referencing real filenames — at least one CLEAN label, one
   single-flag label, and one multi-flag label. Via the rendered DOM confirm:
     - the Approved/Cleared bucket card appears with the CLEAN app inside it, its row badged "Auto-cleared"
       (the clean app is now IN the bucket, not just a tally);
     - the field-error buckets still work exactly as in #12 (open, review screen, approve/reject);
     - APPROVING an application until all its flagged fields are cleared moves it into Approved/Cleared,
       badged "Approved by you";
     - REJECTING an application moves it into the Rejected bucket, showing its "Rejected for / Please check"
       record;
     - opening a record bucket shows a LIST (not the review screen); typing in the SEARCH box filters the
       list by a field value (e.g. a brand or an ABV) and clearing it restores the full list;
     - the record buckets have NO approve/reject (and no re-ingest button yet);
     - reload clears everything (session-only).
5. Scope check: git status shows only batch.js, batch.html, style.css, and the BATCH_TRIAGE_DESIGN doc
   changed; the core, triage.py, main.py, batch.py, verify.py, extraction, the single-label page, the
   catalog, and the demo data are untouched.
6. Report back to the Testing Manager: the pytest summary, a step-by-step of the DOM walkthrough (clean-in-
   Approved/Cleared, approve->Approved/Cleared, reject->Rejected with rollup, and search filtering),
   confirmation of scope, and that nothing was committed/pushed and no live run occurred.
