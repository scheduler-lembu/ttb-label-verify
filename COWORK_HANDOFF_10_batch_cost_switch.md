OBJECTIVE
Make the batch path cheap enough to run on a public demo URL: (1) route BATCH extraction to
the cheap BATCH_MODEL (Luna) instead of the pricier PRIMARY_MODEL (Terra), and (2) add an
in-memory image-hash dedup cache so the app never pays to extract the same image twice. The
single-label path (Terra) is UNCHANGED. Correctness is preserved: the cache stores the
EXTRACTION (the transcribed fields), keyed by image content — NOT the final verdict — so the
free deterministic matcher always re-runs against the current expected values. Offline build +
unit tests; no deploy, no UI change, no live 300-run required.

TARGET REPO (CONFIRMED): C:\Users\finan\Documents\ttb-label-verify\  (NOT "shaphal".)

BEFORE YOU START — READ THESE
- app\config.py              (PRIMARY_MODEL, BATCH_MODEL, MAX_CONCURRENCY, etc.)
- app\extraction\base.py     (Extractor interface + ExtractionResult shape)
- app\extraction\vision_llm.py (OpenAIVisionExtractor — how the model ID is set today)
- app\extraction\router.py   (get_single_extractor / extract_single — the single-label path)
- app\verify.py              (verify_label: extract -> run_matchers -> LabelResult; failure -> all NEEDS_REVIEW)
- app\batch.py               (run_batch_stream — how it calls verify_label per item under the semaphore)
- app\cache.py               (the ImageCache STUB to implement)
- tests\test_batch.py        (existing batch tests to keep green)

FILES TO EDIT / CREATE
EDIT:   app\cache.py                    (stub -> real in-memory content-hash cache of EXTRACTION results)
EDIT:   app\extraction\vision_llm.py    (allow the model ID to be chosen: primary vs batch)
EDIT:   app\extraction\router.py        (add get_batch_extractor + extract_batch with dedup)
EDIT:   app\verify.py                   (allow batch to supply the batch extractor WITHOUT changing single-label behavior)
EDIT:   app\batch.py                    (route batch items through the batch extractor + a SHARED cache)
EDIT:   app\.env.example                (comment: batch uses BATCH_MODEL + dedup; keep values as-is)
CREATE: tests\test_cache.py             (offline cache + dedup unit tests)
EDIT:   tests\test_batch.py             (add a dedup call-count test — see acceptance)
EDIT:   ASSUMPTIONS_AND_TRADEOFFS.md    (add-only note — see change F)

CHANGES

A) app\cache.py — implement ImageCache (in-memory, per-process)
   - key(image_bytes) -> str : a stable content hash (e.g. sha256 hexdigest of the bytes).
   - get(key) -> value | None : return the cached value, or None on miss (do NOT raise on miss).
   - put(key, value) -> None : store value under key in an in-memory dict.
   - The stored VALUE is the EXTRACTION result (the fields dict / ExtractionResult), NOT a LabelResult.
   - In-memory only (no disk, no persistence — CON-02/D-8). Lost on process restart, by design.
   - Only successful extractions get cached (see C). Keep it small and dependency-free.

B) app\extraction\vision_llm.py — make the model selectable
   - The OpenAIVisionExtractor must be able to use EITHER PRIMARY_MODEL or BATCH_MODEL. Add a model
     parameter (constructor arg or factory arg) that defaults to settings.PRIMARY_MODEL, so the single
     path is byte-for-byte unchanged. The batch factory passes settings.BATCH_MODEL.
   - Nothing else about the extractor changes (same prompt, same JSON parsing, same timeout/fail handling).

C) app\extraction\router.py — batch extractor + dedup
   - Keep get_single_extractor / extract_single EXACTLY as they are (single-label path untouched).
   - Add get_batch_extractor() -> an OpenAIVisionExtractor configured with settings.BATCH_MODEL.
   - Add extract_batch(image_bytes, cache) -> ExtractionResult:
       * compute key = cache.key(image_bytes);
       * hit  (cache.get(key) is not None) -> return the cached ExtractionResult, NO API call;
       * miss -> call the batch extractor; if result.ok, cache.put(key, result); return result.
       * do NOT cache failures (ok=False), so a transient error isn't stuck.
     The cache is PASSED IN (so batch.py owns one shared instance) — do not use a module global.

D) app\verify.py — let batch supply its extractor without disturbing single-label
   - Preferred pattern (lowest risk): keep the existing verify_label(image_bytes, expected) signature and
     behavior 100% unchanged (still uses extract_single), and add a small internal core it delegates to,
     e.g. verify_label_with(image_bytes, expected, extract_fn) that does extract -> run_matchers -> assemble,
     and the failure branch (all fields NEEDS_REVIEW, reason UNREADABLE) exactly as today. verify_label
     becomes the thin wrapper calling the core with extract_single. If you instead add an optional
     parameter to verify_label, its default MUST be the current single-label extractor so all existing
     callers/tests are unaffected.
   - The matcher (run_matchers) and the failure-handling semantics are UNCHANGED.

E) app\batch.py — use the batch engine + one shared cache
   - Create ONE ImageCache for the batch run (per job/process is fine).
   - For each item, verify via the BATCH extractor path (extract_batch with that shared cache) instead of
     extract_single — i.e. call the verify core with a batch extract_fn that closes over the shared cache.
   - Keep everything else: the MAX_CONCURRENCY semaphore, off-thread execution, as-completed streaming,
     pairing, folder_tags/clean annotation (from #8), and the summary event — ALL UNCHANGED.
   - Net effect: identical images within a run (or across repeated runs in the same process) are extracted
     once; the matcher still runs per item against that item's expected values.

F) ASSUMPTIONS_AND_TRADEOFFS.md — ADD-ONLY
   - Append one short note (new §E limitation item, next number): "Batch extraction now runs on BATCH_MODEL
     (the cheap Luna tier) with an in-memory image-hash dedup cache: an identical image is transcribed once
     per process and reused, so repeated demo runs are near-free until restart. The cache is in-memory only
     (no persistence, CON-02) and stores the EXTRACTION, not the verdict, so results stay correct when the
     same image is checked against different application data. Single-label stays on PRIMARY_MODEL (Terra)
     for graded accuracy." Do not reword or remove any existing line.

DO NOT TOUCH
- The matching/verdict logic: app\matching\*, app\models.py, app\fields.py, app\matching\canonical.py — UNCHANGED.
  (run_matchers, the reason codes, the canonical warning — none of it changes.)
- app\triage.py and the entire triage UI: app\static\batch.js, app\templates\batch.html, app\static\style.css — UNCHANGED.
- app\extraction\prompt.py (the transcribe-only prompt) — UNCHANGED.
- The single-label path behavior (verify_label as called today, extract_single, PRIMARY_MODEL) — UNCHANGED.
- The graded catalog (test_labels\, sample_data\test_labels.csv, TEST_PLAN.md, tools\generate_test_labels.py) — UNCHANGED.
- The #7 demo corpus (demo_labels\, sample_data\demo_applications.csv, tools\generate_demo_labels.py) — UNCHANGED.
- Docs other than the one ASSUMPTIONS add-only note — UNCHANGED. Do NOT change REQUIREMENTS.md (no requirement changes).
- No git add/commit/push. No .env / API-key access or printing. No Docker/deploy. Do NOT run the 300-item demo
  through the live model this pass — prove it with the offline call-count test below.

ACCEPTANCE TEST
1. pip install -r requirements.txt
2. pytest -q — all prior tests (89) still pass, PLUS:
   - tests\test_cache.py: key() is stable for identical bytes and differs for different bytes; put/get roundtrip;
     get() on a missing key returns None (no raise).
   - a DEDUP CALL-COUNT test (in test_cache.py or test_batch.py): with a FAKE extractor that counts calls and a
     shared ImageCache, extract_batch on the SAME image bytes twice calls the underlying extractor EXACTLY ONCE
     (second call is a cache hit); two DIFFERENT images call it twice. No real model — fully offline.
   - a wiring assertion that get_batch_extractor() is configured with settings.BATCH_MODEL (and the single
     extractor still uses PRIMARY_MODEL).
   Report the pytest summary and the new test count.
3. Boot check: TestClient GET /batch -> 200.
4. Confirm single-label path unchanged: verify_label's existing signature/behavior is intact (its existing tests
   pass untouched); the single extractor still uses PRIMARY_MODEL.
5. Scope check: git status shows only the intended files changed; the matcher core, canonical warning, triage.py,
   the whole triage UI, the graded catalog, the #7 corpus, and all docs except the one ASSUMPTIONS note are untouched.
6. Report back to the Testing Manager: the pytest summary + new test count, the exact dedup call-count result
   (1 call for the repeated image, 2 for distinct images), confirmation the single-label path is unchanged,
   confirmation of scope, and that nothing was committed/pushed and no live 300-run occurred.
