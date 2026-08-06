# ARCHITECTURE — TTB AI Label Verification Prototype

**Status:** Design + scaffold checkpoint (no business logic implemented) ·
**Owner:** Testing Manager · **Source of truth:** `README.md`, `REQUIREMENTS.md`,
`ASSUMPTIONS_AND_TRADEOFFS.md`

> This blueprint is deliberately implementation-free. Every code file in the repo
> is a **stub** (docstring + signatures). This document describes what those stubs
> become. It supersedes and updates decisions **D-1** and **D-6** and retires
> limitation **E.8** in `ASSUMPTIONS_AND_TRADEOFFS.md` (see §8).

---

## 1. Overview

The app helps a TTB compliance agent verify that an alcohol-beverage **label**
matches the **application data** for that product. The agent supplies a label
image plus the expected field values (a form for one label, a CSV for a batch);
the system reads the label with AI/OCR and returns a **per-field PASS / FAIL /
NEEDS_REVIEW** verdict showing the extracted value next to the expected value.

The organizing principle is **"AI reads, code judges."** The extractor's *only*
job is to transcribe the label into structured fields. **Every** comparison —
fuzzy brand match, ABV/proof equivalence, exact Government Warning match — is done
by deterministic Python against stored rules. This keeps verdicts auditable,
testable, and explainable, which a compliance tool requires; a model is never
asked to make the compliance call.

The second organizing idea is the **Azure production spine**. The app is
containerized so the **same image** runs on **Fly.io** for the public prototype
and drops into TTB's **existing Azure tenant** (Azure Container Apps / App Service
for Linux) for production. In production the cloud-vision call swaps — by
**config, not by rewrite** — to **Azure OpenAI** or **Azure AI Document
Intelligence** over a private endpoint, which also clears TTB's outbound-ML-endpoint
firewall block (the network/IT constraint noted in the brief). The prototype deliberately picks a
model with an **Azure twin** (the GPT-5.6 family — Terra single-label, Luna batch —
runs both as a public API and inside Azure OpenAI) so prototype → production is a
config change.

---

## 2. Component Diagram

```
                          ┌──────────────────────────────────────────────┐
                          │                Browser UI                    │
                          │   index.html — one big upload zone, one       │
                          │   primary button, a results table. app.js.    │
                          └───────────────┬──────────────────────────────┘
                                          │  HTTP (multipart upload) + SSE
                                          ▼
                          ┌──────────────────────────────────────────────┐
                          │                  FastAPI                      │
                          │   main.py — routes: /verify (single),         │
                          │   /batch (many, streamed), / (serves UI)      │
                          └───────┬───────────────────────────┬──────────┘
                                  │ single                     │ batch
                                  ▼                            ▼
                   ┌──────────────────────┐      ┌──────────────────────────────┐
                   │  verify.py           │      │  batch.py (Batch runner)     │
                   │  orchestrator        │      │  pre-screen → cache/dedup →  │
                   │  (fail-fast, ~5s)    │      │  capped worker pool → SSE    │
                   └──────────┬───────────┘      └──────────────┬───────────────┘
                              │                                 │
                              ▼                                 ▼
                   ┌───────────────────────────────────────────────────────────┐
                   │              Extractor Router (router.py)                 │
                   │   selects engine: single = premium, batch = cheap/local   │
                   │   failover chain: primary → backup → NEEDS_REVIEW         │
                   └───┬──────────────────┬────────────────────┬──────────────┘
                       ▼                  ▼                     ▼
             ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
             │ vision_llm.py    │ │ (backup provider)│ │ ocr_local.py         │
             │ premium cloud    │ │ via same         │ │ cheap / local OCR    │
             │ vision (single)  │ │ interface        │ │ (batch + prod path)  │
             └────────┬─────────┘ └────────┬─────────┘ └──────────┬───────────┘
                      │                    │                      │
                      └──────────┬─────────┴──────────────────────┘
                                 │  structured fields (+ ok / confidence flag)
                                 ▼
                   ┌───────────────────────────────────────────────────────────┐
                   │        Matcher — DETERMINISTIC (matching/rules.py)        │
                   │  match_brand · match_abv · match_warning · match_supporting│
                   │  driven by the field registry (fields.py); normalize.py;   │
                   │  canonical.py (stored Government Warning)                   │
                   └──────────────────────────┬────────────────────────────────┘
                                              ▼
                              ┌──────────────────────────────┐
                              │  Result: PASS / FAIL /        │
                              │  NEEDS_REVIEW  (models.py)    │
                              └──────────────────────────────┘

   NEEDS_REVIEW is the safe fallback OUT OF THE ROUTER: if no provider can read the
   label (all engines fail / time out), the router returns NEEDS_REVIEW — never a
   guessed PASS or FAIL.
```

---

## 3. Single-Label Flow (the ~5s interactive path)

The ~5-second bar (NFR-01) is the hard constraint. Budget is annotated per step;
the single path **fails fast** — it does **not** retry serially across providers,
because serial cross-provider retries would blow the budget.

| Step | What happens | Budget note |
|---|---|---|
| 1. Upload | Agent submits one label image + form values (`FR-01`). | — |
| 2. Validate | `main.py` checks file type/size (`MAX_UPLOAD_MB`); malformed → clear message, no crash (`NFR-06`). | ~instant |
| 3. Route | `router.py` selects the **premium cloud vision** engine for single labels. | ~instant |
| 4. Extract | `vision_llm.py` transcribes the label to structured fields with a **fail-fast timeout** (`SINGLE_LABEL_TIMEOUT_S`). | **bulk of the ~5s** |
| 5. Match | `matching/rules.py` runs each field's deterministic rule against the expected value. | milliseconds (local) |
| 6. Assemble | `verify.py` builds a `LabelResult` — per field: extracted, expected, rule, verdict (`FR-03/04`). | ~instant |

**On extractor failure or timeout → `NEEDS_REVIEW`** for the affected field(s),
returned immediately. No serial retry. This is how the 5-second bar and resilience
coexist: when the AI can't deliver in time, a human takes over, never a guess.

---

## 4. Batch Flow & Concurrency Model

Batch is governed by **throughput/progressiveness (NFR-02)**, not the 5s single
bar (tension **T-1** in `REQUIREMENTS.md`). Per-item latency is relaxed, so batch
uses the **cheap/local engine** and **may retry serially** across providers.

```
CSV + image files
      │
      ▼
1. Pair        — match each image to its CSV row by the `image_filename` column (D-7, MA-4).
      │           Unmatched rows / orphan images are flagged, not fatal.
      ▼
2. Pre-screen  — reject blank/invalid/oversized files BEFORE spending an extraction
      │           call (cost guard). Rejected items → NEEDS_REVIEW with a reason.
      ▼
3. Dedup/cache — cache.py hashes each image; identical images reuse the prior result
      │           (image-hash dedup) instead of re-extracting (cost guard).
      ▼
4. Extract     — concurrent extraction on the CHEAP/LOCAL engine via a CAPPED worker
      │           pool (`MAX_CONCURRENCY`). Ambiguous items MAY escalate to premium.
      │           Batch MAY retry serially across providers (latency relaxed).
      ▼
5. Match       — per-item deterministic matching (same rules as single).
      │
      ▼
6. Stream      — each item's result is pushed to the browser via SSE the moment it
      │           finishes (app.js appends a row). Agent reviews before batch ends.
      ▼
7. Summarize   — final BatchResult: counts of PASS / FAIL / NEEDS_REVIEW (FR-11).
```

**Caps & ceilings:** `MAX_BATCH_ITEMS` bounds how many pairs one submission
accepts; `PER_BATCH_COST_CEILING` stops/flags a batch whose projected cost exceeds
the ceiling (informational in the prototype). 300 sequential 5s calls would be
~25 minutes (D-6); concurrency + streaming make a realistic 200–300 demo usable.

---

## 5. Result Model

Every field resolves to exactly one of three states (`models.py :: ResultState`):

- **PASS** — extracted value satisfies the expected value under that field's rule.
- **FAIL** — extracted value is present and readable but does **not** satisfy the rule.
- **NEEDS_REVIEW** — the system could not confidently read or judge the field.

The system is **biased against a false PASS** — the worst failure mode in
compliance. Low confidence, unreadable text, a legitimately absent field that
can't be adjudicated, **or an unavailable extractor** all resolve to
`NEEDS_REVIEW`, never a guessed PASS/FAIL. `NEEDS_REVIEW` therefore does double
duty: it is both the low-confidence verdict **and the resilience fallback** — if
the AI is unavailable, the field goes to a human, matching current agent practice
of asking for a better image.

Each result also carries the **extracted value, expected value, and the rule
applied** ("show the work") so the agent stays in control (Dave's "you need
judgment") — never a bare verdict (`FR-04`).

---

## 6. Extractor Interface & Provider Strategy

A single **abstract `Extractor` interface** (`extraction/base.py`) defines one
operation: `extract(image_bytes) -> structured fields` plus an **ok / confidence
flag** so the router can decide whether to accept, fail over, or escalate. Three
concrete implementations sit behind it:

1. **`vision_llm.py`** — premium cloud vision extractor. Prototype **primary** for
   single labels; robust to phone-photo glare/angle; hits ~5s.
2. **`ocr_local.py`** — cheap/local OCR extractor. The **batch** engine and the
   **production-compatible** path (runs where outbound ML endpoints are blocked).
3. **`router.py`** — not an extractor itself but the **selection + failover**
   layer that chains providers behind the same interface.

**Dual-engine split:** single = premium, batch = cheap/local, with ambiguous
batch items escalating to premium only when needed. **Providers are
config-selected, never hardcoded** (`PRIMARY_MODEL`, `BACKUP_MODEL`,
`BATCH_MODEL`). The **Azure twin** requirement means the prototype's primary model
has an Azure OpenAI equivalent, so prototype → production is config-only.

---

## 7. Resilience & Failover — *"what if the AI is down?"*

The router implements one chain: **primary → backup → `NEEDS_REVIEW`.**

- **Single-label fails FAST.** One primary attempt within `SINGLE_LABEL_TIMEOUT_S`;
  on failure/timeout the field goes straight to `NEEDS_REVIEW`. Serial
  cross-provider retries are forbidden here because they violate the ~5s bar.
- **Batch may retry SERIALLY.** Because per-item latency is relaxed, a failed batch
  item may fall through primary → backup before landing on `NEEDS_REVIEW`.
- **The system never crashes and never guesses.** Every failure mode has a defined
  terminal state (`NEEDS_REVIEW`), satisfying graceful degradation (`NFR-05`) and
  robust input handling (`NFR-06`).
- **Production failover** uses **Azure regional redundancy** and/or **Document
  Intelligence** as the backup engine inside the tenant — the same interface, a
  different configured provider.

---

## 8. Cost Model — *"cost savings" and "300 calls is wasteful"*

Because the AI **only transcribes**, a **cheaper/smaller** vision or OCR engine
suffices for most work — full model "judgment" is unnecessary since judgment lives
in deterministic code. The prototype's cost controls:

- **Dual-engine split** — premium only where it earns its cost (single, imperfect
  phone photos); cheap/local for the bulk of batch work.
- **Image-hash dedup/cache** (`cache.py`) — identical images are never extracted twice.
- **Pre-screen** — blank/invalid files are rejected **before** spending a call.
- **Concurrency cap** (`MAX_CONCURRENCY`) and **per-batch cost ceiling**
  (`PER_BATCH_COST_CEILING`).
- **Escalate-ambiguous-only** — cheap engine first; premium only when the cheap
  read is ambiguous.
- **Providers/prices are chosen at build time — never hardcoded anywhere.**

> **This section updates decisions D-1 and D-6 and retires limitation E.8** in
> `ASSUMPTIONS_AND_TRADEOFFS.md`. D-1 (single cloud LLM engine) becomes the
> dual-engine, config-selected, Azure-twin strategy above. D-6 (concurrent batch)
> gains the pre-screen, dedup/cache, cost ceiling, and escalate-only controls.
> E.8 ("Cost not optimized") is retired: cost is now an explicit, designed-for
> concern rather than a noted limitation.

---

## 9. Extensible Field Set

Which fields are checked, and by which rule, is driven by a **field registry**
(`fields.py`) — a data structure mapping each field to its rule type (fuzzy /
abv-equivalence / exact-warning / present-normalized). Adding TTB's proposed
**Alcohol Facts** panel or an **allergen disclosure** later means adding a
registry entry, **not** rewriting the matcher or the orchestrator. New label
elements become **data, not a code rewrite**.

---

## 10. Module Layout

```
ttb-label-verify\
├── ARCHITECTURE.md                 this document
├── app\
│   ├── __init__.py
│   ├── main.py                     FastAPI app; routes for single + batch verify; serves the UI page
│   ├── config.py                   typed settings from env vars (.env.example knobs)
│   ├── models.py                   pydantic models + ResultState enum; FieldResult, LabelResult, BatchResult
│   ├── fields.py                   field registry: which fields exist + which rule each uses
│   ├── cache.py                    image-hash dedup/cache (batch cost guard); in-memory for prototype
│   ├── verify.py                   single-label orchestrator: router → extractor → matchers → LabelResult
│   ├── batch.py                    batch runner: pair, pre-screen, dedup, capped concurrent extract, stream, summarize
│   ├── extraction\
│   │   ├── __init__.py
│   │   ├── base.py                 abstract Extractor interface (+ ok/confidence flag for failover)
│   │   ├── router.py               engine selection + failover chain primary→backup→NEEDS_REVIEW
│   │   ├── vision_llm.py           premium cloud vision extractor (stub)
│   │   ├── ocr_local.py            cheap/local OCR extractor (stub) — batch + production path
│   │   └── prompt.py               extraction prompt text + expected JSON schema (verbatim-warning instruction)
│   ├── matching\
│   │   ├── __init__.py
│   │   ├── rules.py                deterministic field matchers: match_brand, match_abv, match_warning, match_supporting
│   │   ├── normalize.py            text-normalization helpers (case, punctuation, whitespace)
│   │   └── canonical.py            stored canonical Government Warning constant (placeholder + TODO)
│   ├── templates\
│   │   └── index.html              one page: big upload zone, one primary button, results table
│   └── static\
│       ├── style.css               minimal, high-contrast, large-font (no-training / 73-year-old bar)
│       └── app.js                  upload handling; batch appends rows via SSE as they arrive
├── tests\
│   ├── __init__.py
│   ├── test_matching.py            test stubs for each matcher (graded core tested here later)
│   └── fixtures\.gitkeep
├── test_labels\.gitkeep            generated test label images go here later
├── sample_data\batch_template.csv  header row only (the batch pairing contract)
├── requirements.txt
├── Dockerfile                      python slim, install reqs, run uvicorn
├── fly.toml                        minimal placeholder; real values at deploy time
├── .env.example                    config knobs (see below)
├── .gitignore
└── README.md                       existing deliverable — left untouched
```

---

## 11. Technical Choices & Why

- **FastAPI (Python).** Async request handling maps directly onto the batch
  concurrency model (capped worker pool + SSE streaming). Fast to build; strong AI
  ecosystem. Ties to the "appropriate technical choices" grading criterion.
- **Deterministic matching in plain Python.** Verdicts must be auditable and
  repeatable. The exact Government Warning check in particular **cannot** be model
  judgment — a single wrong word must FAIL — so judgment lives in code, separate
  from the AI, and is unit-testable.
- **Swappable + resilient extractor.** One interface, config-selected providers, a
  failover chain. This is what makes "what if the AI is down" and "cheaper engine"
  answerable without a rewrite.
- **SSE (Server-Sent Events).** The simplest fit for one-directional server→client
  streaming of batch results; no WebSocket complexity for a progressive-append UI.
- **Docker as the portability unit into Azure — the *real* reason.** The container
  is not a convenience; it is the mechanism by which the **same image** moves from
  Fly.io to TTB's Azure tenant. This is the spine of the whole production story.
- **Python vs. their .NET COLA.** The brief explicitly permits any language
  (`CON-05`). A Linux container is equally at home in TTB's Azure tenant regardless
  of language, so language choice is a non-issue for deployment — while Python
  gives the best AI/vision ecosystem for the transcription work. There is no COLA
  integration in scope (`CON-01`), so matching COLA's stack buys nothing here.

---

## 12. Requirements Mapping

| Module | Satisfies |
|---|---|
| `main.py` | FR-01, FR-02, FR-03, NFR-03, NFR-06 |
| `verify.py` | FR-02, FR-03, FR-04, NFR-01 (fail-fast ~5s) |
| `batch.py` | FR-10, FR-11, NFR-02 (progressive), T-1 |
| `models.py` | FR-03, FR-09 (three-state result) |
| `fields.py` | Extensibility (Alcohol Facts / allergen as data) |
| `cache.py` | Cost model; NFR-02 throughput |
| `extraction/base.py` + `router.py` | NFR-05 (graceful degradation), NFR-06, D-1 (updated) |
| `extraction/vision_llm.py` | NFR-01, NFR-05 (imperfect images) |
| `extraction/ocr_local.py` | ASM-02 (local/Azure production path), cost model |
| `extraction/prompt.py` | MR-04/05 (verbatim-warning transcription) |
| `matching/rules.py` | FR-05, FR-06, FR-07, FR-08, MR-01…MR-05, CON-04 (clean core) |
| `matching/normalize.py` | MR-01 (case/punct-insensitive brand) |
| `matching/canonical.py` | MR-04 (exact warning), ASM-03/MA-2 |
| `templates/` + `static/` | NFR-03 (no-training UI), NFR-04 |

Resilience & cost specifically map to **NFR-05** (graceful degradation),
**NFR-06** (robust input), **NFR-01/02** (latency/throughput), and **CON-04**
(clean core kept clean by pushing config/cost concerns to the edges).

---

## 13. `.env.example` Knobs

```
# --- Extraction providers (config-selected; no logic this pass) ---
PRIMARY_MODEL=gpt-5.6-terra   # premium cloud vision model for single-label (Azure OpenAI twin; GPT-5.6 Terra)
BACKUP_MODEL=             # failover provider/model
BATCH_MODEL=              # cheap/local engine used for batch (e.g. ocr-local)
API_KEY=                  # cloud provider key (prototype only; never a real secret in the repo)
# --- Concurrency & cost guards ---
MAX_CONCURRENCY=          # capped worker pool size for batch
MAX_BATCH_ITEMS=          # hard cap on items accepted per batch submission
PER_BATCH_COST_CEILING=   # stop/flag a batch if projected cost exceeds this (informational in the prototype)
MAX_UPLOAD_MB=            # per-file upload size cap
SINGLE_LABEL_TIMEOUT_S=   # fail-fast budget for single-label; on exceed -> NEEDS_REVIEW
# --- Access (optional, OFF by default) ---
DEMO_PASSWORD=            # optional shared password to limit public-demo abuse/cost
```

`config.py` exposes these as a typed settings object (read env; no behavior this pass).

---

## 14. Deferred to Later Phases

- Real extraction logic (any actual AI/OCR call) — **none in this pass**.
- Real matching/verification logic — matchers are stubs.
- Batch implementation (pairing, pre-screen, dedup, pool, SSE wiring).
- The soft warning **font-size/bold "buried text" signal** (MR-06, D-5) → NEEDS_REVIEW.
- Local-OCR wiring and its dependencies.
- Second-provider failover wiring.
- Deployment (Docker build, Fly.io, GitHub, Azure).
- Optional shared-password enforcement.
