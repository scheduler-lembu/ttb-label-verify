# TTB AI Label Verification — Prototype

A web app that helps a TTB compliance agent verify an alcohol-beverage **label image**
against its **application data**, returning a per-field **PASS / FAIL / NEEDS REVIEW**
result with the extracted value shown next to the expected value. It is a standalone
proof-of-concept: **no COLA integration and no real PII** — expected values are entered
(single label) or uploaded as a CSV (batch), not fetched from any production system.

The guiding idea is **"AI reads, code judges"**: a vision model only *transcribes* the
label into structured fields; every verdict is produced by deterministic Python so the
results are repeatable, auditable, and explainable.

## Live demo

Deployment target: **https://ttb-label-checker.fly.dev**

This is the intended public demo URL for the Fly.io deployment. The app is containerized
and the Fly app is created, but deployment is the immediately-following step — if the link
does not respond yet, see [Deploy (Fly.io)](#deploy-flyio). Treat it as the demo/target
URL, not a guarantee that it is currently live.

## What it does

- **Brand name** — normalized / fuzzy, case- and punctuation-insensitive (`STONE'S THROW`
  matches `Stone's Throw`).
- **Alcohol content** — ABV / proof equivalence (proof = 2 × ABV%), within a small
  tolerance.
- **Government Warning** — exact, character-for-character against the stored **27 CFR
  16.21** canonical text (whitespace-normalized only), plus an **all-caps prefix** check
  (`GOVERNMENT WARNING` must be all caps; title case fails).
- **Supporting fields** — class/type, net contents, producer name/address, country of
  origin (imports).
- **Single-label and batch modes** — batch accepts a CSV plus label images; results
  **stream in progressively** (SSE) so a reviewer can start on finished items before the
  whole batch completes.
- **Three-state results** — PASS / FAIL / NEEDS REVIEW, deliberately **biased against a
  false PASS**, each carrying a machine-readable **reason code** (e.g. `mismatch`,
  `blank_expected`, `borderline`, `special_character`, `warning_wording`) for triage.

## Approach

- **AI reads, code judges.** The vision model transcribes the label into structured
  fields; the deterministic matcher owns every PASS/FAIL/NEEDS_REVIEW. The AI is a
  decision aid, never the decider.
- **Three-state, safety-biased results.** When a field can't be read or confidently
  judged, it becomes NEEDS_REVIEW rather than a guessed PASS or FAIL — a confident-but-wrong
  PASS is the worst failure mode in compliance.
- **Blind extraction.** The extractor is not told the expected values, so it can't be
  nudged toward "matching" — it transcribes what's on the label; the matcher compares.
- **Literal-OCR warning cross-check.** Because vision models tend to paraphrase text, the
  warning region is *also* read with Tesseract; if the two reads disagree, a warning PASS
  is downgraded to NEEDS_REVIEW. This is safety-only — it can never turn a FAIL into a PASS,
  and it degrades gracefully (skips) if Tesseract isn't installed.
- **Swappable extractor.** The extraction engine is selected by config (cloud vision for
  the prototype); the documented production path swaps it for an in-tenant Azure endpoint,
  which also clears the network/firewall constraint noted by TTB IT.

## Tech stack / tools

- **Python 3.11+**, **FastAPI**, **Uvicorn** (ASGI).
- **Vision extractor:** OpenAI GPT-5.6 family — `gpt-5.6-terra` (single label) and
  `gpt-5.6-luna` (cheaper batch). Model IDs are **config values** (`.env` / `config.py`),
  **not hardcoded** in logic.
- **Tesseract** (`pytesseract`) for the literal Government-Warning cross-check (optional —
  degrades gracefully if absent).
- **rapidfuzz** for fuzzy field matching; **OpenCV** (`opencv-python-headless`) + **NumPy**
  for the pre-extraction image quality gate; **Pillow** for image handling.
- **SSE** (`sse-starlette`) for progressive batch streaming; **pandas** for the demo data
  source.
- **Docker** for the portable container; **Fly.io** as the demo host.

See `requirements.txt` for the full dependency list and `ARCHITECTURE.md` for the design.

## Setup & run (local)

**Prerequisites**
- Python 3.11 or newer.
- (Optional) **Tesseract OCR** for the literal warning cross-check. Without it the app
  runs fine — the cross-check is simply skipped and the warning verdict falls back to the
  vision read.
- An OpenAI API key to run live extraction. The **test suite and the offline tools do not
  need a key.**

**Install**
```bash
pip install -r requirements.txt
```

**Run the tests** (offline — no API key, no network):
```bash
pytest -q
```
The suite currently reports **101 passed**. It proves the deterministic matcher core
(brand/ABV/warning/supporting rules, batch pairing, triage, quality gate) without any key.

**Configure the API key**
```bash
cp .env.example .env
# then edit .env and set:
#   API_KEY=sk-...
```
The key variable is **`API_KEY`**. `.env` is **git-ignored** and must never be committed;
model IDs and cost/concurrency knobs are also read from `.env` (see `.env.example` for every
option and its default).

**Run the web app**
```bash
uvicorn app.main:app --reload
```
Then open **http://127.0.0.1:8000** — the batch/triage app is the home page; the
single-label page is at `/single`.

**Regenerate the demo / test data and run the accuracy harness** (all offline except the
last, which needs a key):
```bash
python tools/generate_demo_labels.py   # ~300 synthetic demo labels -> demo_labels/ + sample_data/demo_applications.csv
python tools/generate_test_labels.py   # the graded 10-label adversarial catalog -> test_labels/ + sample_data/test_labels.csv
python tools/run_catalog.py            # runs the catalog through the REAL pipeline (needs API_KEY); prints per-label verdicts vs TEST_PLAN + timings
```

## Batch input format

Upload a CSV plus the label images. The CSV header is the field-registry keys:

```
image_filename,brand,alcohol_content,warning,class_type,net_contents,producer,country_of_origin
```

- Each row is paired to an image by **`image_filename`**, matched **case-insensitively** on
  the basename (so `Label1.PNG` or `folder/label1.png` in the CSV pairs with an uploaded
  `label1.png`). Extensions are not guessed, and two uploads that differ only by case are
  reported as ambiguous rather than guessed.
- A downloadable template is served at **`/template.csv`**.
- The **`warning` column is informational** — the Government Warning is always checked
  against the stored canonical 27 CFR text, not against a per-row value.
- Unmatched rows/images, oversized images, and truncation (batches over the item cap) are
  surfaced back to the user as pairing notices rather than silently dropped.

## Deploy (Fly.io)

The app ships as a Docker image (`Dockerfile`) and deploys to Fly.io as
**`ttb-label-checker`** (`fly.toml`: internal port 8000, a `/health` check, scale-to-zero
when idle). The OpenAI key is provided as a **Fly secret**, never baked into the image or
committed:

```bash
fly secrets set API_KEY=sk-...
fly deploy
```

The same container is designed to drop into TTB's Azure tenant for production
(prototype → production is a config change of the extraction endpoint, not a rebuild).

## Assumptions, trade-offs & limitations

Honest highlights (full list in `ASSUMPTIONS_AND_TRADEOFFS.md`):

- **Not production-hardened — by design.** No authentication, no persistence, no PII
  handling, no audit log (CON-02); images are processed in memory and discarded.
- **Cloud AI for the demo.** The documented production/network-restricted path is
  Azure OpenAI / Azure Document Intelligence over an in-tenant private endpoint.
- **Strict, character-for-character warning match.** Over-strict beats under-strict on the
  one graded exact field: a correctly-worded but re-cased/reformatted warning can FAIL, but
  it's shown with extracted-vs-canonical and is overridable.
- **MR-06 font-size / "buried text" detection is DEFERRED and NOT implemented** (it's a
  *Could*). The exact-text and all-caps-prefix checks (both *Must*) are done. A tiny warning
  may still land in NEEDS_REVIEW *incidentally* when the literal-OCR cross-check disagrees —
  but that is an OCR-disagreement signal, not a size measurement.
- **Latency is a measured median, not an SLA.** ~2s median (≈1.8–4.4s) on the synthetic
  test-label catalog, within the ~5s design target (NFR-01) — a target met on the test set,
  not a hard per-request guarantee.
- **English-only.** Non-ASCII / accented values are routed to a `special_character`
  NEEDS_REVIEW rather than silently mis-matched.
- **Batch is demo-grade.** Concurrent + streamed with a per-item size skip and an item cap;
  there is a per-item upload cap but **no total-request memory cap** (a documented prototype
  limit). Sustained high volume would need a queue/worker system.

## Requirements & tests

- **`REQUIREMENTS.md`** — the SRS: functional requirements (FR), matching rules (MR),
  non-functional requirements (NFR), constraints, and traceability.
- **`TEST_PLAN.md`** — a deliberately adversarial test-label catalog where each label proves
  a specific requirement (exact/altered/omitted warning, title-case prefix, ABV equivalence,
  tiny warning, degraded image, …).
- The automated suite (`pytest -q`, **101 passed**) proves the matcher core **offline with
  no API key**; `tools/run_catalog.py` exercises the full extraction+matching pipeline live.

## Repository layout

```
app/            FastAPI app: routes/UI (main.py), extraction (extraction/), deterministic
                matchers (matching/), verify orchestrator, quality gate, batch, triage, config
tests/          Offline test suite (matcher core, batch pairing, triage, quality gate)
tools/          Offline generators for the demo + graded catalogs, and the accuracy harness
sample_data/    Expected-values CSVs and the batch template
demo_labels/    ~300 synthetic demo label images (one-click demo batch)
test_labels/    The graded 10-label adversarial catalog (TEST_PLAN)
```

More detail: `ARCHITECTURE.md` (components, request/data flow, batch concurrency),
`ASSUMPTIONS_AND_TRADEOFFS.md` (every decision and its trade-off). The original take-home
brief is preserved at `docs/PROJECT_BRIEF.md`.
