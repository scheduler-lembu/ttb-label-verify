# COWORK HANDOFF #4b-1 — Image Quality Gate

## OBJECTIVE
Add a pre-extraction IMAGE QUALITY GATE to the single-label pipeline. A too-blurry,
blank, or undecodable upload must resolve to all-fields NEEDS_REVIEW ("request a
better image") BEFORE any AI/API call is made (cost guard + NFR-05). This pass does
NOT touch the tested matcher core, the extractor, or the warning verdict. The 36
existing tests must still pass. Do not git commit or push.

## FILES TO CREATE / EDIT
Create:
- C:\Users\finan\Documents\ttb-label-verify\app\quality_gate.py
- C:\Users\finan\Documents\ttb-label-verify\tests\test_quality.py

Edit:
- C:\Users\finan\Documents\ttb-label-verify\app\verify.py
- C:\Users\finan\Documents\ttb-label-verify\app\config.py
- C:\Users\finan\Documents\ttb-label-verify\.env.example
- C:\Users\finan\Documents\ttb-label-verify\requirements.txt
- C:\Users\finan\Documents\ttb-label-verify\ASSUMPTIONS_AND_TRADEOFFS.md
- C:\Users\finan\Documents\ttb-label-verify\REQUIREMENTS.md

## CHANGES

### 1) requirements.txt
Append these two lines, keep everything else unchanged:
```
opencv-python-headless
numpy
```

### 2) app/config.py
Add three knobs to the Settings dataclass with defaults, and read them in
get_settings():
- `QUALITY_GATE_ENABLED: bool = True`  (treat "0"/"false"/"no"/"" as False, anything else True)
- `QUALITY_BLUR_THRESHOLD: float = 60.0`
- `QUALITY_BLANK_STDDEV: float = 8.0`

Add a small `_get_bool(name, default)` helper if one does not already exist. Read
the two floats with the existing `_get_float` helper. Do not change any existing
knob or default. Never print/log values.

### 3) app/quality_gate.py — NEW
Single responsibility: a cheap, dependency-light check of whether an uploaded image
is readable enough to bother extracting.
- Import `cv2` and `numpy`.
- Define a dataclass `QualityResult` with:
  - `ok: bool`
  - `reason: str`   # one of: "ok", "blank", "blurry", "undecodable"
- Function:
  ```python
  def check_quality(image_bytes: bytes, *, blur_threshold: float,
                    blank_stddev: float) -> QualityResult
  ```
  Behavior:
  a. Decode to grayscale:
     ```python
     arr = np.frombuffer(image_bytes, np.uint8)
     gray = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
     ```
     If `gray is None` or `arr.size == 0` → `QualityResult(False, "undecodable")`.
  b. Blank/uniform check: if `float(gray.std()) < blank_stddev`
     → `QualityResult(False, "blank")`.
  c. Blur check: if `float(cv2.Laplacian(gray, cv2.CV_64F).var()) < blur_threshold`
     → `QualityResult(False, "blurry")`.
  d. Otherwise `QualityResult(True, "ok")`.

  Wrap the whole body in try/except; on ANY unexpected exception return
  `QualityResult(False, "undecodable")` — this gate must never raise.
- Module docstring: explain this is a heuristic pre-flight guard (not a calibrated
  quality model) that saves an API call on unreadable uploads and produces the
  "request a better image" path (NFR-05).

### 4) app/verify.py
Wire the gate in as STAGE 1, and generalize the existing all-needs-review helper.
- Generalize `_all_needs_review` so it accepts an optional note and reason,
  defaulting to the CURRENT values so existing behavior is unchanged:
  ```python
  def _all_needs_review(expected: dict, note: str = _UNAVAILABLE_NOTE,
                        reason: ResultReason = ResultReason.UNREADABLE) -> LabelResult
  ```
  and use `note`/`reason` when building each FieldResult.
- In `verify_label`, BEFORE calling `extract_single`, add:
  ```python
  settings = get_settings()
  if settings.QUALITY_GATE_ENABLED:
      q = check_quality(image_bytes,
                        blur_threshold=settings.QUALITY_BLUR_THRESHOLD,
                        blank_stddev=settings.QUALITY_BLANK_STDDEV)
      if not q.ok:
          return _all_needs_review(
              expected,
              note=f"image failed quality check ({q.reason}) — please upload a clearer photo",
          )
  ```
  Then proceed to the existing `extract_single(...)` → run_matchers / fallback logic
  exactly as it is now. Import `check_quality` and `get_settings` at the top.
- Do NOT change the extractor-unavailable path's wording or behavior (it still uses
  the default note/reason).

### 5) .env.example
Append the three new knobs with short comments and safe defaults:
```
QUALITY_GATE_ENABLED=true
QUALITY_BLUR_THRESHOLD=60
QUALITY_BLANK_STDDEV=8
```
Keep every existing line unchanged; keep API_KEY blank.

### 6) tests/test_quality.py — NEW
Fully offline (no API key, no Tesseract). Build images with numpy and encode to PNG
bytes via `cv2.imencode(".png", arr)[1].tobytes()`:
- `test_sharp_noise_ok`: a random-noise uint8 image (`np.random.randint(0,255,(200,200),dtype=uint8)`)
  → `check_quality(...).ok is True`, reason "ok".
- `test_blank_image_flagged`: a solid mid-gray image (`np.full((200,200),127,uint8)`)
  → ok is False, reason "blank".
- `test_blurry_image_flagged`: a smooth horizontal gradient
  (`np.tile(np.linspace(0,255,200).astype(uint8),(200,1))`) → ok is False, reason "blurry".
- `test_undecodable_bytes`: `check_quality(b"not an image", ...)` → ok is False,
  reason "undecodable".

Pass `blur_threshold=60.0` and `blank_stddev=8.0` explicitly in the tests.

### 7) DOC SYNC (paper matches code)

**ASSUMPTIONS_AND_TRADEOFFS.md**
- §B table — append one row:
  `D-15 | Pre-extraction image quality gate | Cheap OpenCV blur (Laplacian variance) + blank (std-dev) check; fail -> NEEDS_REVIEW "request a better image" BEFORE any API call | Saves a paid call on unreadable uploads and mirrors the agent's real practice of asking for a better photo (NFR-05) | Heuristic thresholds; a borderline image may pass or be flagged | Tunable thresholds / a calibrated quality model`
- §E (Known Limitations) — append one item (next number in sequence): "The image
  quality gate is heuristic (Laplacian-variance blur + std-dev blank check) — a cheap
  pre-flight guard, not a calibrated image-quality model; thresholds are config-tunable
  (QUALITY_BLUR_THRESHOLD / QUALITY_BLANK_STDDEV)."

**REQUIREMENTS.md** (ADD-ONLY — do not reword/remove anything existing)
- §6, the NFR-05 area: append one clarifying sentence after the table or in the
  acceptance detail prose: "A pre-extraction image quality gate (Laplacian-variance
  blur + std-dev blank check) routes unreadable uploads to NEEDS_REVIEW ('request a
  better image') before an API call is made, saving cost and matching current agent
  practice."

## DO NOT TOUCH
- app/matching/* (rules.py, normalize.py, canonical.py), app/models.py, app/fields.py,
  tests/test_matching.py — the graded matcher core is frozen and must stay at 36
  passing tests.
- app/extraction/* (vision_llm.py, base.py, router.py, prompt.py, and the ocr_local.py
  STUB — Tesseract comes in the NEXT pass, #4b-2).
- app/main.py, app/templates/*, app/static/* (UI = #5); app/batch.py, app/cache.py
  (batch = #6); Dockerfile, fly.toml (deploy / Tesseract system pkg = later).
- ARCHITECTURE.md and TEST_PLAN.md — leave unchanged this pass.
- Do NOT git add, commit, or push. Do NOT touch .env or print the API key.

## ACCEPTANCE TEST
1. `pip install -r requirements.txt`  (now includes opencv-python-headless, numpy)
2. `pytest -q` — report the summary. Expected: the previous 36 tests still pass PLUS
   the 4 new quality tests = **40 passed**. If anything fails, STOP and paste it.
3. Confirm API_KEY is present (report only "present"/"absent", never the key). If
   present, run `python tools/run_catalog.py` and paste the full per-label table +
   timing summary. Expected: still **10/10 MATCH** vs TEST_PLAN (the gate must NOT
   wrongly reject any real catalog label), and max single-label time still under ~5s
   (the gate adds only milliseconds). If any catalog label now returns all-NEEDS_REVIEW
   with a "quality check" note, that is a false-rejection — flag it clearly.
4. Paste back: the pytest summary (40 passed), the harness table + timing, the exact
   lines added to ASSUMPTIONS_AND_TRADEOFFS.md (§B row + §E item) and REQUIREMENTS.md
   (the NFR-05 note), and confirmation that nothing in the DO NOT TOUCH list changed
   and nothing was committed or pushed.
