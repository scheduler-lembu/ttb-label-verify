# COWORK HANDOFF #4c — Single-Label Latency Hardening

## OBJECTIVE
Harden the single-label vision call against latency pathologies so NFR-01 holds in
the real world: (1) disable the OpenAI SDK's silent retries (they doubled a slow call
to ~7s), (2) apply a generous per-request hang-ceiling timeout (a genuinely stalled
call degrades to NEEDS_REVIEW rather than hanging), (3) cap output tokens (no runaway
generation), and (4) downscale oversized images before the call (keeps real phone
photos fast and cheap; a no-op on the small catalog). Verdicts must NOT change — the
catalog must still report 10/10. The matcher core, the warning cross-check, and the
verify pipeline are NOT touched. Do not git commit or push.

## FILES TO CREATE / EDIT
Create:
- C:\Users\finan\Documents\ttb-label-verify\tests\test_vision_image.py
Edit:
- C:\Users\finan\Documents\ttb-label-verify\app\extraction\vision_llm.py
- C:\Users\finan\Documents\ttb-label-verify\app\config.py
- C:\Users\finan\Documents\ttb-label-verify\.env.example
- C:\Users\finan\Documents\ttb-label-verify\.env   (careful line edits only — see below)
- C:\Users\finan\Documents\ttb-label-verify\ASSUMPTIONS_AND_TRADEOFFS.md
- C:\Users\finan\Documents\ttb-label-verify\REQUIREMENTS.md

## CHANGES

### 1) app/config.py
- Change the default of `SINGLE_LABEL_TIMEOUT_S` from `5.0` to `10.0` in BOTH the
  Settings dataclass field default AND the `_get_float("SINGLE_LABEL_TIMEOUT_S", ...)`
  call in get_settings. Update its comment to: "per-request hard timeout (hang
  ceiling); typical latency is ~2-3s, the ~5s target is met by normal model latency —
  this only catches genuine stalls."
- Add two new knobs to the Settings dataclass with defaults, and read them in
  get_settings() with `_get_int`:
  - `VISION_MAX_IMAGE_DIM: int = 1536`   (longest-side cap for the vision input)
  - `MAX_OUTPUT_TOKENS: int = 700`       (cap on transcription output length)
- Change nothing else.

### 2) app/extraction/vision_llm.py
- Add `from io import BytesIO` to the top-level imports (next to `import base64`,
  `import json`). Keep PIL imported LAZILY inside the new helper.
- Add a helper next to `_image_mime`:
  ```python
  def _prepare_image(image_bytes: bytes, max_dim: int) -> "tuple[bytes, str]":
      """Downscale to a longest side of max_dim if larger; return (bytes, mime).
      Small images pass through unchanged. Fail-safe: on any error, send the
      original bytes so extraction still proceeds."""
      try:
          from PIL import Image
          with Image.open(BytesIO(image_bytes)) as img:
              w, h = img.size
              if max(w, h) <= max_dim:
                  return image_bytes, _image_mime(image_bytes)
              scale = max_dim / float(max(w, h))
              resized = img.convert("RGB").resize(
                  (max(1, int(w * scale)), max(1, int(h * scale))),
                  Image.LANCZOS,
              )
              buf = BytesIO()
              resized.save(buf, format="JPEG", quality=90)
              return buf.getvalue(), "image/jpeg"
      except Exception:
          return image_bytes, _image_mime(image_bytes)
  ```
- In `OpenAIVisionExtractor.extract`, change the client construction to disable retries:
  ```python
      client = OpenAI(
          api_key=self.settings.API_KEY,
          timeout=self.settings.SINGLE_LABEL_TIMEOUT_S,
          max_retries=0,  # no silent retry-balloon past the latency budget
      )
  ```
- Replace the image-encoding lines:
  ```python
      b64 = base64.b64encode(image_bytes).decode("ascii")
      data_url = f"data:{_image_mime(image_bytes)};base64,{b64}"
  ```
  with:
  ```python
      proc_bytes, mime = _prepare_image(image_bytes, self.settings.VISION_MAX_IMAGE_DIM)
      b64 = base64.b64encode(proc_bytes).decode("ascii")
      data_url = f"data:{mime};base64,{b64}"
  ```
- In the `client.responses.create(...)` call, add one argument (keep all others):
  ```python
          max_output_tokens=self.settings.MAX_OUTPUT_TOKENS,
  ```
  (Place it after `reasoning={"effort": "low"},`.)
- Change nothing else in the file. The broad `except Exception` fail-safe stays.

### 3) .env.example
- Change `SINGLE_LABEL_TIMEOUT_S=5` to `SINGLE_LABEL_TIMEOUT_S=10`.
- Append two lines: `VISION_MAX_IMAGE_DIM=1536` and `MAX_OUTPUT_TOKENS=700`.
- Keep every other line unchanged; keep API_KEY blank.

### 4) .env  (CAREFUL — do NOT touch the API key)
The live .env currently has SINGLE_LABEL_TIMEOUT_S=5, which would override the new
default. Update ONLY the timeout line and add the two new knobs:
- Change the `SINGLE_LABEL_TIMEOUT_S=` line's value to `10` (if the line exists; if
  it does not, add `SINGLE_LABEL_TIMEOUT_S=10`).
- Add `VISION_MAX_IMAGE_DIM=1536` and `MAX_OUTPUT_TOKENS=700` if not present.
- Do NOT read, print, reorder, modify, or remove the `API_KEY=` line or its value.
  After editing, report only "API_KEY still present" (never the key itself).

### 5) tests/test_vision_image.py — NEW, fully offline (Pillow only, NO API key)
Import `_prepare_image` and `_image_mime` from app.extraction.vision_llm. Build test
images with PIL and encode to bytes via a BytesIO buffer. Include:
- `test_small_image_passthrough`: a 100x100 PNG -> _prepare_image(bytes, 1536) returns
  the SAME bytes object/content (max dim <= 1536), and a PNG mime.
- `test_large_image_downscaled`: a 3000x2000 image -> _prepare_image(bytes, 1536)
  returns bytes that decode (via PIL) to an image whose longest side == 1536, and mime
  == "image/jpeg".
- `test_prepare_image_failsafe`: _prepare_image(b"not an image", 1536) returns a
  2-tuple without raising, and the first element is the original bytes.

### 6) DOC SYNC (paper matches code)

**ASSUMPTIONS_AND_TRADEOFFS.md**
- §B table — append one row (next id after D-19 is D-20):
  `D-20 | **Single-label latency hardening** | Disable SDK retries (max_retries=0); a generous per-request hang-ceiling timeout (stall -> NEEDS_REVIEW); cap output tokens; downscale oversized images before the vision call | The retry-balloon pushed a slow call past the bar; typical latency (~2-3s median) meets NFR-01, and downscaling keeps real phone photos fast and cheap | A genuinely slow single attempt can still take up to the hang-ceiling; the ~5s is met by typical latency, not a hard guillotine | Faster model tier / streaming in production |`
- §D (Trade-offs) — append one bullet: "Latency is bounded primarily by typical model latency (median ~2-3s on the catalog), not a hard 5s guillotine: retries are disabled and output/image size are capped so a slow call degrades to NEEDS_REVIEW at a hang-ceiling rather than ballooning, and large uploads are downscaled to stay within the interactive range and cut cost."
- §E — append one item (next number in sequence): "Single-label latency is dominated by the vision model; the heaviest labels approach ~5s and rely on typical latency (not a hard cap) to meet NFR-01. A per-request hang-ceiling prevents indefinite waits by degrading a stalled call to NEEDS_REVIEW."

**REQUIREMENTS.md** (ADD-ONLY)
- §6, the NFR-01 area — append: "Single-label latency is dominated by the vision model; measured median ~2-3s on the test catalog. The client disables retries and applies a per-request hang-ceiling timeout so a stalled call degrades to NEEDS_REVIEW rather than exceeding the budget indefinitely, and large images are downscaled before the call to keep real photos within the budget and reduce cost."

## DO NOT TOUCH
- app/matching/*, app/models.py, app/fields.py, app/quality_gate.py,
  app/extraction/ocr_local.py (the cross-check), app/verify.py (the pipeline),
  app/extraction/base.py, router.py, prompt.py, tools/run_catalog.py, TEST_PLAN.md,
  ARCHITECTURE.md — all unchanged this pass.
- All existing tests (test_matching.py, test_quality.py, test_ocr_local.py) — unchanged.
- app/main.py, templates/*, static/*, batch.py, cache.py, Dockerfile, fly.toml.
- Do NOT git add, commit, or push. Never read/print/alter the API_KEY value in .env.

## ACCEPTANCE TEST
1. `pip install -r requirements.txt`  (no-op; Pillow already present)
2. `pytest -q` — report the summary. Expected: the 50 existing tests still pass PLUS
   the 3 new image tests = 53 passed. If any existing test fails, STOP and paste it.
3. Confirm API_KEY is present in .env (report "present", never the key) and that its
   value was NOT altered. Confirm `SINGLE_LABEL_TIMEOUT_S` now reads 10 in .env.
4. If API_KEY present, run `python tools/run_catalog.py` and paste the full per-label
   table + timing summary. Expected: still **10/10 MATCH** (downscale is a no-op on the
   small catalog, the output cap does not bind, and first attempts succeed within the
   10s ceiling), and NO label balloons — the max time should reflect a single attempt
   (~5-7s worst), not a retry (~7s+). If any label DIFFERS, STOP and report.
5. Paste back: the pytest summary (53 passed), the harness table + timing, the exact
   doc lines added to ASSUMPTIONS_AND_TRADEOFFS.md / REQUIREMENTS.md, confirmation that
   the API key was untouched and never printed, and confirmation that nothing in the DO
   NOT TOUCH list changed and nothing was committed or pushed.
