# COWORK HANDOFF #18 — Batch Page Reorder + Status-Pill Alignment

## OBJECTIVE
Two presentation-only UI changes to the TTB Label Verification app.
(A) On the batch page, reorder the results layout so that once a batch has run, the
top-to-bottom order is: Done summary → folders → records → upload area.
(B) Align the status pills into a fixed column immediately LEFT of the Re-ingest button
on the History view (and any record rows that share that layout), so every pill lines up
in one straight vertical column.

NO changes to matching, verdicts, extraction, quality-gate, batch logic, data, pill
text/colors, or route behavior — this is layout / markup / CSS only.

---

## FIRST: LOCATE THE FILES (do this before editing)
The exact file names have drifted from the original planning docs, so find the files by
content, not by guessing paths. From `C:\Users\finan\Documents\ttb-label-verify\`, search
the `app\templates` and `app\static` folders for these strings and open whatever files
contain them:

- `"Run the demo batch"`   → the batch page markup / renderer
- `"cleared automatically"` → the "Done —" summary bar
- `"Re-ingest"`            → the History row markup
- `"Auto-cleared"`         → the status pill markup

Likely locations: `app\templates\*.html` and `app\static\*.js` / `*.css`. Report the
actual files you edited.

---

## PART A — REORDER THE BATCH PAGE RESULTS

On the batch page there are four blocks:
1. the "Done — cleared automatically / need your attention" summary bar,
2. the field-grouped folders/buckets (records grouped by which field needs a look),
3. the individual records list,
4. the upload area = the "Check a batch of labels" heading + intro text + the
   "Try the demo" card + the "Use your own" card.

Change the layout so that **when a batch has been run and results are present**, the
top-to-bottom order is:
1. Done summary
2. Folders
3. Records
4. Upload area (heading + intro + both cards)

**Before any batch is run (no results yet):** show the upload area (heading + intro +
both cards) at the top exactly as it is today. The reorder applies only once results
exist, so the "Done" bar becomes the first thing on the page after a batch runs.

Keep the heading + intro grouped WITH the upload cards so they move down together as one
unit. Implement this by physically ordering the containers in the DOM (or a single flex
column with explicit `order` values) — do NOT use absolute positioning or fragile
margins. Preserve every existing block's content and behavior exactly; only their
vertical order changes.

---

## PART B — LINE UP THE STATUS PILLS NEXT TO RE-INGEST

On each History row (and any batch record row that uses the same pill + trailing action
layout), the status pill currently floats right after the product name, so the pills sit
at ragged horizontal positions. Restructure each row as a flex row with three parts, in
this order:

`[ product name / description — flex: 1, takes the flexible remaining width ]`
`[ status pill — fixed-width slot, right-aligned, immediately LEFT of the button ]`
`[ Re-ingest button — last, fixed ]`

- Give the pill slot a **fixed width** wide enough for the longest pill label (e.g. the
  longest of "Auto-cleared", "Needs review", "Rejected", etc.) and **right-align** the
  pill within that slot, so every pill lands at the same x-position and forms one straight
  vertical column directly beside the Re-ingest button.
- Vertically center the pill and the button within the row.
- Do NOT change pill colors, labels, verdicts, or the button's behavior.

---

## DO NOT TOUCH
- Any matching, verdict, extraction, quality-gate, or batch-processing logic.
- The pill semantics (which verdict maps to which pill/color) and pill text.
- Route handlers' behavior or the data shown — this is markup / CSS / render-order only.
- Do NOT commit, push, or deploy. The Testing Manager reviews first.

---

## ACCEPTANCE TEST
1. Run the app locally (e.g. `uvicorn app.main:app`) and open the batch page.
2. With results present, confirm the vertical order is: Done summary → folders → records
   → upload area (heading + both cards). With no results, the upload area shows normally
   at the top.
3. Open History: confirm every status pill lines up in one straight vertical column
   directly to the LEFT of its Re-ingest button, across rows of different name lengths.
4. Confirm nothing else moved or changed and no verdicts/pills changed value.
5. Report back to the Testing Manager: the exact files you edited, and a screenshot (or
   clear description) of the batch page order and the aligned History pills. **Do NOT push.**
