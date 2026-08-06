# Software Requirements Specification (SRS)
## TTB AI Label Verification Prototype

**Status:** Draft for review · **Owner:** Testing Manager · **Source:** derived from the R1–R35 requirements list (traced in §13)

---

## 1. Purpose & Scope

This document formalizes the requirements for a prototype web application that
helps TTB compliance agents verify an alcohol beverage label against its
application data. The agent supplies a label image and the expected field values;
the system reads the label using AI/OCR and returns a per-field PASS/FAIL result.

Scope is a **standalone proof-of-concept** — no integration with the production
COLA system, no handling of real PII. The prototype is delivered as source code
plus a publicly testable deployed URL.

---

## 2. Glossary

| Term | Meaning |
|---|---|
| **Application data** | The expected field values an agent enters/uploads (brand, ABV, warning, etc.). |
| **Label** | The uploaded artwork/photo of the physical label to be checked. |
| **Government Warning** | The mandatory, statutorily-fixed TTB health warning statement. |
| **Match** | An automated determination that an extracted label value satisfies the expected value under that field's rule (§5). |
| **Needs Review** | A result state where the system could not confidently read or judge a field and defers to a human. |
| **Batch** | A single submission containing many label + application pairs. |

---

## 3. Priority Scheme (MoSCoW)

| Code | Meaning |
|---|---|
| **M — Must** | Core, graded, or a hard constraint. The prototype fails without it. |
| **S — Should** | High-value, strongly expected; include unless it risks the core. |
| **C — Could** | Bonus. Include only if the core is solid. |
| **W — Won't** | Explicitly out of scope for this prototype. |

**Verification methods:** *Demo* (show it working), *Test* (pass/fail cases),
*Measure* (timed/quantified), *Inspect* (code/UI review), *DocReview* (present in docs).

---

## 4. Functional Requirements (FR)

| ID | Pri | The system shall… | Verify | Trace |
|---|---|---|---|---|
| FR-01 | M | accept a **label image** and the corresponding **application data** as inputs. | Demo | R3 |
| FR-02 | M | verify the label content against the application data and report the result. | Test | R1, R2 |
| FR-03 | M | present the outcome as a clear **per-field PASS / FAIL**. | Demo | R4 |
| FR-04 | M | display, for each field, the **value extracted from the label** next to the **expected value**, so the agent can judge. | Demo | R19 |
| FR-05 | M | verify the **Brand Name** field. | Test | R5 |
| FR-06 | M | verify the **Alcohol Content** field (ABV and/or proof). | Test | R6, R9 |
| FR-07 | M | verify the **Government Warning** statement. | Test | R7 |
| FR-08 | S | verify **supporting fields**: class/type, net contents, producer name/address, country of origin (imports). | Test | R8 |
| FR-09 | M | when a field cannot be read/extracted, mark it **Needs Review** rather than passing it or crashing. | Test | R18 |
| FR-10 | S | accept a **batch** of many label + application pairs in a single submission. | Demo | R16 |
| FR-11 | S | produce a **per-item result** for every batch entry plus a **batch summary** (counts of pass / fail / needs-review). | Demo | R17 |
| FR-12 | C | allow the agent to **override** an automated result (human-in-the-loop). | Demo | R19 |
| FR-13 | S | categorize each NEEDS_REVIEW / FAIL result with a machine-readable reason code (blank, unreadable, borderline, special-character, warning-prefix, wording, mismatch, ...) to support triage and grouping. | Test | stakeholder efficiency |

---

## 5. Matching & Verification Rules (MR)

The field-comparison logic. This section is the functional heart of the grading —
the brand-vs-warning distinction is deliberate and must be preserved.

| ID | Pri | Rule | Verify | Trace |
|---|---|---|---|---|
| MR-01 | M | **Brand name** comparison is **case- and punctuation-insensitive** (normalized/fuzzy). `STONE'S THROW` shall match `Stone's Throw`. | Test | R10 |
| MR-02 | M | **ABV/proof equivalence**: proof = 2 × ABV%. `45% Alc./Vol.` shall satisfy an expected `45%` **or** `90 proof`. | Test | R9 |
| MR-03 | S | Where a beverage type **legitimately omits** ABV, absence shall not be recorded as a failure. | Test | R9b |

> **Decided behavior (D-12):** a blank/absent ABV (nothing expected, nothing on
> the label) → NEEDS_REVIEW with reason `blank_expected`, not PASS — which still
> satisfies MR-03 ("absence shall not be recorded as a failure"), since a review
> is not a failure. A human confirms whether the omission is legitimate.
| MR-04 | M | **Government Warning** text shall be matched **exactly** (word-for-word) against the stored canonical TTB statement. | Test | R11 |
| MR-05 | M | The `GOVERNMENT WARNING:` prefix shall be verified as **all caps**; title case (`Government Warning`) shall FAIL. | Test | R11, R12 |
| MR-06 | C | The system shall attempt to detect **format evasion** on the warning — missing bold, disproportionately small font, or buried/tiny text — and FAIL such labels. | Test | R12 |

**Acceptance detail for MR-01:** pairs differing only in letter case, apostrophes,
hyphens, ampersand-vs-"and", or internal spacing return MATCH; a genuinely
different brand returns FAIL. Values containing non-ASCII/accented characters that
do not normalize to a match are routed to NEEDS_REVIEW (`special_character`),
consistent with the English-only scope (OOS-04 / MA-5).

**Acceptance detail for MR-04/05:** the extracted warning is normalized only for
whitespace, then compared character-for-character to the canonical text; any
wording change, omission, or a non-all-caps prefix returns FAIL. Whitespace
variation *within the prefix* (a line break or extra spaces between GOVERNMENT and
WARNING) does not by itself fail the all-caps check — only a genuine letter-case
difference fails. As an additional safeguard the prototype cross-checks the vision
transcription of the warning against a literal OCR (Tesseract) read of the same
image; if the two reads disagree on wording (beyond a fuzzy tolerance) or on the
all-caps prefix, a warning that would otherwise PASS is routed to NEEDS_REVIEW. The
strict character-for-character verdict itself is unchanged — the cross-check only
makes a PASS more conservative, never a FAIL less so.

**Note on MR-06:** exact text and all-caps checks (MR-04/05) work from OCR text
alone and are **Must**. Bold-weight and font-size/"buried text" detection require
layout/typography analysis and are therefore isolated as **Could** — see §12.

---

## 6. Non-Functional Requirements (NFR)

| ID | Pri | Requirement | Verify | Trace |
|---|---|---|---|---|
| NFR-01 | M | **Single-label latency:** a single verification returns results in **~5 seconds** or less under normal conditions. | Measure | R13 |
| NFR-02 | S | **Batch throughput:** batch results **populate progressively** so the agent can begin reviewing before the whole batch finishes; the agent is never blocked waiting for all items. | Demo | R13, R16 |
| NFR-03 | M | **Usability:** the interface is operable by a non-technical, first-time user with **no training**; the primary action is immediately visible ("no hunting for buttons"). Benchmark: a 73-year-old. | Inspect | R14 |
| NFR-04 | M | **Net time-saver:** the workflow reduces effort versus manual review and adds no friction. | Inspect | R15 |
| NFR-05 | S | **Graceful degradation:** on imperfect images (glare, angle, lighting) the system either reads them or clearly flags for a better image — it never crashes. | Test | R18, R25 |
| NFR-06 | M | **Robust input handling:** malformed or unsupported uploads produce a clear message, not an error or crash. | Test | R18, R32 |

**Note on NFR-01:** Single-label latency is dominated by the vision model; measured
median ~2-3s on the test catalog. The client disables retries and applies a
per-request hang-ceiling timeout so a stalled call degrades to NEEDS_REVIEW rather
than exceeding the budget indefinitely, and large images are downscaled before the
call to keep real photos within the budget and reduce cost.

**Note on NFR-05:** A pre-extraction image quality gate (Laplacian-variance blur +
std-dev blank check) routes unreadable uploads to NEEDS_REVIEW ("request a better
image") before an API call is made, saving cost and matching current agent practice.

---

## 7. Constraints (C)

| ID | Constraint | Trace |
|---|---|---|
| CON-01 | Standalone prototype; **no COLA integration**. | R20 |
| CON-02 | **No real PII** stored; minimal/no persistence; security is not production-hardened (and this is documented). | R21 |
| CON-03 | The deployed prototype must be **publicly reachable** by Treasury for testing (target: Fly.io). | R28 |
| CON-04 | Prioritize a **clean working core** over ambitious-but-incomplete features; document trade-offs. | R22 |
| CON-05 | Free choice of language/framework/library; **the technical choices are themselves evaluated**. | R24 |

---

## 8. Assumptions (A)

| ID | Assumption | Trace |
|---|---|---|
| ASM-01 | Application/expected data is supplied to the app (typed into a form and/or uploaded as a structured file); it is **not** pulled from COLA. | R3, R20 |
| ASM-02 | The deployed prototype may use a **cloud** AI/OCR service. TTB's production network blocks some outbound ML endpoints, so a **local/offline extraction path** is documented as the production-compatible alternative. This local-vs-cloud trade-off is written up. | R23 |
| ASM-03 | The **canonical Government Warning** is the fixed TTB statutory wording, stored as the reference string. | R7, R11 |
| ASM-04 | **Test labels** (including deliberately non-compliant ones) will be generated/sourced, AI image generation permitted. | R26 |
| ASM-05 | Prototype targets **English-language** labels. *(Confirm — flagged for review.)* | scoping |

---

## 9. Out of Scope / Non-Goals (Won't)

| ID | Excluded from this prototype |
|---|---|
| OOS-01 | COLA system integration. |
| OOS-02 | Production security, PII handling, and document-retention compliance. |
| OOS-03 | User accounts / authentication (beyond anything trivial). |
| OOS-04 | Non-English labels. |
| OOS-05 | Full typographic/forensic font analysis beyond the basic evasion checks in MR-06. |

---

## 10. Deliverables (D)

| ID | Deliverable | Trace |
|---|---|---|
| DEL-01 | **GitHub repository** (`scheduler-lembu`) — all source code, README with setup + run instructions, and brief docs of approach / tools / assumptions. | R27 |
| DEL-02 | **Deployed application URL** — a working prototype Treasury can access and test. | R28 |

---

## 11. Acceptance Criteria — Definition of Done

The prototype is done when **all** of the following hold:

1. An agent uploads **one** label image + its application data and receives a
   **per-field PASS / FAIL** (FR-03) showing **extracted vs expected** values
   (FR-04) in **≤ ~5 seconds** (NFR-01).
2. **Brand** matches fuzzily (MR-01), **ABV/proof** matches with equivalence
   (MR-02), and the **Government Warning** is checked exactly with an all-caps
   prefix (MR-04/05).
3. An agent uploads a **batch** of many pairs and receives **per-item results +
   a summary** (FR-10/11) that populate **progressively** (NFR-02).
4. **Unreadable / malformed** inputs are **flagged, not crashed** (FR-09, NFR-06).
5. The UI is usable **without training** (NFR-03).
6. The **GitHub repo** (DEL-01) and **deployed URL** (DEL-02) are live, with the
   approach/assumptions writeup — including the cloud-vs-local decision (ASM-02).

---

## 12. Known Tensions & Risks

| # | Tension | Resolution at requirement level |
|---|---|---|
| T-1 | **Batch (FR-10/11) vs 5-second latency (NFR-01).** 300 labels cannot each get a sequential 5-second call. | NFR-01 is scoped to **single-label** interactive use; batch is governed by **NFR-02 (progressive/throughput)**. Final mechanism decided at architecture stage. |
| T-2 | **Warning format-evasion detection (MR-06)** needs bold-weight and font-size analysis — the highest-effort item. | Split: exact-text + all-caps (MR-04/05) are **Must**; font/size/"buried" detection is isolated as **Could (MR-06)**. |
| T-3 | **Cloud vs local AI (ASM-02)** affects both speed and the network constraint. | Treated as a **documented decision**, not a silent one; prototype may use cloud, production path noted as local. |

---

## 13. Traceability (original R-ID → formal ID)

| R-ID | Formal ID | | R-ID | Formal ID |
|---|---|---|---|---|
| R1, R2 | FR-02 | | R16 | FR-10 |
| R3 | FR-01 | | R17 | FR-11 |
| R4 | FR-03 | | R18 | FR-09 / NFR-06 |
| R5 | FR-05 | | R19 | FR-04 / FR-12 |
| R6 | FR-06 | | R20 | CON-01 / ASM-01 |
| R7 | FR-07 / MR-04 | | R21 | CON-02 |
| R8 | FR-08 | | R22 | CON-04 |
| R9 | MR-02 | | R23 | ASM-02 |
| R9b | MR-03 | | R24 | CON-05 |
| R10 | MR-01 | | R25 | NFR-05 |
| R11 | MR-04 / MR-05 | | R26 | ASM-04 |
| R12 | MR-05 / MR-06 | | R27 | DEL-01 |
| R13 | NFR-01 / NFR-02 | | R28 | CON-03 / DEL-02 |
| R14 | NFR-03 | | R29–R34 | Grading lens (all §4–§6) |
| R15 | NFR-04 | | R35 | Independent gap-filling (ASM-*) |
