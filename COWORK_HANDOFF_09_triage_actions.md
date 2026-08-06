OBJECTIVE
Turn the read-only exception-folder triage view into the actual triage WORKFLOW: add three
per-label actions — Approve, Reject, and "Tool was wrong" — with the row clearing on-screen
the instant the agent acts, running tallies, and an "all caught up" closing state. Disposition
is LABEL-LEVEL and SESSION-ONLY (no persistence — D-8/CON-02). This realizes FR-12 (human
override). FRONT-END ONLY: no backend, no new Python logic, no model calls. Verified offline
via the same fabricated-batch DOM method used in #8.

TARGET REPO (CONFIRMED): C:\Users\finan\Documents\ttb-label-verify\
  NOTE: NOT "shaphal" (an unrelated project). All paths below are under ttb-label-verify.

BEFORE YOU START — READ THESE (understand what #8 built; don't rewrite it)
- app\static\batch.js         (the triage client: folder bucketing, live counts, drill-down, detail panel)
- app\templates\batch.html    (the triage surface: summary bar, folders container, detail panel)
- app\static\style.css        (triage styling appended in #8)
- BATCH_TRIAGE_DESIGN.md       (the workflow: approve/reject/note, clear on-screen, a label in multiple
                                folders, the single-label view retained as the detail panel)

FILES TO EDIT (front-end + one doc line only)
EDIT: app\static\batch.js        (resolution state + the three actions + clearing + tallies + advance-to-next)
EDIT: app\templates\batch.html   (the three action buttons on folder rows AND in the detail panel;
                                  resolved-tally UI; "all caught up" state; optional undo/note)
EDIT: app\static\style.css       (button styling — large, obvious, color-coded; NFR-03)
EDIT: BATCH_TRIAGE_DESIGN.md      (status banner ONLY — see change F)

CHANGES

A) Resolution model (batch.js — client-side, in-memory)
   - Keep a client-side map: labelId -> disposition ('approved' | 'rejected' | 'tool_error' | none).
     In MEMORY only. No network, no localStorage, no persistence. Reloading the page clears it.
   - Disposition is LABEL-LEVEL: resolving a label removes it from EVERY folder it is tagged in
     (a label is one application with one disposition). The DETAIL PANEL shows ALL of that label's
     flaws so the agent decides with the full picture.
   - Three actions:
       Approve       -> agent overrides the flag and passes the label (FR-12 override).
       Reject        -> agent confirms the problem; the label fails / goes back.
       Tool was wrong-> records a tool mis-flag; optional short typed note. (On-screen only.)
     All three RESOLVE the label and clear it from the folders.

B) Where the actions live
   - Inline on each FOLDER ROW: three clear buttons (Approve / Reject / Tool was wrong) for the fast
     rip-through described in the design ("click through fast... move to the next").
   - In the DETAIL PANEL: the same three actions, plus an OPTIONAL short note field on "Tool was wrong".
     After acting in the detail panel, AUTO-ADVANCE to the next unresolved item in the SAME folder; if
     none remain, return to the folder list.
   - Acting in EITHER place updates all counts and clears the label from every folder it appeared in.

C) Tallies + closure
   - Update the summary bar live: the "need your attention" count DECREASES as items resolve. ADD a
     reviewed tally: "reviewed by you: A approved · R rejected · T tool errors".
   - When a folder's last item is resolved, show "All clear" for that folder (or hide it).
   - When EVERY folder is empty, show an "All caught up" completion state summarizing the dispositions.
   - OPTIONAL (nice-to-have, not required for acceptance): an "Undo last" control that reverses ONLY the
     most recent disposition (forgiving for a mis-click). Keep it to the last action; skip if it adds risk.

D) UX (NFR-03 — the 73-year-old bar)
   - Big, obvious, color-coded buttons: Approve = green, Reject = red, Tool was wrong = neutral/amber.
     No hunting. Actions are available progressively as items stream in. High contrast, large targets.

E) Preserve #8 behavior
   - Clean-item auto-clear, folder counts, drill-down, and the full per-field detail panel from #8 keep
     working exactly as-is. This pass ONLY ADDS actions; it does NOT change the bucketing logic
     (app\triage.py) or the streamed SSE payload.

F) BATCH_TRIAGE_DESIGN.md — status banner ONLY
   - Update the status banner to note that the approve / reject / "tool was wrong" click-through with
     on-screen clearing is now BUILT (label-level disposition, session-only, no persistence), and that
     the triage queue (Phase 3) is functionally complete pending deploy. Change NO other line.

DO NOT TOUCH
- The matching/extraction core: app\matching\*, app\models.py, app\fields.py, app\verify.py,
  app\quality_gate.py, app\extraction\*, app\config.py, app\matching\canonical.py — UNCHANGED.
- app\triage.py — UNCHANGED (bucketing is done; this pass only acts on its output).
- app\batch.py and app\main.py — UNCHANGED. Resolution is entirely client-side; the streamed payload
  from #8 already carries fields/folder_tags/clean. Do NOT add a resolution endpoint or any persistence.
- The graded catalog: test_labels\*, sample_data\test_labels.csv, TEST_PLAN.md, tools\generate_test_labels.py — UNCHANGED.
- The #7 demo corpus: demo_labels\*, sample_data\demo_applications.csv, tools\generate_demo_labels.py — UNCHANGED.
- Docs other than the BATCH_TRIAGE_DESIGN status banner — UNCHANGED.
- No new Python files/logic. No git add/commit/push. No .env / API-key access. No Docker/deploy.
- Do NOT run the 300-item demo batch through the model. Verify OFFLINE (see acceptance).

ACCEPTANCE TEST
1. pip install -r requirements.txt
2. pytest -q — the existing 89 tests still pass, unchanged (this pass adds no Python logic). Report the summary.
3. Boot check: TestClient GET /batch -> 200.
4. Interaction check WITHOUT the 300 live run — path (a): stub window.fetch + window.EventSource (no server/model
   call), feed a small fabricated batch INCLUDING at least one MULTI-FLAW label (e.g. brand + ABV), and via the
   rendered DOM confirm:
     - each folder row shows Approve / Reject / "Tool was wrong" buttons;
     - clicking Approve on the multi-flaw label removes it from the ABV folder AND the Brand folder
       (label-level clearing across all its folders);
     - the "need your attention" count decreases and the "reviewed by you" tally increments with the correct
       disposition (approved / rejected / tool errors);
     - the detail panel offers the same three actions and, after acting, auto-advances to the next unresolved
       item in that folder (or returns to the folder list when the folder empties);
     - when all items are resolved, the "all caught up" state shows the disposition summary;
     - reloading the page clears all dispositions (session-only — nothing persisted).
5. Scope check: git status shows ONLY app\static\batch.js, app\templates\batch.html, app\static\style.css, and the
   BATCH_TRIAGE_DESIGN status banner changed. The core, triage.py, batch.py, main.py, the graded catalog, the #7
   corpus, and all other docs are untouched.
6. Report back to the Testing Manager: the pytest summary (89), a step-by-step of the DOM interaction check
   (especially the multi-flaw label clearing from BOTH folders on one action, and the tally updates),
   confirmation of scope, and confirmation that nothing was committed/pushed and no 300-item live run occurred.
