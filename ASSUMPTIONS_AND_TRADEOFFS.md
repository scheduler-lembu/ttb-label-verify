# Approach, Assumptions, Trade-offs & Limitations
## TTB AI Label Verification Prototype — Working Document

**Status:** Living document · **Owner:** Testing Manager
**Purpose:** Capture every decision, forced assumption, trade-off, and known
limitation as we build, so the final README writeup is already done and every
"why did you do it this way" question has an answer on record.

> **How to use this doc:** Each item has a state — **[DECIDED]**, **[PROPOSED]**
> (awaiting your confirmation), or **[OPEN]**. As we lock things in, states move to
> DECIDED. Open questions are collected in §F.

---

## A. Guiding Principles (the approach in four ideas)

1. **AI reads, code judges.** The vision model only transcribes the label into
   structured fields. All matching (fuzzy brand, ABV/proof equivalence, exact
   warning) is done by deterministic code against stored rules. → reliable,
   testable, and *explainable* verdicts, which a compliance tool needs.
2. **Three-state results, biased to safety.** Every field is **PASS / FAIL /
   NEEDS REVIEW**. When confidence is low, escalate to a human rather than guess.
   A false PASS is the worst failure mode in compliance; we bias against it.
3. **Show the work.** Every result displays extracted value, expected value, the
   rule applied, and the verdict — never a bare PASS/FAIL. Keeps the human in
   control (Dave's "you need judgment").
4. **Fast single-label, streamed batch.** ~5s is the bar for one interactive
   label. Batch runs concurrently and streams results as they complete, so the
   agent is never blocked.

---

## B. Key Design Decisions & Their Trade-offs

| # | Decision | Choice (prototype) | Why | Trade-off / Limitation | Production path |
|---|---|---|---|---|---|
| D-1 | **Extraction engine** | OpenAI GPT-5.6 tier family — `gpt-5.6-terra` for single label, `gpt-5.6-luna` for batch; config-swappable; production path = the current GPT model offered on Azure OpenAI inside TTB's tenant | One call does OCR + field understanding; best on imperfect images; fits ~5s. The Sol/Terra/Luna tiers map directly onto the premium/balanced/cheap dual-engine cost model. | Cloud dependency; per-call cost; non-deterministic transcription | Azure OpenAI / Azure Document Intelligence **inside TTB's existing Azure tenant** → avoids the outbound-firewall block |
| D-2 | **Matching logic** | Deterministic Python, separate from AI | Exact-warning check and auditability require code, not model judgment | More rules to write and test | Same code; add per-field config |
| D-3 | **Result model** | PASS / FAIL / **NEEDS REVIEW** | Avoids false PASS; matches agent behavior of asking for a better image | Some auto-passable labels get flagged (extra human glance) | Tune confidence thresholds with real data |
| D-4 | **Warning check** | Extract text → normalize whitespace only → compare char-for-char to stored canonical text; verify all-caps prefix | This is the one field where fuzzy = wrong | Depends on faithful transcription of the warning | Same |
| D-5 | **Warning font-size / bold ("buried text")** | Best-effort visual signal → **NEEDS REVIEW**, not a hard FAIL | True forensic font analysis is the hardest item (MR-06, a Could) | Not a rigorous measurement in the prototype | Bounding-box + font metrics via Document Intelligence |
| D-6 | **Batch processing** | Concurrent calls (capped pool) + progressive result streaming | 300 sequential 5s calls = 25 min; unacceptable | Cost scales with batch size; API rate limits | Queue + worker autoscaling |
| D-7 | **Application-data input** | Single: on-screen form. Batch: CSV/spreadsheet (one row per label) + image files matched by a filename/ID column | No COLA to pull from; simplest agent-friendly contract | Rigid input format; agent must follow the column convention | Pull expected values directly from COLA |
| D-8 | **Persistence** | None / ephemeral. Images processed in memory, discarded after | No real PII (CON-02); nothing sensitive stored | No history/audit trail in the prototype | Compliant retention store |
| D-9 | **Auth** | None (or a trivial shared password if you want to limit access) | It's a public demo POC | Anyone with the URL can use it | SSO / federal identity |
| D-10 | **Stack** | Python + FastAPI, deterministic matcher, minimal frontend, Docker, Fly.io | Async (good for batch), fast to build, strong AI ecosystem, simple deploy | Opinionated; not the only valid choice | Containerized into TTB's Azure |
| D-11 | **UI** | One obvious page: big upload zone, one primary button, results as a clear table | 73-year-old / no-training benchmark | Fewer power-user features | Role-based richer UI |
| D-12 | **Blank required field** | Empty required expected value → NEEDS_REVIEW (categorized), not PASS | Closes a false-PASS hole; makes the required flag meaningful | A little more review on incomplete entries | Form pre-validation; pull expected values from COLA |
| D-13 | **Warning body strictness** | Exact characters incl. case (strict) | MR-04 says "character-for-character"; over-strict beats under-strict on the one exact field | Re-cased/reformatted-but-correct warnings FAIL (false-FAIL); visible + overridable | Same; optional case-insensitive body mode |
| D-14 | **Review reason taxonomy** | Every result carries a machine-readable reason code | Lets agents triage/group reviews ("all blanks", by field) — efficiency for 47 agents, esp. batch | Small enum to maintain | Same + filterable review-queue UI |
| D-15 | **Pre-extraction image quality gate** | Cheap OpenCV blur (Laplacian variance) + blank (std-dev) check; fail → NEEDS_REVIEW "request a better image" BEFORE any API call | Saves a paid call on unreadable uploads and mirrors the agent's real practice of asking for a better photo (NFR-05) | Heuristic thresholds; a borderline image may pass or be flagged | Tunable thresholds / a calibrated quality model |
| D-16 | **Literal-OCR warning cross-check (Tesseract)** | Vision read still produces the strict verdict; Tesseract reads the same image and if the two warning reads disagree (fuzzy body < threshold, or all-caps prefix differs) a PASS is downgraded to NEEDS_REVIEW | VLMs paraphrase/"clean up" text — the false-PASS failure mode on the one graded exact field; a literal reader catches divergence without brittle OCR-vs-canonical matching | Tesseract is weaker on rotated/tiny text, so some compliant warnings on imperfect images route to NEEDS_REVIEW (recall-over-precision); needs the tesseract-ocr binary | Azure Document Intelligence (Read) as the literal reader in production |
| D-17 | **Parallel dual read** | Vision call and Tesseract read run concurrently (thread pool) | Adds ~no wall-clock (bounded by the slower read), so the cross-check honors the ~5s bar | Slightly more orchestration than sequential | async in production |
| D-18 | **Cross-check is one-directional (safety-only)** | The cross-check can only move a warning PASS → NEEDS_REVIEW; it never relaxes a FAIL/REVIEW, and the strict verdict still runs on the vision read via the unchanged matcher | Keeps the graded matcher frozen and the change strictly conservative | A compliant warning misread by OCR may be flagged for a human (visible, overridable) | Tune threshold with real data |
| D-19 | **Graceful OCR fallback** | If the Tesseract binary is unavailable, the cross-check is skipped and the warning falls back to the vision read (the #4 behavior) | The cross-check is an enhancement, not a hard dependency; local dev without the binary still runs | Without Tesseract the false-PASS protection is prompt-only | The deployed container ships Tesseract so production always has the cross-check |
| D-20 | **Single-label latency hardening** | Disable SDK retries (max_retries=0); a generous per-request hang-ceiling timeout (stall → NEEDS_REVIEW); cap output tokens; downscale oversized images before the vision call | The retry-balloon pushed a slow call past the bar; typical latency (~2-3s median) meets NFR-01, and downscaling keeps real phone photos fast and cheap | A genuinely slow single attempt can still take up to the hang-ceiling; the ~5s is met by typical latency, not a hard guillotine | Faster model tier / streaming in production |
| D-21 | **UI: server-rendered single page** | One page: an upload zone, an expected-values form (the 6 typed fields), one primary button, and a color-coded extracted-vs-expected results table with an overall banner; the Government Warning has no input (checked against the canonical text). Progressive-enhancement JS (filename/thumbnail/"Checking…" state) only — the plain form works with JS off | Meets the no-training / 73-year-old bar (NFR-03): one obvious action, no hunting; robust because the core works without JavaScript | A full-page reload clears the file input, so re-checking the same image after editing a value needs re-selecting it | JS fetch (no reload) or a richer role-based UI in production |

---

## C. Assumptions We *Must* Make (unavoidable — the app can't exist without deciding these)

| ID | Assumption | Why it's forced | Risk if wrong |
|---|---|---|---|
| MA-1 | **Application/expected data is entered into the app** (form for single, CSV for batch); it is **not** fetched from COLA. | There is no COLA integration; the expected values must come from somewhere. | Low — this is the stated scope. |
| MA-2 | **The canonical Government Warning is stored as a verified constant**, sourced from the current regulation (27 CFR 16.21) — **not typed from memory**. | Exact match needs a trusted reference string; a single wrong word breaks the very check we're grading on. | High if the stored text is inaccurate → sourced/verified at build time. |
| MA-3 | **Per-field match tolerances are fixed by rule** (brand = case/punctuation-insensitive; ABV = proof-equivalence; warning = exact). Concrete thresholds (committed): brand fuzzy 90/75, supporting 85/70, ABV ±0.15% ABV. | "Match" is undefined without explicit tolerance rules. | Medium — rules are drawn straight from the interviews. |
| MA-4 | **Batch pairing contract:** each image maps to one CSV row via a filename or ID column. | Something must tell the app which expected values go with which image. | Medium — mitigated by clear instructions + a downloadable CSV template. |
| MA-5 | **English-language labels only** for the prototype. | Extraction/normalization rules are language-specific; scope must be bounded. | Confirmed. English-only is implemented (the normalizer keeps a–z/0–9). Non-ASCII/accented values are detected and routed to NEEDS_REVIEW (special_character) rather than silently degraded. Risk: low. |
| MA-6 | **Cloud AI is acceptable for the deployed prototype**, with a local/Azure path documented for production. | The prototype must run somewhere reachable; TTB's firewall only constrains *their* network, not our demo host. | Low — explicitly reconciled in D-1. |
| MA-7 | **The deployed prototype is publicly reachable and effectively unauthenticated.** | Treasury must be able to open and test it without accounts (OOS-03). | Low for a POC; noted as a security trade-off (D-9). |
| MA-8 | Warning is matched to the stored canonical constant, not the agent's input value. | MR-04 says "against the stored canonical". | Low — agents may expect their entry to matter; documented. |
| MA-9 | "Exact" = exact characters including case in the body, not just wording. | Strictest defensible reading of MR-04 (D-13). | Medium — re-cased/reformatted-but-correct warnings FAIL; overridable. |
| MA-10 | The extractor delivers each field (esp. the warning) as a clean, bounded value — no trailing text scooped in. | Exact-match assumes the warning field isn't polluted (e.g. "CONTAINS SULFITES"). | Medium — pushed onto HANDOFF #3's extraction prompt. |
| MA-11 | The Government Warning is the last statement block on the label, so anchoring on the case-insensitive "government warning" text and taking to end captures it without vision bounding boxes | The prototype vision extractor returns fields, not coordinates | Low — true for standard TTB layouts; unusual layouts make the reads disagree → NEEDS_REVIEW |

---

## D. Trade-offs (stated plainly)

- **Speed vs. thoroughness.** We hit ~5s by keeping the AI's job narrow (transcribe
  only) and doing judgment in fast code. We deliberately do **not** run heavy image
  preprocessing (deskew, glare removal) that would add seconds.
- **Cloud (fast, easy, best image handling) vs. local (network-compatible, private,
  cheaper).** Prototype favors cloud for the demo; production favors local/Azure.
  This is a documented decision, not a silent one.
- **Determinism vs. flexibility.** Moving judgment out of the AI makes results
  repeatable and auditable but means we hand-write the matching rules.
- **Recall vs. precision on "Needs Review."** We accept flagging some clean labels
  (a little extra human work) to avoid ever auto-passing a bad one.
- **Batch cost vs. throughput.** Concurrency makes 300 labels usable in a demo but
  multiplies API calls; production would meter/queue this.
- **Simplicity vs. features.** The UI is intentionally minimal to meet the
  no-training bar, at the cost of power-user conveniences.
- **Literal-spec fidelity vs. real-world robustness:** matchers are built to the
  letter of MR-01/02/04; beyond-spec cases (subset brand names, volume-unit
  conversion) are deferred and documented, per CON-04.
- **Strict warning → false-FAIL bias:** correctly-worded but re-cased/reformatted
  warnings FAIL rather than pass. Consistent with recall-over-precision, but note
  it produces false FAILs, not just reviews. Each is shown with
  extracted-vs-canonical and is overridable.
- **Determinism → no model fallback:** real-world coverage is exactly what we
  encode; the deliberately-nasty test-label catalog is the safety net, not the
  matcher.
- **Latency is bounded primarily by typical model latency** (median ~2-3s on the
  catalog), not a hard 5s guillotine: retries are disabled and output/image size
  are capped so a slow call degrades to NEEDS_REVIEW at a hang-ceiling rather than
  ballooning, and large uploads are downscaled to stay within the interactive
  range and cut cost.

---

## E. Known Limitations of the Prototype (honest list for the README)

1. **Not production-secure.** No auth, no encryption-at-rest guarantees, no PII
   handling, no audit log. By design (CON-02, OOS-02).
2. **No COLA integration.** Expected values are entered, not fetched (OOS-01).
3. **Font-forensics is best-effort.** Bold-weight and precise "too small / buried"
   detection are surfaced as *Needs Review* signals, not rigorous measurements (D-5).
4. **AI transcription is non-deterministic.** Rare mis-reads possible; mitigated by
   low temperature, structured output, verbatim-warning prompting, and the
   Needs-Review escape hatch. It is a *decision aid*, not an infallible authority.
5. **Batch scale is demo-grade.** Concurrency + streaming handle a realistic 200–300
   demo; sustained high volume would need a queue/worker system.
6. **Image robustness is bounded.** Moderate glare/angle/lighting handled by the
   vision model; severely degraded images go to Needs Review rather than being
   force-read (matches current agent practice).
7. **English-only.** Non-English labels out of scope (OOS-04).
8. **Cost not optimized.** Each verification is an API call; no caching/batching
   economics tuned for the prototype.
9. **Accented/non-ASCII values** are detected and routed to a special_character
   review, not silently mis-matched (English-only boundary).
10. **Every result carries a reason code** enabling triage/grouping of reviews
    and failures.
11. **The all-caps prefix check is whitespace-tolerant:** the matched
    `GOVERNMENT WARNING` prefix is whitespace-normalized before the case
    comparison, so a correctly-capitalized prefix that wraps across lines is not
    false-failed. Case remains strict (title case fails).
12. **The image quality gate is heuristic** (Laplacian-variance blur + std-dev
    blank check) — a cheap pre-flight guard, not a calibrated image-quality
    model; thresholds are config-tunable (QUALITY_BLUR_THRESHOLD /
    QUALITY_BLANK_STDDEV).
13. **The literal-OCR warning cross-check requires the Tesseract binary;** where
    it is absent (e.g. local dev without the install) the warning verdict falls
    back to the vision transcription (prompt-guarded only). The deployed
    container installs tesseract-ocr so the cross-check is always active in
    production.
14. **Single-label latency is dominated by the vision model;** the heaviest labels
    approach ~5s and rely on typical latency (not a hard cap) to meet NFR-01. A
    per-request hang-ceiling prevents indefinite waits by degrading a stalled call
    to NEEDS_REVIEW.
15. **The single-label UI is server-rendered** (full-page form POST); after a
    result the browser clears the file input, so re-checking the same image with
    edited expected values requires re-selecting the image. Minor; a no-reload JS
    submit is the production refinement.

---

## F. Open Questions (please confirm — cheap to change now, expensive later)

| # | Question | My recommended default (proceeds if you say nothing) |
|---|---|---|
| Q-1 | **English-only** for the prototype? (MA-5) | **Confirmed — English only.** |
| Q-2 | **Batch input format:** CSV template + images matched by filename? | Yes — provide a downloadable CSV template with an `image_filename` column. |
| Q-3 | Do you want the **soft font-size/bold "Needs Review" signal** (D-5), or drop it entirely to keep the core clean? | Include it as a soft signal only — it shows attention to the buried requirement without risking the core. |
| Q-4 | Any need to **limit access** to the deployed demo (a shared password), or fully open? | Fully open for easy testing; add a shared password only if you'd prefer. |
| Q-5 | Confirm **stack** (Python + FastAPI + cloud vision + Docker + Fly.io)? | Proceed as-is unless you object. |

Decisions D-12 (blank→review) and D-13 (strict warning) resolved.

---

*Next step after this doc is agreed: architecture (component diagram, request/data
flow, the batch concurrency model, and the file/module layout).*

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
