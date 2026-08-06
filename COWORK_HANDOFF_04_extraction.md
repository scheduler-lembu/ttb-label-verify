# COWORK HANDOFF #4 — Vision Extraction Wired to the Matching Core

## START HERE
Read these first, then this handoff:
- `C:\Users\finan\Documents\ttb-label-verify\ARCHITECTURE.md`  (§3 single-label flow, §6 extractor interface, §7 resilience)
- `C:\Users\finan\Documents\ttb-label-verify\app\fields.py`  (the 7 field keys the extractor must return)
- `C:\Users\finan\Documents\ttb-label-verify\app\matching\rules.py`  (`run_matchers` — the code that judges; DO NOT change it)
- `C:\Users\finan\Documents\ttb-label-verify\TEST_PLAN.md`  (the expected verdict per catalog label)
- `C:\Users\finan\Documents\ttb-label-verify\.env.example`  (the config knobs)

---

## OBJECTIVE
Implement **real vision extraction** ("AI reads") and wire it through a verify step
into the existing **deterministic matcher** ("code judges"), then verify the whole
single-label pipeline against the test-label catalog. **Single-label only** — no UI,
no batch, no deployment. The matching core is DONE and must not be reopened.

---

## MODEL (current — updates D-1, which said "GPT-4o")
- Provider: **OpenAI**, official `openai` Python SDK. All current models are vision-capable.
- **Single-label primary = `gpt-5.6-terra`** (balances accuracy and cost; ~$2/$12 per MTok).
- **Batch engine = `gpt-5.6-luna`** (cheap; used in a LATER batch pass — set the default now, don't use it yet).
- Model IDs are **config values** (`PRIMARY_MODEL`, `BATCH_MODEL`), never hardcoded in logic.
- Use a **low reasoning effort** setting for speed/cost (transcription needs no deep reasoning).

---

## CORE PRINCIPLES (build to these)
- **AI reads, code judges.** The extractor ONLY transcribes the label into the 7
  registry fields. ALL verdicts come from `run_matchers` (unchanged). The extractor
  never decides PASS/FAIL.
- **Verbatim warning + clean boundaries (MA-10).** The prompt MUST instruct the model
  to transcribe the Government Warning **exactly, character-for-character, preserving
  case and punctuation**, with **no correction, completion, or normalization**, and to
  return ONLY the warning text in that field (do NOT scoop trailing text such as
  "CONTAINS SULFITES" into the warning). If a field is not present or not readable,
  return **null** — never guess.
- **Fail-fast (single-label ~5s).** One primary attempt within `SINGLE_LABEL_TIMEOUT_S`.
  On timeout/error, do NOT retry serially (backup provider is deferred) — return a
  result that makes verify mark the fields **NEEDS_REVIEW**, never a crash, never a guess.
- **Structured output.** Ask the model for a JSON object with exactly these keys:
  `brand, alcohol_content, warning, class_type, net_contents, producer, country_of_origin`
  (string or null each). Parse it defensively.

---

## FILES TO EDIT / CREATE

### `app/config.py`
Typed settings loaded from env (`python-dotenv` already present). Read:
`API_KEY`, `PRIMARY_MODEL` (default `gpt-5.6-terra`), `BATCH_MODEL` (default
`gpt-5.6-luna`), `SINGLE_LABEL_TIMEOUT_S` (default `5`), `MAX_UPLOAD_MB` (default `10`).
Expose one settings object. Do not print or log the key.

### `app/extraction/base.py`
Define the interface + result type:
- `ExtractionResult` (pydantic): `fields: dict[str, str | None]`, `ok: bool`, `error: str | None = None`.
- Abstract `Extractor` with `extract(self, image_bytes: bytes) -> ExtractionResult`.

### `app/extraction/prompt.py`
The extraction prompt text + the JSON schema/keys. Encode the verbatim-warning and
clean-boundary rules above verbatim. State that the response must be JSON only, with the
7 keys, string-or-null values, and no commentary.

### `app/extraction/vision_llm.py`
`OpenAIVisionExtractor(Extractor)`:
- Build the client with `OpenAI(api_key=settings.API_KEY)`.
- Base64-encode `image_bytes`; send it as image input together with the prompt, using
  the SDK's **current vision pattern** (Responses API preferred; `chat.completions`
  with a base64 image is an acceptable fallback if simpler). Use `PRIMARY_MODEL`, low
  reasoning effort, and a request timeout aligned to `SINGLE_LABEL_TIMEOUT_S`.
- Request JSON output; parse into the 7 keys. Missing/extra keys handled gracefully
  (missing → null). On any exception/timeout → `ExtractionResult(fields={}, ok=False, error=str(e))`.

### `app/extraction/router.py`
- `get_single_extractor()` → returns the `OpenAIVisionExtractor` (primary).
- `extract_single(image_bytes) -> ExtractionResult` → calls the primary; on `ok=False`
  returns it as-is (backup/failover is a LATER pass — leave a clear TODO, no logic).

### `app/verify.py`
- `verify_label(image_bytes: bytes, expected: dict) -> LabelResult`:
  - `result = extract_single(image_bytes)`.
  - If `result.ok`: `return run_matchers(expected, result.fields)`.
  - If not ok: build a `LabelResult` where **every registry field is NEEDS_REVIEW**
    (reason `UNREADABLE`, note "extractor unavailable — needs human review"), so the
    app degrades gracefully and never crashes (NFR-05/06). Use the field registry to
    enumerate fields; overall rolls up to NEEDS_REVIEW.

### `tools/run_catalog.py`  (the acceptance harness)
- Load `sample_data/test_labels.csv`. For each row: read the PNG named by
  `image_filename` from `test_labels/`, call `verify_label(png_bytes, row_expected)`,
  time it.
- Print, per label: filename · overall verdict · each field's verdict(reason) · seconds.
- Include the **TEST_PLAN expected verdict** for each label (hardcode a small
  expected-map drawn from TEST_PLAN §3) and mark each label **MATCH / DIFFERS** vs expected.
- Print a summary: how many labels matched expected, min/median/max single-label seconds.
- Load `API_KEY` from `.env`; if it's blank, print a clear "add your key to .env" message and exit 0 (do not crash).

### `requirements.txt`
Append `openai` (the official SDK). Keep the rest unchanged.

### `.env.example`
Ensure defaults reflect the model update: `PRIMARY_MODEL=gpt-5.6-terra`,
`BATCH_MODEL=gpt-5.6-luna`, `SINGLE_LABEL_TIMEOUT_S=5`. Keep `API_KEY=` blank.

### `.env`  (CREATE this file for the user; it is git-ignored)
Copy `.env.example` to `.env` with `API_KEY=` left **blank**. This is where the user
pastes their key. Never put a real key in any committed file.

---

## PAUSE FOR THE KEY (important sequencing)
After building everything above **and creating `.env`**, do NOT run the harness yet.
**Pause and tell the user:** "Open `C:\Users\finan\Documents\ttb-label-verify\.env` in
Notepad, paste your OpenAI key so the line reads `API_KEY=sk-...`, save, and tell me to
continue." Only after the user confirms, run the harness.

---

## DOC SYNC (Cowork writes these — ADD-ONLY where noted)
- `ASSUMPTIONS_AND_TRADEOFFS.md` **§B, decision D-1** — update the model choice: replace
  the "GPT-4o" wording with "OpenAI GPT-5.6 tier family — `gpt-5.6-terra` for single
  label, `gpt-5.6-luna` for batch; config-swappable; production path = the current GPT
  model offered on Azure OpenAI inside TTB's tenant." Add a sentence: "The Sol/Terra/Luna
  tiers map directly onto the premium/balanced/cheap dual-engine cost model."
- `ARCHITECTURE.md` — wherever "GPT-4o" appears (§1, §6), replace the model name with
  "the GPT-5.6 family (Terra single-label, Luna batch)". Factual sync only; do not
  restructure.
- **Do NOT change `REQUIREMENTS.md`** — no requirement is model-specific.

---

## DO NOT TOUCH
- `app/models.py`, `app/fields.py`, `app/matching/*`, `tests/*` — the matching core is
  DONE; do not modify it (verify.py CALLS `run_matchers`, it does not change it).
- `app/main.py`, `app/templates/*`, `app/static/*` — UI is the NEXT pass; leave stubs.
- `app/batch.py`, `app/cache.py` — batch is a later pass; leave stubs.
- No Docker, no deploy, no `git push`. Never commit `.env` or the key.

---

## ACCEPTANCE TEST
1. `pip install -r requirements.txt` (now includes `openai`).
2. Build completes; `.env` exists with `API_KEY=` blank; **pause for the user's key** as above.
3. After the user pastes their key: run `python tools/run_catalog.py`.
4. The harness prints, for all 10 labels: overall + per-field verdicts (with reasons),
   seconds, and MATCH/DIFFERS vs the TEST_PLAN expectation, plus the summary line.
5. **Expected outcome:** the clean labels (01–07) should reproduce their TEST_PLAN
   verdicts, and each single label should return in roughly ≤5s. Labels 08–10 (missing
   warning, tiny warning, degraded image) may DIFFER — that is a *finding about the
   model's reading*, not a bug; the harness should surface it, not hide it.
6. Report back to the Testing Manager: the full harness table, the timing summary, and a
   note on any DIFFERS rows. **Do not push** — the Testing Manager reviews first.
