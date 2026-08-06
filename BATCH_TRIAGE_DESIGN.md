# Batch Triage & Data-Source — Design Direction (Documented Target)
## TTB AI Label Verification Prototype — Working Document

> **STATUS: IN BUILD — Phase 3 (exception-folder triage) functionally complete, pending deploy.**
> Batch sorts into folders by reason code and clean items auto-clear; clicking a label opens the full
> per-field detail. The approve / reject / "tool was wrong" click-through is now BUILT, with the row
> clearing on-screen the instant the agent acts (label-level disposition — one label with one decision
> clears from every folder it appears in), running tallies, and an "all caught up" closing state.
> Disposition is session-only, held in memory with no persistence (D-8 / CON-02). Next: deploy.

---

## 1. The north star: batch in, exceptions out

Today the deputy director's 47 agents pull applications one at a time and re-check, by
eye, fields that are usually correct. The tool's real leverage is not "verify one label
faster" — it is **turning a queue of hundreds into a short list of the few that actually
need a human**.

The target workflow:

1. **Batch in.** An agent (or an ingestion job) submits many label + application pairs at
   once — the peak-season importer dump of 200–300 that Janet in Seattle has been asking
   about for years.
2. **Clean items auto-clear.** Every pair runs through the existing pipeline
   ("AI reads, code judges"). Anything that comes back all-PASS drops out of the human's
   view — it is done. The agent never looks at the labels that were already right.
3. **Exceptions group into folders by reason code.** Everything not-clean is bucketed by
   *why* it was flagged, using the reason taxonomy already in the result model (D-14):
   an "ABV mismatch" folder, a "warning wording" folder, a "couldn't read" folder, a
   "blank in the application" folder, and so on.
4. **Review one flaw across many labels.** The agent works a folder at a time — reviewing
   the same kind of problem across many labels in one mental mode, instead of context-
   switching field-by-field down a queue. This is the efficiency multiplier for a team of
   47 covering 150,000 applications a year.
5. **Click-through resolution.** For each flagged item the agent can **approve** (override
   to accept), **reject**, or **note**, right in the folder.
6. **Multi-flaw labels appear in multiple folders.** A label with both an ABV mismatch and
   a bad warning is tagged into both folders; resolving it in one reflects everywhere.

## 2. The single-label view is retained, not retired

The single-label page built in #5 is **not** replaced by the triage queue — it becomes the
**detail panel** that opens when an agent clicks a flagged row. The batch view answers
"which of these need me?"; the single-label view answers "show me this one, field by
field, extracted-vs-expected, so I can make the call." Both are needed; the detail view is
where "show the work" (Principle A-3) lives.

## 3. The data-source seam (this handoff) is the foundation

This handoff builds the piece the triage queue stands on: a **single `ApplicationSource`
interface** that supplies the expected values, backed today by a bundled demo CSV
(`DemoCsvSource`) and, in production, by the same shape coming from TTB's systems
(`AzureApplicationSource`, a visible stub). Batch triage is "run the pipeline over every
`Application` the source yields, then group the results" — so the source is exactly the
input side of the north-star workflow. An uploaded CSV is just another `ApplicationSource`.

## 4. Registry-driven extensibility

The loader reads which fields are "expected" from the field registry, not a hardcoded list.
Add TTB's proposed **Alcohol Facts** panel or an **allergen** disclosure as a registry
entry and the data layer pulls it from applications automatically — **data, not a code
rewrite**. Unknown columns (like the demo's `beverage_type`) ride along in an `extra` bag
and never reach the matcher, so a richer application record never destabilizes the graded
core. The triage folders inherit the same extensibility: a new field just means new
possible reason-code folders.

## 5. The Azure/COLA on-ramp: visible but stubbed

Production would pull application records straight from TTB's COLA/Azure tenant instead of a
CSV. That path is present in the code as `AzureApplicationSource` — same `Application`
shape, so nothing downstream changes — but it is a **documented stub, never a live
integration**. COLA integration is explicitly out of scope for the prototype (CON-01); the
demo runs on `DemoCsvSource` or an uploaded CSV. Keeping the seam visible shows the
production shape without pretending to have built it.

## 6. Resolution is on-screen only (no persistence)

Approve / reject / note decisions live in the browser session for the demo — there is **no
persistence** (D-8 / CON-02): no PII stored, no audit trail, nothing sensitive retained. A
production version would write decisions to a compliant retention store; the prototype
deliberately does not, and says so.

## 7. Alternatives considered and rejected

- **Auto-match / auto-approve (no human).** Rejected: a false PASS is the worst failure mode
  in compliance (Principle A-2). The tool clears the *obviously clean* and routes everything
  else to a human; it never closes an application on the AI's say-so.
- **Single-label as the whole workflow.** Rejected as the *primary* workflow at scale: making
  an agent open 300 labels one at a time is the status quo with extra clicks. Single-label is
  retained as the detail view (§2), not the front door.
- **Real Azure/COLA integration in the prototype.** Rejected (out of scope, CON-01): it would
  blow the timebox and needs authorization the POC does not have. The seam is stubbed and
  visible instead.

---

*This is the documented target. The current phase order (single-label UI → data-source →
batch → deploy) is unchanged; this doc graduates from target to in-build only when the pivot
is scheduled.*
