# COWORK HANDOFF #4b-1-doc — "Future Build" note (applicant pre-scan / ingestion-time verification)

## OBJECTIVE
Append ONE new, self-contained "Future Build / Out of Scope" section to the END of
`ASSUMPTIONS_AND_TRADEOFFS.md`, recording an idea that was considered and deliberately
NOT adopted for this prototype: an applicant-facing pre-scan with an authoritative
TTB-side re-verification at ingestion. This is documentation only — it captures the
reasoning so a reviewer sees it was thought through. Change nothing else. Do not
build anything, do not touch any other file, do not commit or push.

## FILES TO CREATE / EDIT
Edit:
- C:\Users\finan\Documents\ttb-label-verify\ASSUMPTIONS_AND_TRADEOFFS.md

## CHANGES
Append the following as a NEW section at the very END of the file (after the last
existing section). Do NOT edit, renumber, or reword any existing decision (D-*),
assumption (MA-*), trade-off, limitation, or open question. This is add-only, and it
introduces NO new D-* or MA-* IDs (so nothing collides with existing numbering — note
D-15 is already the image quality gate). Add it verbatim:

---

## G. Future Build / Considered-but-Not-Adopted

Ideas evaluated during design that are **deliberately out of scope** for this
prototype but recorded here to show they were reasoned through. None of these is
built, and none changes the graded core.

### FB-1 — Applicant-facing pre-scan with ingestion-time re-verification

**The idea.** "Submission" and "agent review" are two separate moments: the label
artwork and expected data enter the system when an applicant files, potentially days
before an agent pulls the item from their queue. That opens an option to run
verification at **submission / ingestion time** rather than at **agent-review time**.
An applicant could self-scan a label and get instant completeness / legibility /
match feedback (a retake loop, like mobile check deposit) before submitting; the
agent would then read a pre-computed verdict instead of waiting on a live call.

**Why it's attractive.** It largely removes the ~5-second latency bar as an *agent*
constraint (the verdict is pre-computed), and — because the applicant enters the
expected data too — a pre-scan could catch mismatches before submission, heading off
the multi-day "reject and ask for a better image" round-trip.

**The load-bearing correction (trust boundary).** The applicant is the regulated
party and has an incentive to pass, so an applicant-side result and any
client-submitted metadata can only ever be **advisory**. The **authoritative
compliance verdict must be computed on TTB-controlled infrastructure at ingestion**,
never trusted from the filer. (Same as a bank: your phone's read of a check is
convenience; the bank re-reads server-side.) With that boundary in place, all the
benefits hold — applicant gets instant feedback on their own time, the agent reads a
trustworthy pre-computed verdict, and the queue is auto-filtered so unreadable /
mismatched / junk submissions are flagged before a human sees them.

**Why it's cheap to add later.** The core is already "AI reads, code judges" behind a
single `verify()` interface, so the same engine can serve an agent upload, an
applicant pre-scan, or an ingestion-time run with **no change to the graded logic** —
only a new caller plus the rule that the authoritative run is server-side.

**Why it's NOT in this prototype.** The brief and every stakeholder interview describe
an **agent-facing desk tool** reviewing a queue; COLA integration is explicitly out of
scope (CON-01), and the deliverable should stay the clean, complete agent-facing core
rather than pivot to an applicant portal (CON-04). This is therefore documented as a
production/scale direction, not built. Cost note: applicant-triggered scans would
spend our API budget, so an adopted version would depend on the spend-cap /
bring-your-own-key control and per-endpoint rate limiting.

---

## DO NOT TOUCH
- Any existing section, decision, assumption, trade-off, limitation, or open question
  in ASSUMPTIONS_AND_TRADEOFFS.md — additions only, appended at the end.
- Every other file in the repo: REQUIREMENTS.md, ARCHITECTURE.md, TEST_PLAN.md, all
  source and test files, .env, Dockerfile, etc. — unchanged.
- No code. No new FR/MR/NFR. No new D-*/MA-* IDs. No git add, commit, or push.

## ACCEPTANCE TEST
1. Open `C:\Users\finan\Documents\ttb-label-verify\ASSUMPTIONS_AND_TRADEOFFS.md` and
   confirm a new final section "## G. Future Build / Considered-but-Not-Adopted" with
   the "FB-1 — Applicant-facing pre-scan..." entry appears at the end, and that no
   earlier content was changed, renumbered, or removed.
2. Confirm no other file changed (`git status` shows only ASSUMPTIONS_AND_TRADEOFFS.md
   modified), and that nothing was committed or pushed.
3. Paste back the appended section and the `git status` output to the Testing Manager.
