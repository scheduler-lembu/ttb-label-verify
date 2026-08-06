OBJECTIVE
The last build pass before deploy. Add two SESSION-SCOPED pages and settle the final navigation:
(1) a DASHBOARD view with live session counts (ingested / cleared / approved / rejected / outstanding);
(2) a HISTORY (Archive) view — one searchable, re-ingestable list of every decided application (approved/
cleared + rejected), styled like the record buckets; (3) a final top nav — Pipeline · Dashboard · History —
with the batch/triage app as the HOME page; (4) REMOVE the single-label page from the screen while KEEPING its
code (reachable but unlinked). Everything is client-side over the state the app already tracks — NO database,
NO new backend logic, consistent with the "nothing stored" design. Verified offline.

TARGET REPO (CONFIRMED): C:\Users\finan\Documents\ttb-label-verify\   (NOT "shaphal".)

BEFORE YOU START — READ THESE
- app\static\batch.js         (the SPA + #15 hash routing; the client state: records.cleared/rejected,
                               approvedFields, field-error buckets, re-ingest, the search/list rendering)
- app\templates\batch.html    (the app shell, header/nav, the views)
- app\static\style.css         (#11 design system + batch styles)
- app\main.py                 (routes: GET / currently serves single-label; GET /batch serves the app; POST /verify; /single?)
- app\templates\index.html    (the single-label page — to be UNLINKED, not deleted)

CHANGES

PART 1 — Final navigation + make the app the home page
  - The batch/triage app (batch.html) becomes the SITE HOME: GET / serves the app. Keep GET /batch serving it too
    (or redirect / <-> /batch consistently). The app's client-side URLs (from #15) stay hash-based.
  - Top nav (in the app shell) becomes exactly: **Pipeline · Dashboard · History**, with the active item highlighted.
    "Pipeline" = the existing batch run + triage view (the current default). Remove the "Single label" nav link.
  - REMOVE single-label from the screen but KEEP its code: serve index.html at GET /single (unlinked), keep POST
    /verify working. Do NOT delete index.html or app.js. index.html's own header may keep a simple link back to the
    app (/), but it must not be reachable from the app's nav.

PART 2 — Dashboard view (session-scoped, client-side)
  - A new client-side view at #dashboard (routed like the #15 views). It computes its numbers from the CURRENT
    session state (the current batch run + the decisions made on it) — no persistence.
  - Show clear stat cards (large, obvious — NFR-03), labeled:
      * Ingested (this session)      = total applications in the current run (clean + flagged)
      * Cleared automatically        = clean items auto-passed on ingest
      * Approved by you              = applications you fully approved
      * Rejected                     = applications you rejected
      * Outstanding (in pipeline)    = applications still in field-error buckets awaiting a decision
    A simple visual (e.g. a proportion bar of cleared/approved/rejected/outstanding) is welcome but optional.
  - The numbers update to reflect the live state whenever the Dashboard is shown (recompute on view). Empty state
    before any batch has run: show zeros / "Run a batch to see today's numbers."
  - Session semantics: "this session / today" = the current run (the app is session-only). Do NOT try to persist or
    accumulate across reloads or across calendar days — that's the documented production step.

PART 3 — History / Archive view (session-scoped, client-side)
  - A new client-side view at #history. It lists EVERY decided application in the session — the union of
    Approved/Cleared and Rejected — using the SAME row style, SEARCH box, and RE-INGEST button as the record-bucket
    list (reuse that rendering). Each row shows the application's brand/filename, its status badge (Auto-cleared /
    Approved by you / Rejected-for…), and Re-ingest.
  - Provide simple filter chips: **All · Approved/Cleared · Rejected** (default All). The search filters by any field
    value (reuse the existing searchText). Re-ingest behaves exactly as in #13b (re-runs the label, re-buckets it,
    posts a notification); a re-ingested item leaving/entering the decided set updates History live.
  - Empty state: "No decided applications yet."
  - (Framing only — no persistence.) This view is the session's archive; in production it would hold decisions
    archived across days. Keep the label "History" / "Archive" but do NOT implement day-rollover or storage.

PART 4 — Routing + cache-bust
  - Extend the #15 hash router with #dashboard and #history (plus the existing overview, #bucket/*, #records/*),
    with Back/Forward working across all of them. Nav clicks route via the same mechanism.
  - Bump the static asset cache-bust token (e.g. ?v=16) on batch.html (and index.html if touched).

PART 5 — BATCH_TRIAGE_DESIGN.md
  - Update the banner/model note: the app now has Pipeline / Dashboard / History; single-label is unlinked (kept in
    code); Dashboard + History are session-scoped (production would persist/roll over by day). Keep it concise.

DO NOT TOUCH
- The matching/verdict core: app\matching\*, app\models.py, app\fields.py, app\triage.py, app\matching\canonical.py — UNCHANGED.
- app\verify.py, app\extraction\* — UNCHANGED. Do NOT add any database/persistence.
- The GRADED catalog and the demo generators/data (demo_labels\, demo_applications.csv, tools\*) — UNCHANGED.
- The existing batch behaviors (#12 review, #13a records/search, #13b re-ingest/notification, #14 photo/persistence,
  #15 bucket-as-page) — PRESERVE them; you are ADDING views + nav, not changing those flows.
- Do NOT delete index.html / app.js / POST /verify — the single-label page is kept in code, only unlinked.
- REQUIREMENTS.md, ARCHITECTURE.md, PROJECT_HANDOFF.md, README.md — UNCHANGED this pass (README rewrite is a later submission-prep step).
- No git add/commit/push. No .env / API-key access. No Docker/deploy. No live 300-model run — verify offline.

ACCEPTANCE TEST
1. pip install -r requirements.txt
2. pytest -q — the existing suite still passes unchanged (this pass adds no Python logic beyond routing). Report the summary.
3. Boot: GET / -> 200 (now serves the app); GET /batch -> 200; GET /single -> 200 (single-label kept); POST /verify still wired.
4. DOM walkthrough (OFFLINE — fabricated stream over the real demo images):
     - the top nav reads **Pipeline · Dashboard · History** with NO "Single label"; the app is served at /.
     - run the fabricated batch (a few clean + a few flagged, incl. a multi-flag). Go to **Dashboard**: confirm
       Ingested / Cleared automatically / Approved by you / Rejected / Outstanding show the correct numbers; approve
       and reject a couple in the Pipeline, return to Dashboard, and confirm the numbers UPDATED.
     - go to **History**: confirm it lists all decided applications (approved/cleared + rejected), the filter chips
       (All / Approved-Cleared / Rejected) work, the search filters by a field value, and a row's **Re-ingest** works
       (stub the reverify fetch — no model call) and posts a notification.
     - confirm Back/Forward and the nav route correctly across Pipeline / Dashboard / History and the bucket sub-pages.
     - confirm GET /single still serves the single-label page (reachable, just not in the nav).
5. Scope: git status shows only batch.js, batch.html, style.css, main.py (routing), index.html (unlink/cache-bust),
   and BATCH_TRIAGE_DESIGN.md. The matcher core, triage.py, verify.py, extraction, the graded catalog, and the demo
   data/generators are unchanged; no persistence/database was added.
6. Report back to the Testing Manager: the pytest summary, a step-by-step of the walkthrough (the Dashboard numbers
   before/after a couple of decisions, the History search/filter/re-ingest, the nav/routing, and /single still
   reachable), scope confirmation, and that nothing was committed/pushed and no live run occurred.
