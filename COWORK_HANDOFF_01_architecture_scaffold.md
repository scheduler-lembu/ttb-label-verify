# COWORK HANDOFF #1 — Architecture + Project Scaffold

> **This is the definitive HANDOFF #1.** If an earlier draft of this handoff
> exists in the folder, replace it with this one. This version folds in three
> refinements agreed after the first draft: the **Azure production spine**, the
> **resilient/swappable extractor** (failover), and the **single-vs-batch cost
> split**. These update decisions **D-1** and **D-6** and retire limitation
> **E.8** in `ASSUMPTIONS_AND_TRADEOFFS.md`.

---

## START HERE (do this first, before anything else)
Read these four files **in full** before writing anything. They are the locked
source of truth for this project:
- `C:\Users\finan\Documents\ttb-label-verify\README.md`  (project background & stakeholder context)
- `C:\Users\finan\Documents\ttb-label-verify\REQUIREMENTS.md`  (formal requirements — FR / MR / NFR, priorities, traceability)
- `C:\Users\finan\Documents\ttb-label-verify\ASSUMPTIONS_AND_TRADEOFFS.md`  (decisions, assumptions, trade-offs, limitations)
- `C:\Users\finan\Documents\ttb-label-verify\Working_Document_List.txt`  (which docs we're keeping and when)

---

## OBJECTIVE
Set up the project. Produce a clear architecture document, then create the empty
repository skeleton that matches it. **Do NOT implement any business logic in this
pass** — no AI calls, no matching code, no deployment. This is a design + scaffold
checkpoint that will be reviewed before core code is written. Every code file is a
**stub** (docstring + signatures with `pass` or `raise NotImplementedError`).

---

## LOCKED DECISIONS (already agreed — do not re-litigate; build to these)

**Stack & core principle**
- **Stack:** Python + **FastAPI** backend; deterministic matching in plain Python;
  minimal server-rendered frontend (Jinja templates + a little vanilla JS);
  **Docker**; prototype deploy target **Fly.io**.
- **"AI reads, code judges":** the extractor ONLY transcribes the label into
  structured fields. ALL comparison/matching is done by deterministic Python
  against stored rules. These two concerns live in separate modules.
- **Result model — three states:** every field is `PASS`, `FAIL`, or
  `NEEDS_REVIEW`. Low confidence, unreadable, OR extractor-unavailable →
  `NEEDS_REVIEW`, never a guessed PASS/FAIL.

**Per-field rules** (design for them now; implement later)
- Brand name → fuzzy/normalized (case- and punctuation-insensitive).
- Alcohol content → ABV/proof equivalence (proof = 2 × ABV%).
- Government Warning → EXACT match to a stored canonical constant +
  `GOVERNMENT WARNING:` verified all-caps.
- Supporting fields (class/type, net contents, producer name/address, country of
  origin) → present/normalized match.

**Latency**
- ~5s is the bar for a **single** label. **Batch** is concurrent + streamed
  (results appear as each finishes), NOT sequential.

**Extractor — swappable AND resilient** (design now as stubs; no logic)
- One **abstract Extractor interface** with **three concrete stubs behind it**:
  1. a **premium cloud vision** extractor (prototype primary / single-label),
  2. a **cheap/local OCR** extractor (batch + production-compatible path),
  3. a **router/failover** layer that selects the engine and chains providers.
- **Failover chain:** primary → backup → `NEEDS_REVIEW`. **Single-label fails
  FAST** to `NEEDS_REVIEW` (the ~5s bar forbids serial cross-provider retries).
  **Batch MAY retry serially** across providers (per-item latency is relaxed).
- Providers are **config-selected, not hardcoded**.

**Azure production spine** (document; do NOT implement)
- The app is containerized so the **same image** runs on Fly.io (prototype) and
  drops into TTB's **existing Azure tenant** (Azure Container Apps / App Service
  for Linux) in production. In production the cloud vision call swaps to **Azure
  OpenAI** or **Azure AI Document Intelligence** over a private endpoint — which
  also clears TTB's outbound-ML-endpoint firewall block.
- **Choose a prototype model that has an Azure twin** (the GPT-4o family runs both
  as a public API and inside Azure OpenAI) so prototype → production is a **config
  change, not a rewrite**.

**Cost model** (design + config knobs now; no logic, no prices)
- Because the AI only transcribes, a **cheaper/smaller** vision or OCR engine
  suffices for most work.
- **Single-label = premium cloud model** (robust to phone-photo glare/angle; hits
  ~5s). **Batch = cheap/local engine** + **image-hash dedup/cache** + a cheap
  **pre-screen** that rejects blank/invalid files before spending a call +
  **concurrency cap** + **per-batch cost ceiling**; only ambiguous items escalate
  to the premium model.
- **Do NOT hardcode any model prices** — the provider/price is chosen at build time.

**Extensible field set** (design the structure; stub)
- Which fields are checked, and by which rule, is driven by a **field registry**
  so new label elements (e.g., TTB's proposed **Alcohol Facts** panel and
  **allergen disclosure**) become **data, not a code rewrite**.

**Access, persistence, scope**
- **No persistence, no auth** for the prototype (public demo). Add an *optional*
  shared-password hook (OFF by default) — justified by **cost/abuse control** on a
  paid API, not security.
- **English-only.**
- **Canonical Government Warning text:** in THIS pass leave it as a clearly marked
  placeholder constant with `# TODO: source exact 27 CFR 16.21 text at build time`.
  (The statutory text has been confirmed **stable** — a fixed constant is correct,
  no versioning machinery needed — but do **NOT** paste it from memory now.)

---

## FILES TO CREATE
Create exactly this tree under `C:\Users\finan\Documents\ttb-label-verify\`. Every `.py`
file gets a top-of-file docstring stating its single responsibility and, where
useful, function/class stubs with `pass` or `raise NotImplementedError` — but **no
working logic**.

```
C:\Users\finan\Documents\ttb-label-verify\
├── ARCHITECTURE.md                     (write this — see "ARCHITECTURE.md CONTENTS" below)
├── app\
│   ├── __init__.py
│   ├── main.py                         # FastAPI app: routes for single + batch verify, serves the UI page
│   ├── config.py                       # settings via env vars (see .env.example knobs below)
│   ├── models.py                       # pydantic models + ResultState enum (PASS/FAIL/NEEDS_REVIEW); FieldResult, LabelResult, BatchResult
│   ├── fields.py                       # NEW — field registry: which fields exist + which rule type each uses (extensible field set)
│   ├── cache.py                        # NEW — image-hash dedup/cache (batch cost guard); in-memory for prototype
│   ├── verify.py                       # orchestrator (single): router -> extractor -> matchers -> assemble LabelResult
│   ├── batch.py                        # batch runner: pair images to CSV rows, pre-screen, dedup, concurrent extract (capped pool), stream results, build summary + cost ceiling
│   ├── extraction\
│   │   ├── __init__.py
│   │   ├── base.py                     # abstract Extractor interface: extract(image_bytes) -> structured fields (+ an ok/confidence flag so the router can fail over)
│   │   ├── router.py                   # NEW — selects engine (single=premium, batch=cheap) + failover chain primary->backup->NEEDS_REVIEW
│   │   ├── vision_llm.py               # premium cloud vision extractor (stub) implementing the interface
│   │   ├── ocr_local.py                # NEW — cheap/local OCR extractor (stub) implementing the interface (batch + production path)
│   │   └── prompt.py                   # the extraction prompt text + expected JSON schema (verbatim-warning instruction)
│   ├── matching\
│   │   ├── __init__.py
│   │   ├── rules.py                    # the field matchers (stubs): match_brand, match_abv, match_warning, match_supporting
│   │   ├── normalize.py                # text-normalization helpers (case, punctuation, whitespace)
│   │   └── canonical.py                # stored canonical Government Warning constant (placeholder + TODO note)
│   ├── templates\
│   │   └── index.html                  # ONE page: big upload zone, one primary button, results table area. Plain, obvious, large targets.
│   └── static\
│       ├── style.css                   # minimal, high-contrast, large-font styling (73-year-old / no-training bar)
│       └── app.js                      # handles upload + renders results; batch uses SSE/streaming to append rows as they arrive
├── tests\
│   ├── __init__.py
│   ├── test_matching.py                # empty test stubs for each matcher (the graded core gets tested here later)
│   └── fixtures\
│       └── .gitkeep
├── test_labels\
│   └── .gitkeep                        # generated test label images go here later
├── sample_data\
│   └── batch_template.csv              # header row only: image_filename,brand,alcohol_content,warning,class_type,net_contents,producer,country_of_origin
├── requirements.txt                    # fastapi, uvicorn[standard], pydantic, python-multipart, jinja2, httpx, rapidfuzz, pandas, python-dotenv, pytest, sse-starlette
│                                       #   (local-OCR / provider SDK deps are added in a LATER phase — not this pass)
├── Dockerfile                          # python slim base, install requirements, run uvicorn (stub is fine)
├── fly.toml                            # minimal placeholder; real values filled at deploy time
├── .env.example                        # see the knob list below
├── .gitignore                          # python, .env, __pycache__, venv, uploaded temp files
└── README.md                           # LEAVE THE EXISTING FILE — see DO NOT TOUCH
```

**`.env.example` must contain these knobs (names + empty values + a short comment each):**
```
# --- Extraction providers (config-selected; no logic this pass) ---
PRIMARY_MODEL=            # premium cloud vision model for single-label (pick one with an Azure OpenAI twin, e.g. gpt-4o)
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
`config.py` exposes these as a typed settings object (stub — read env, no behavior).

---

## ARCHITECTURE.md CONTENTS
Write `ARCHITECTURE.md` as a clear technical blueprint with these sections:

1. **Overview** — one paragraph: what the app does, the **"AI reads, code judges"**
   principle, AND the **Azure production spine** as the organizing idea (prototype
   on Fly.io with a cloud model; the *same container* into TTB's Azure tenant with
   Azure OpenAI / Document Intelligence for production).
2. **Component diagram** (ASCII or Mermaid): `Browser UI → FastAPI → Extractor
   Router → [ Premium cloud vision | Backup provider | Cheap/local OCR ] →
   Matcher (deterministic) → Result`. Show the **Batch runner** path including
   **pre-screen → cache/dedup → capped worker pool → SSE stream**. Show
   `NEEDS_REVIEW` as the safe fallback out of the router.
3. **Single-label flow** — upload → validate → extract (premium, **fail-fast**) →
   match → per-field result, with the **~5s budget annotated at each step**; on
   extractor failure/timeout → `NEEDS_REVIEW` (no serial retry, to honor 5s).
4. **Batch flow & concurrency model** — CSV + images → pair by `image_filename` →
   **pre-screen** invalid/blank → **image-hash dedup/cache** → concurrent
   extraction on the **cheap/local engine** (capped pool) → per-item matching →
   results **streamed via SSE** as each finishes → final **summary counts**. Note
   `MAX_BATCH_ITEMS` + `PER_BATCH_COST_CEILING`, and that batch may **retry across
   providers serially**.
5. **Result model** — `PASS / FAIL / NEEDS_REVIEW`; the bias against false PASS;
   and that `NEEDS_REVIEW` doubles as the **resilience fallback** (AI unavailable →
   human, never a guessed pass).
6. **Extractor interface & provider strategy** — the abstract interface; providers
   swappable via config; the **dual-engine split** (single = premium, batch =
   cheap/local); the **Azure twin** so prototype→prod is config-only.
7. **Resilience & failover** — primary → backup → `NEEDS_REVIEW`; single fails fast
   vs batch serial retry; production failover via Azure regional redundancy /
   Document Intelligence. *(This section explicitly answers "what if the AI is down.")*
8. **Cost model** — AI-transcribes-only means a cheaper model suffices; dedup/cache;
   pre-screen; concurrency + cost caps; escalate-ambiguous-only; providers
   config-selected; **prices are chosen at build time, never hardcoded**. State
   plainly that this section updates decisions **D-1** & **D-6** and retires
   limitation **E.8**. *(Answers "cost savings" and "300 calls is wasteful.")*
9. **Extensible field set** — the field registry drives which fields are checked
   and by which rule; adding the proposed **Alcohol Facts** / **allergen** fields
   later is **data, not code**.
10. **Module layout** — reproduce the tree above; one line on each module's job.
11. **Technical choices & why** — justify FastAPI (async → batch), deterministic
    matching (auditable; exact-warning can't be model judgment), the swappable +
    resilient extractor, SSE (simple server→client streaming), and **Docker as the
    portability unit into Azure** (the *real* reason, not convenience). Address
    **Python vs their .NET COLA**: the brief permits any language, and a Linux
    container is equally at home in their Azure tenant, so language is a non-issue
    while Python gives the best AI/vision ecosystem. Tie to the "appropriate
    technical choices" grading criterion.
12. **Requirements mapping** — a short table linking each module to the FR/MR/NFR
    it satisfies (pull IDs from `REQUIREMENTS.md`). Include resilience/cost →
    NFR-05 (graceful degradation), NFR-06 (robust input), NFR-01/02
    (latency/throughput), CON-04 (clean core).
13. **Deferred to later phases** — real extraction/matching logic, batch
    implementation, the soft warning font-size/bold signal (MR-06), local-OCR
    wiring, second-provider failover wiring, and deployment.

---

## DO NOT TOUCH
- Do **not** overwrite or edit `README.md`, `REQUIREMENTS.md`,
  `ASSUMPTIONS_AND_TRADEOFFS.md`, or `Working_Document_List.txt`. They are inputs.
- Do **not** write any real extraction, matching, or verification logic in this pass.
- Do **not** call any external/AI API.
- Do **not** deploy, run Docker, or push to GitHub.
- Do **not** invent or paste the Government Warning text from memory — placeholder + TODO only.
- Do **not** install local-OCR or provider-SDK dependencies this pass (stubs only).
- Do **not** hardcode any model prices or provider-specific pricing anywhere.

---

## ACCEPTANCE TEST (so the user can confirm it worked without technical judgment)
1. Open `C:\Users\finan\Documents\ttb-label-verify\ARCHITECTURE.md` — it reads as a clear
   blueprint, contains a diagram, describes both the single-label and batch flows,
   **and** has sections on **resilience/failover**, **cost**, and the **Azure
   production path**.
2. Open the `C:\Users\finan\Documents\ttb-label-verify\` folder — the folder/file tree above
   is present, including `app\`, `app\extraction\` (with `base.py`, `router.py`,
   `vision_llm.py`, `ocr_local.py`, `prompt.py`), `app\matching\`, `app\cache.py`,
   `app\fields.py`, `tests\`, `sample_data\`, and `test_labels\`.
3. Open two or three of the `.py` files — each has a short docstring explaining what
   it's for, and stubs, but no actual working code yet.
4. Nothing was run and nothing crashed, because nothing executes in this pass.

When all four are true, STOP and return `ARCHITECTURE.md` to the Testing Manager for review.
