OBJECTIVE
Rework the batch triage into the agent's real review workflow: buckets are ONE PER FIELD; a closed
bucket shows only its name + count; clicking a bucket opens a FOCUSED, one-label-at-a-time review
screen (banner → submitted photo → what the application says for that field → why the tool flagged it
→ Approve / Reject), advancing until the bucket empties. Approve is PER-FIELD (clears the label from
this bucket only); Reject is WHOLE-APPLICATION (pulls the label from every bucket and records a
"Rejected for / Please check" rollup). A new backend endpoint serves each label's photo. Built in the
#11 design system so it looks consistent. The matching/extraction core stays FROZEN — triage only
reads its output. Verified OFFLINE (unit tests + a fabricated-stream DOM walkthrough over real demo
images); no model calls.

TARGET REPO (CONFIRMED): C:\Users\finan\Documents\ttb-label-verify\   (NOT "shaphal".)

BEFORE YOU START — READ THESE
- app\triage.py            (current per-(field,reason) "folder" mapping — you will replace it with per-FIELD buckets)
- app\models.py            (FieldResult: field, expected, extracted, verdict, reason, note; LabelResult.fields)
- app\fields.py            (FIELD_REGISTRY — the 7 field keys + human labels)
- app\matching\canonical.py (CANONICAL_GOVERNMENT_WARNING — the warning reference text)
- app\main.py             (POST /batch, the SSE item/summary payload incl. folder_tags/clean/fields; job store)
- app\batch.py            (run_batch_stream, build_demo_items, the in-memory job store + how item images are held)
- app\templates\batch.html + app\static\batch.js + app\static\style.css (current triage UI from #8/#9/#11 — you rewrite the triage parts)
- tests\test_triage.py    (the folder tests — you rewrite them for per-field buckets)
- BATCH_TRIAGE_DESIGN.md   (status banner to update)

FILES TO EDIT / CREATE
EDIT:   app\triage.py                    (per-FIELD buckets + a whole-label "couldn't read" bucket)
EDIT:   tests\test_triage.py             (rewrite for the per-field bucket model)
EDIT:   app\main.py                      (rename folder_tags->bucket_tags in the SSE payload; ADD the image endpoint)
EDIT:   app\batch.py                     (expose per-item image bytes/path to the image endpoint; no behavior change to streaming)
EDIT:   app\static\batch.js              (rewrite the results/review UI: bucket cards + review screen + disposition logic)
EDIT:   app\templates\batch.html         (review-screen containers/markup)
EDIT:   app\static\style.css             (bucket-card + review-screen styling, in the #11 design system)
EDIT:   BATCH_TRIAGE_DESIGN.md           (status banner + the triage-model description — see PART 6)

CHANGES

PART 1 — app\triage.py : buckets are PER FIELD
  - Replace the per-(field,reason) folder mapping with ONE bucket per FIELD. bucket_id = field key;
    bucket_label = the field's human name (pull from FIELD_REGISTRY where possible), e.g.:
        brand -> "Brand name"; alcohol_content -> "Alcohol content"; warning -> "Government warning";
        class_type -> "Class / type"; net_contents -> "Net contents";
        producer -> "Producer name & address"; country_of_origin -> "Country of origin".
  - bucket_tags_for(result) -> list[BucketTag] (keep BucketTag defined here, NOT in models.py):
      BucketTag { bucket_id, bucket_label, field, reason, extracted, expected, note }.
      For each field whose verdict != PASS, emit ONE BucketTag for that field's bucket (carry reason,
      extracted, expected, note for the review screen). A CLEAN result (all PASS) -> [].
  - WHOLE-LABEL "couldn't read" bucket: if the result is a whole-label extractor failure — detect it as
    "every field verdict is NEEDS_REVIEW AND reason is UNREADABLE" (this is exactly how verify marks an
    extractor-unavailable label) — return a SINGLE BucketTag for bucket_id="unreadable_label",
    bucket_label="Couldn't read the label", instead of tagging all seven field buckets.
  - is_clean(result) -> bool unchanged (all fields PASS).
  - Keep it pure and deterministic. Do NOT change any verdict; buckets only GROUP non-PASS results.

PART 2 — tests\test_triage.py : rewrite for the per-field model
  - each non-PASS field -> its field bucket (bucket_id == field key, correct human label);
  - a clean result -> [] and is_clean True;
  - a multi-flag result (e.g. brand + alcohol_content) -> two tags, one per field bucket;
  - a whole-label unreadable result (all fields NEEDS_REVIEW/UNREADABLE) -> a SINGLE "unreadable_label" tag
    (NOT seven tags);
  - a PASS field is never bucketed.
  Report the new test count.

PART 3 — app\main.py + app\batch.py : image serving
  - Rename the SSE item payload key folder_tags -> bucket_tags (built from triage.bucket_tags_for). Keep
    `clean` and `fields`. Do NOT change verdict logic, pairing, or the summary event.
  - ADD endpoint: GET /batch/{job_id}/image/{image_filename} -> returns that label's image bytes with the
    correct content-type (image/png). SAFE LOOKUP ONLY: find the item in that job's stored item list by
    EXACT image_filename match and return ITS bytes/path; never build a filesystem path from the raw URL
    value (no path traversal). Demo items read from demo_labels\ on disk; uploaded items read from the
    in-memory job store. Unknown job or filename -> 404 (no crash).
  - app\batch.py: if needed, expose a small accessor so main.py can get an item's image bytes/path by
    filename from a job. Do NOT change run_batch_stream's streaming/concurrency/annotation behavior.

PART 4 — app\static\batch.js + batch.html + style.css : the bucket + review-screen UI
  RESULTS VIEW (after a batch runs):
    - A live summary bar: "cleared automatically: N" and "need your attention: M" (keep the #9-style
      progressive updates; CLEAN items only increment "cleared" and never render).
    - BUCKET CARDS: one card per non-empty bucket, showing the bucket_label, an icon, and a live COUNT.
      NO preview of contents inside a closed bucket. Large, obvious cards (NFR-03, #11 components).
  REVIEW SCREEN (click a bucket):
    - Banner: what to check for this field, e.g. brand -> "Check the brand name — does the label match the
      application?"; alcohol_content -> "Check the alcohol content (ABV / proof) against the application.";
      warning -> "Check the Government Warning — it must match the official statement exactly, all-caps
      prefix included."; class_type/net_contents/producer/country_of_origin -> "Check the {field} against
      the application."; unreadable_label -> "The tool couldn't read this label — review the image and decide."
    - PHOTO panel: the submitted label image via GET /batch/{job_id}/image/{image_filename}.
    - APPLICATION panel: "What the application says: {expected}" for this field. For the WARNING bucket,
      label it "Official Government Warning (must match exactly)" and show the reference text (the warning
      FieldResult.expected already carries the canonical text).
    - WHY-FLAGGED line (plain language from the tag's reason/extracted/expected), e.g.
        MISMATCH -> "The tool read '{extracted}', but the application says '{expected}'."
        BORDERLINE -> "The tool read '{extracted}' — close to '{expected}', not a confident match."
        BLANK_EXPECTED (abv) -> "No alcohol content was entered and none was read — confirm it's legitimately absent."
        SPECIAL_CHARACTER -> "'{extracted}' has special characters — needs a human check against '{expected}'."
        WARNING_WORDING -> "The warning wording differs from the official statement."
        WARNING_PREFIX_NOT_ALLCAPS -> "The 'GOVERNMENT WARNING' prefix isn't in all caps."
        WARNING_PREFIX_MISSING -> "The 'GOVERNMENT WARNING' prefix is missing."
        UNREADABLE -> "The tool couldn't read this field."
        UNEXPECTED_VALUE -> "The label shows a value here, but the application expected none."
    - Progress: "Label i of N in this bucket".
    - OPTIONAL (recommended) "View full label details" expander: reveals the full per-field
      extracted-vs-expected table for this label (reuse the #11 table + status styling) from the item's
      `fields`. Default view stays focused on the one field.
    - Two big buttons: Approve (btn--success) and Reject (btn--danger).
  DISPOSITION LOGIC (client-side, in-memory, SESSION-ONLY — no persistence, no network):
    - Identify each application by image_filename. Its "flagged fields" = the fields in its bucket_tags.
    - State: appStatus[app] in {pending, rejected}; approvedFields[app] = Set of approved field keys;
      rejectionInfo[app] = { rejectedField, reason, pleaseCheck: [{field, reason} for ALL flagged fields] }.
    - APPROVE (in bucket F): add F to approvedFields[app]; the app leaves bucket F only; advance to the next
      pending item in F. If the app now has every flagged field approved, it is fully cleared (counts toward
      "cleared by you"). It REMAINS in any other buckets it was flagged in.
    - REJECT (in bucket F): set appStatus[app]=rejected; capture rejectionInfo (rejectedField=F, reason=this
      item's reason, pleaseCheck = every flagged field of the app + its reason); the app leaves ALL buckets.
      Show a brief inline confirmation: "Rejected for: {F label}. Please check: {list}." then advance to the
      next pending item in F.
    - Bucket F live count = apps flagged on F that are neither rejected nor have F approved.
    - When a bucket empties, show a short "This bucket is clear" and return to the bucket list.
    - When ALL buckets are empty, show an "All caught up" summary: "Reviewed X applications — A cleared by
      you, R rejected", optionally listing the rejected apps with their "please check" reasons.
    - Reloading the page resets everything (session-only; nothing persisted — D-8/CON-02).
  Keep NFR-03 (big targets, high contrast, obvious) and progressive streaming (NFR-02).

PART 5 — REMOVE the old model
  - Remove the old per-(field,reason) folders, the old list-of-rows-with-inline-buttons, and the old
    THREE-button ("Tool was wrong") interaction from #9. The new flow is two buttons (Approve/Reject) only.

PART 6 — BATCH_TRIAGE_DESIGN.md
  - Update the status banner AND the section that describes the triage/bucket model to reflect: buckets are
    per FIELD; closed buckets show only name + count; a focused one-label review screen (banner/photo/
    application value/why-flagged/Approve/Reject/advance); Approve = per-field clear, Reject = whole-app with
    "Rejected for / Please check" rollup; a single "Couldn't read the label" bucket for whole-label failures;
    photos served to the browser; session-only, no persistence. Keep it concise; do not rewrite unrelated sections.

DO NOT TOUCH
- The matching/verdict core: app\matching\*, app\models.py, app\fields.py, app\matching\canonical.py — UNCHANGED
  (define BucketTag in app\triage.py). run_matchers, reasons, canonical text — all unchanged.
- app\verify.py and app\extraction\* — UNCHANGED (triage reads results; it does not re-run extraction/matching).
- The single-label page + flow: app\templates\index.html, app\static\app.js, GET / and POST /verify — UNCHANGED.
- The graded catalog (test_labels\, sample_data\test_labels.csv, TEST_PLAN.md, tools\generate_test_labels.py) — UNCHANGED.
- The #7 demo corpus GENERATORS + data (tools\generate_demo_labels.py, sample_data\demo_applications.csv) — UNCHANGED
  (the image endpoint READS demo_labels\ images; reading is fine, do not modify them).
- REQUIREMENTS.md, ARCHITECTURE.md, PROJECT_HANDOFF.md — UNCHANGED this pass.
- No git add/commit/push. No .env / API-key access. No Docker/deploy. Do NOT run the 300-item live batch —
  verify OFFLINE per the acceptance test.

ACCEPTANCE TEST
1. pip install -r requirements.txt
2. pytest -q — the prior single-label/matching/etc. tests still pass, PLUS the rewritten tests\test_triage.py
   (per-field bucketing; clean -> []; multi-flag -> per-field tags; whole-label unreadable -> single
   "unreadable_label" tag). Report the pytest summary and the new triage test count.
3. Image endpoint test (OFFLINE — no model): build a demo job (via build_demo_items — pairing only, no
   extraction) in the job store, then TestClient GET /batch/{job_id}/image/{a real demo filename} -> 200 with
   image bytes; an unknown filename -> 404; confirm a traversal-style filename cannot escape the job's item set.
4. Boot check: GET /batch -> 200; GET / -> 200.
5. DOM walkthrough (OFFLINE — path a): create a real demo job (so the image endpoint serves real photos), then
   stub the stream and inject fabricated result items (with bucket_tags/clean/fields) that REFERENCE real demo
   filenames — include at least one CLEAN label, one single-flag label, and one MULTI-FLAG label (e.g. brand +
   alcohol_content). Via the rendered DOM confirm:
     - closed bucket cards show only name + count (no contents preview); clean labels only bump "cleared";
     - clicking a bucket opens the review screen: banner, the PHOTO renders from the image endpoint, the
       application-value panel, the why-flagged line, and Approve/Reject buttons; progress "i of N";
     - APPROVE on the multi-flag label removes it from THIS bucket but it REMAINS in its other bucket;
     - REJECT on a label removes it from ALL its buckets and shows the "Rejected for / Please check" rollup
       listing every flagged field;
     - advancing works to the next label; emptying a bucket returns to the list; resolving everything shows the
       "All caught up" summary;
     - reload clears all dispositions (session-only).
6. Scope check: git status shows only the intended files; the matcher core, verify.py, extraction, the single-
   label page, the graded catalog, and the demo generators/data are unchanged.
7. Report back to the Testing Manager: pytest summary + triage test count, the image-endpoint test result, a
   step-by-step of the DOM walkthrough (especially approve-keeps-multi-flag-in-other-bucket and reject-clears-
   all-buckets-with-rollup), confirmation of scope, and that nothing was committed/pushed and no live 300-run occurred.
