OBJECTIVE
Build the exception-folder triage view on top of the working batch pipeline: a finished
batch sorts its labels into folders by problem type (using the reason codes we already
produce), clean labels auto-clear and never clutter the screen, and the agent can open a
folder to see just that ONE problem across many labels and click any label to open its
full per-field detail. READ-ONLY this pass — the approve/reject/note click-through and
on-screen clearing are the NEXT handoff. All new logic is unit-tested OFFLINE; no model
cost is required to build or verify this pass.

TARGET REPO (CONFIRMED): C:\Users\finan\Documents\ttb-label-verify\
  NOTE: NOT "shaphal" — that is an unrelated Next.js project. All paths below are under
  C:\Users\finan\Documents\ttb-label-verify\.

BEFORE YOU START — READ THESE (understand the current shapes; don't modify yet)
- app\models.py            (FieldResult, LabelResult/VerificationResult, BatchItemResult, ResultReason enum)
- app\matching\rules.py    (which ResultReason each matcher emits, and the verdict per field)
- app\batch.py             (run_batch_stream / build_demo_items — where items are produced + streamed)
- app\main.py              (POST /batch, GET /batch/{id}/stream — the SSE "item" and "summary" payload shape)
- app\templates\batch.html + app\static\batch.js + app\static\style.css  (current batch UI)
- app\templates\index.html + the single-label per-field result rendering (the readout to REUSE as the detail panel)
- BATCH_TRIAGE_DESIGN.md   (the design this implements — folders by reason code, clean items auto-clear,
                            single-label view retained as the detail panel, on-screen only, no persistence)

FILES TO CREATE / EDIT
CREATE: app\triage.py               (reason->folder mapping + pure folder-tagging logic; tested)
CREATE: tests\test_triage.py        (offline unit tests for the mapping + tagging)
EDIT:   app\batch.py and/or app\main.py  (annotate each streamed item with its folder tags + a clean flag)
EDIT:   app\templates\batch.html    (render the triage surface: summary bar, folders, detail-panel container)
EDIT:   app\static\batch.js         (bucket streamed items into folders; live counts + cleared tally; drill-down; detail panel)
EDIT:   app\static\style.css        (folder/triage styling — large targets, high contrast; NFR-03)
EDIT:   app\templates\batch.html    (copy fix: the "Run the 10 built-in sample labels" text -> dynamic count, else "300")
EDIT:   BATCH_TRIAGE_DESIGN.md      (status banner ONLY — see change E; change no other line)

CHANGES

A) app\triage.py  (NEW — pure, testable; keeps "code judges" in Python)
   - Define FolderTag IN THIS FILE (a small pydantic model or dataclass) so app\models.py is NOT touched:
       FolderTag { folder_id: str, folder_label: str, field: str, reason: str,
                   extracted: str | None, expected: str | None, note: str | None }
   - Reason->folder mapping. For each NON-PASS (field, reason), map to a stable folder_id + human label.
     Render only non-empty folders in the UI. Suggested mapping (adjust ids as convenient, keep labels human):
       warning + WARNING_WORDING                       -> "Warning — wording changed"
       warning + WARNING_PREFIX_NOT_ALLCAPS            -> "Warning — prefix not all caps"
       warning + WARNING_PREFIX_MISSING               -> "Warning — prefix missing"
       warning + UNREADABLE                            -> "Warning — couldn't read"
       alcohol_content + MISMATCH                      -> "Alcohol content — mismatch"
       alcohol_content + BLANK_EXPECTED                -> "Alcohol content — confirm absence"
       alcohol_content + (UNREADABLE | UNEXPECTED_VALUE) -> "Alcohol content — couldn't read"
       brand + MISMATCH                                -> "Brand — mismatch"
       brand + BORDERLINE                              -> "Brand — borderline match"
       brand + SPECIAL_CHARACTER                       -> "Brand — special characters"
       brand + UNREADABLE                              -> "Brand — couldn't read"
       (class_type|net_contents|producer|country_of_origin) + BLANK_EXPECTED -> "Required field left blank"
       (class_type|net_contents|producer|country_of_origin) + (MISMATCH|BORDERLINE|UNREADABLE|SPECIAL_CHARACTER)
                                                       -> "Supporting field — needs review"
     Provide a FALLBACK folder "Other — needs review" for any non-PASS (field, reason) not explicitly mapped,
     so no flaw is ever silently dropped.
   - folder_tags_for(result) -> list[FolderTag]:
       iterate result.fields; for each field whose verdict != PASS, emit one FolderTag (carry the field's
       extracted, expected, note). A CLEAN item (all fields PASS) returns []. A MULTI-FLAW item returns
       multiple tags — this is the "tagged into multiple folders" behavior. De-dupe identical folder_ids.
   - is_clean(result) -> bool: True iff every field verdict == PASS.
   - Do NOT reclassify or change any verdict. Folders only GROUP the non-PASS results the engine already produced.

B) Stream annotation (app\batch.py / app\main.py)
   - Where each item is serialized for the SSE "item" event, ADD two fields to the payload:
       folder_tags: the list from triage.folder_tags_for(result)
       clean:       triage.is_clean(result)
   - Do NOT change verdict logic, pairing, or the final "summary" event (still total + pass/fail/needs-review counts).

C) Triage UI (batch.html + batch.js + style.css)
   - After a batch runs (demo or upload), the RESULTS SURFACE is the triage view:
       * Summary bar, updating live as items stream:  "✓ N cleared automatically   ▲ M need your attention".
       * CLEAN items increment the cleared tally ONLY — they NEVER appear as rows (the auto-clear requirement).
       * FLAWED items drop into their folder(s) by folder_tags. Each folder shows its label + a LIVE count.
         Only non-empty folders render.
       * Click a folder -> it opens/expands to LIST its items. Each row shows the label id/filename + THIS
         folder's single flaw (that field's extracted-vs-expected + reason) — NOT the full seven-field readout.
       * Click a row -> open the DETAIL PANEL: the FULL per-field readout for that label (REUSE the single-label
         result rendering: field | extracted | expected | verdict | reason, color-coded green/red/amber).
         This is where the single-label view lives on as the detail panel (per the design — it is retained, not retired).
   - NFR-03: big obvious targets, high contrast, no hunting. Folders are large clickable cards/rows.
   - NFR-02: preserve progressive streaming — folders and tallies fill as items arrive.
   - READ-ONLY this pass: NO approve/reject/note buttons, NO clearing/resolution interactions (next handoff).

D) Copy fix
   - Update the demo button/description that reads "10" sample labels to reflect the current demo size — prefer
     reading the count dynamically; otherwise "300".

E) BATCH_TRIAGE_DESIGN.md — status banner ONLY
   - Change the top status banner from the "DOCUMENTED TARGET — not yet the built product" wording to:
       "STATUS: IN BUILD — Phase 3 (exception-folder triage) started. Read-only folder view first
        (batch sorts into folders by reason code, clean items auto-clear, click a label for the full
        per-field detail); approve/reject/note click-through is the next pass."
   - Change NOTHING else in the document.

DO NOT TOUCH
- The graded matching/extraction core: app\matching\*, app\models.py, app\fields.py, app\verify.py,
  app\quality_gate.py, app\extraction\*, app\config.py, app\matching\canonical.py — UNCHANGED.
  (Define FolderTag in app\triage.py, NOT in models.py.)
- The graded catalog: test_labels\*, sample_data\test_labels.csv, TEST_PLAN.md, tools\generate_test_labels.py — UNCHANGED.
- The #7 demo corpus: demo_labels\*, sample_data\demo_applications.csv, tools\generate_demo_labels.py — UNCHANGED.
- Docs other than the BATCH_TRIAGE_DESIGN status banner: README.md, REQUIREMENTS.md,
  ASSUMPTIONS_AND_TRADEOFFS.md, ARCHITECTURE.md, PROJECT_HANDOFF.md — UNCHANGED this pass (doc sync comes later).
- NO approve/reject/note/resolution logic this pass (that is the next handoff).
- NO git add/commit/push. NO .env / API-key access or printing. NO Docker/deploy.
- Do NOT run the 300-item demo batch through the model. Build and verify OFFLINE (see acceptance).

ACCEPTANCE TEST
1. pip install -r requirements.txt
2. pytest -q — all pass, including the new tests\test_triage.py. Cover at least:
     - each mapped (field, reason) lands in the expected folder_id/label;
     - a clean result (all PASS) -> folder_tags_for returns [] and is_clean is True;
     - a multi-flaw result -> multiple tags (into multiple folders);
     - an unmapped non-PASS (field, reason) -> the "Other — needs review" fallback (nothing dropped).
   Report the pytest summary and the new test count.
3. Boot check: TestClient GET /batch -> 200.
4. Rendering check WITHOUT the 300 live run — choose the cheapest path:
     (a) feed the client a small FABRICATED batch (hand-built item payloads incl. folder_tags/clean), OR
     (b) upload 3–5 catalog images through the normal upload path (a handful of cheap calls).
   Do NOT run the 300-item demo. Via the rendered DOM confirm:
     - clean items increment the "cleared" tally and do NOT appear as rows;
     - flawed items appear under the correct folders with live counts;
     - clicking a folder lists its items each showing that folder's one flaw;
     - clicking a row opens the FULL per-field detail panel.
5. Scope check: git status shows only the intended files changed; the graded catalog, the #7 demo corpus,
   the matching/engine core, and all docs EXCEPT the BATCH_TRIAGE_DESIGN status banner are untouched.
6. Report back to the Testing Manager: the pytest summary + new test count, the folder mapping as built,
   which rendering-check path you used and what the DOM showed, confirmation of scope, and confirmation that
   nothing was committed/pushed and no 300-item live run occurred.
