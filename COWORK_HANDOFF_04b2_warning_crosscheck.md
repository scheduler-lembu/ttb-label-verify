# COWORK HANDOFF #4b-2 — Tesseract Literal-OCR Warning Cross-Check

## OBJECTIVE
Add a literal-OCR (Tesseract) CROSS-CHECK on the Government Warning. The strict
warning verdict still runs on the vision model's read via the UNCHANGED matcher.
Tesseract reads the same image in parallel; if the two reads DISAGREE (on wording
beyond a fuzzy tolerance, or on the all-caps prefix), a warning that would otherwise
PASS is downgraded to NEEDS_REVIEW. The cross-check can ONLY make a warning verdict
more conservative (PASS -> NEEDS_REVIEW); it never relaxes a FAIL/REVIEW. If Tesseract
is unavailable, the cross-check is skipped and behavior falls back to today's. The
graded matcher core and its tests are NOT touched. Do not git commit or push.

## FILES TO CREATE / EDIT
Create:
- C:\Users\finan\Documents\ttb-label-verify\tests\test_ocr_local.py
Edit:
- C:\Users\finan\Documents\ttb-label-verify\app\extraction\ocr_local.py
- C:\Users\finan\Documents\ttb-label-verify\app\verify.py
- C:\Users\finan\Documents\ttb-label-verify\app\config.py
- C:\Users\finan\Documents\ttb-label-verify\.env.example
- C:\Users\finan\Documents\ttb-label-verify\requirements.txt
- C:\Users\finan\Documents\ttb-label-verify\ASSUMPTIONS_AND_TRADEOFFS.md
- C:\Users\finan\Documents\ttb-label-verify\REQUIREMENTS.md
- C:\Users\finan\Documents\ttb-label-verify\TEST_PLAN.md

## CHANGES

### 1) requirements.txt
Append one line, keep everything else unchanged:
```
pytesseract
```
(The Tesseract SYSTEM binary is installed separately — on Windows it is already
installed for local dev; the deployed container installs it at Handoff #7. Do NOT
touch the Dockerfile this pass.)

### 2) app/config.py
Add two knobs to the Settings dataclass with defaults, and read them in
get_settings() (reuse the existing _get_bool and _get_float helpers):
- `WARNING_XCHECK_ENABLED: bool = True`
- `WARNING_XCHECK_THRESHOLD: float = 90.0`
Do not change any existing knob or default.

### 3) app/extraction/ocr_local.py
KEEP the existing module docstring and the `LocalOCRExtractor` stub exactly as they
are (that stub is the future batch engine — do not implement or remove it). ADD, below
the stub, the literal-OCR warning cross-check code. Requirements:

Imports to add at the top (module level is fine for these std-lib ones; import
pytesseract and PIL LAZILY inside functions so importing this module never fails when
the binary/wrapper is absent):
```python
import os
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from rapidfuzz import fuzz
```

Add:
```python
_WINDOWS_DEFAULT_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


@dataclass
class LiteralWarningRead:
    """Result of the literal-OCR warning read.
    available: False means Tesseract is not usable -> caller falls back to the
        vision read (no cross-check).
    text: the literal warning region ('GOVERNMENT WARNING...' onward) or None.
    """
    available: bool
    text: "str | None"


def _configure_tesseract() -> None:
    """Point pytesseract at the Windows default install if it is not on PATH.
    No-op if pytesseract is missing or on non-Windows."""
    try:
        import pytesseract
    except ImportError:
        return
    if os.name == "nt" and os.path.exists(_WINDOWS_DEFAULT_TESSERACT):
        pytesseract.pytesseract.tesseract_cmd = _WINDOWS_DEFAULT_TESSERACT


@lru_cache(maxsize=1)
def is_tesseract_available() -> bool:
    """True iff the Tesseract binary can be invoked. Cached (checked once)."""
    try:
        import pytesseract
    except ImportError:
        return False
    _configure_tesseract()
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def read_full_text(image_bytes: bytes) -> str:
    """Literal OCR of the whole image -> raw text (may raise; callers guard)."""
    import pytesseract
    from PIL import Image
    _configure_tesseract()
    with Image.open(BytesIO(image_bytes)) as img:
        return pytesseract.image_to_string(img)


def extract_warning_region(text: "str | None") -> "str | None":
    """Return the warning block: from the case-insensitive 'government warning'
    anchor to the end of the text (the warning is the last statement on a label).
    Pure function — no Tesseract needed."""
    if not text:
        return None
    idx = text.lower().find("government warning")
    if idx == -1:
        return None
    region = text[idx:].strip()
    return region or None


def read_warning(image_bytes: bytes) -> LiteralWarningRead:
    """Literal-OCR the image and return the warning region, guarded end to end."""
    if not is_tesseract_available():
        return LiteralWarningRead(available=False, text=None)
    try:
        return LiteralWarningRead(available=True,
                                  text=extract_warning_region(read_full_text(image_bytes)))
    except Exception:
        return LiteralWarningRead(available=True, text=None)


def _prefix_is_allcaps(text: "str | None") -> "bool | None":
    """True/False if a 'government warning' prefix is present and is/ isn't all
    caps; None if the prefix is absent. Pure function."""
    if not text:
        return None
    idx = text.lower().find("government warning")
    if idx == -1:
        return None
    matched = text[idx: idx + len("government warning")]
    return matched == matched.upper()


def warning_reads_agree(vlm_warning: "str | None", ocr_warning: "str | None",
                        threshold: float) -> bool:
    """Do the vision read and the literal-OCR read of the warning concur?
    Tolerant of OCR noise (case-folded fuzzy body compare) but catches genuine
    wording divergence and prefix-case divergence. Pure function."""
    if not vlm_warning and not ocr_warning:
        return True                       # both say "no warning" -> agree
    if bool(vlm_warning) != bool(ocr_warning):
        return False                      # one found a warning, the other didn't
    if fuzz.token_sort_ratio(vlm_warning.lower(), ocr_warning.lower()) < threshold:
        return False                      # wording diverges beyond tolerance
    if _prefix_is_allcaps(vlm_warning) != _prefix_is_allcaps(ocr_warning):
        return False                      # prefix case diverges (evasion catch)
    return True
```

### 4) app/verify.py
Wire the parallel read + cross-check into `verify_label`, AFTER the quality gate and
in place of the current plain `extract_single(...)` block. The matcher call stays
unchanged; the cross-check only post-processes the result.

- Add imports at the top:
  ```python
  from concurrent.futures import ThreadPoolExecutor
  from app.extraction.ocr_local import (
      is_tesseract_available,
      read_warning,
      warning_reads_agree,
  )
  ```
- Add this private helper (near `_all_needs_review`):
  ```python
  def _downgrade_warning_on_disagreement(label_result: LabelResult) -> LabelResult:
      """If the warning currently PASSes, drop it to NEEDS_REVIEW (reads disagree).
      Only touches a PASS -> more conservative only; never relaxes FAIL/REVIEW."""
      new_fields = []
      changed = False
      for fr in label_result.fields:
          if fr.field == "warning" and fr.verdict == ResultState.PASS:
              new_fields.append(FieldResult(
                  field=fr.field, expected=fr.expected, extracted=fr.extracted,
                  rule=fr.rule, verdict=ResultState.NEEDS_REVIEW,
                  reason=ResultReason.UNREADABLE,
                  note="vision and literal-OCR reads of the warning disagree — needs human review",
              ))
              changed = True
          else:
              new_fields.append(fr)
      return LabelResult.from_fields(new_fields) if changed else label_result
  ```
- Replace the current STAGE 2 block:
  ```python
      # STAGE 2: extract, then let the (unchanged) matcher judge.
      result = extract_single(image_bytes)
      if result.ok:
          return run_matchers(expected, result.fields)
      return _all_needs_review(expected)
  ```
  with:
  ```python
      # STAGE 2: parallel read — vision extract + (optional) literal OCR of the warning.
      xcheck_active = settings.WARNING_XCHECK_ENABLED and is_tesseract_available()
      with ThreadPoolExecutor(max_workers=2) as ex:
          vlm_future = ex.submit(extract_single, image_bytes)
          ocr_future = ex.submit(read_warning, image_bytes) if xcheck_active else None
          result = vlm_future.result()
          ocr = ocr_future.result() if ocr_future is not None else None

      if not result.ok:
          return _all_needs_review(expected)

      # STAGE 3: the unchanged matcher judges the vision read.
      label_result = run_matchers(expected, result.fields)

      # STAGE 4: warning cross-check — literal OCR can only make a PASS more cautious.
      if xcheck_active and ocr is not None and ocr.available:
          vlm_warning = result.fields.get("warning")
          if not warning_reads_agree(vlm_warning, ocr.text, settings.WARNING_XCHECK_THRESHOLD):
              label_result = _downgrade_warning_on_disagreement(label_result)

      return label_result
  ```
  (Keep STAGE 1, the quality gate, exactly as it is. `settings` is already defined
  earlier in the function.)

### 5) .env.example
Append the two new knobs with short comments and safe defaults; keep every existing
line unchanged, keep API_KEY blank:
```
WARNING_XCHECK_ENABLED=true
WARNING_XCHECK_THRESHOLD=90
```

### 6) tests/test_ocr_local.py — NEW, fully offline (NO Tesseract binary, NO API key)
Tests only the PURE functions (extract_warning_region, warning_reads_agree). Import
them from app.extraction.ocr_local. Include at least:
- `test_extract_region_found`: a multi-line text containing "GOVERNMENT WARNING: (1) According to..." -> returns a string that starts with "GOVERNMENT WARNING:".
- `test_extract_region_titlecase`: text containing "Government Warning: (1)..." -> returns a string starting with "Government Warning:" (case preserved).
- `test_extract_region_absent`: text with no warning phrase -> None.
- `test_extract_region_none_input`: extract_warning_region(None) -> None.
- `test_agree_identical`: with W = "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems." , warning_reads_agree(W, W, 90.0) is True.
- `test_agree_minor_ocr_noise`: same W vs W with a single character typo in one word -> still True (fuzzy tolerates it).
- `test_disagree_prefix_case`: W (all-caps prefix) vs the same text with only the prefix changed to "Government Warning:" -> False (prefix case diverges).
- `test_disagree_one_absent`: warning_reads_agree(W, None, 90.0) is False AND warning_reads_agree(None, W, 90.0) is False.
- `test_agree_both_absent`: warning_reads_agree(None, None, 90.0) is True AND warning_reads_agree("", "", 90.0) is True.
- `test_disagree_wording`: W vs a clearly different sentence -> False.

### 7) DOC SYNC (paper matches code)

**ASSUMPTIONS_AND_TRADEOFFS.md**
- §B table — append four rows (D-15 is already the quality gate; use D-16..D-19):
  - `D-16 | **Literal-OCR warning cross-check (Tesseract)** | Vision read still produces the strict verdict; Tesseract reads the same image and if the two warning reads disagree (fuzzy body < threshold, or all-caps prefix differs) a PASS is downgraded to NEEDS_REVIEW | VLMs paraphrase/"clean up" text — the false-PASS failure mode on the one graded exact field; a literal reader catches divergence without brittle OCR-vs-canonical matching | Tesseract is weaker on rotated/tiny text, so some compliant warnings on imperfect images route to NEEDS_REVIEW (recall-over-precision); needs the tesseract-ocr binary | Azure Document Intelligence (Read) as the literal reader in production`
  - `D-17 | **Parallel dual read** | Vision call and Tesseract read run concurrently (thread pool) | Adds ~no wall-clock (bounded by the slower read), so the cross-check honors the ~5s bar | Slightly more orchestration than sequential | async in production`
  - `D-18 | **Cross-check is one-directional (safety-only)** | The cross-check can only move a warning PASS -> NEEDS_REVIEW; it never relaxes a FAIL/REVIEW, and the strict verdict still runs on the vision read via the unchanged matcher | Keeps the graded matcher frozen and the change strictly conservative | A compliant warning misread by OCR may be flagged for a human (visible, overridable) | Tune threshold with real data`
  - `D-19 | **Graceful OCR fallback** | If the Tesseract binary is unavailable, the cross-check is skipped and the warning falls back to the vision read (the #4 behavior) | The cross-check is an enhancement, not a hard dependency; local dev without the binary still runs | Without Tesseract the false-PASS protection is prompt-only | The deployed container ships Tesseract so production always has the cross-check`
- §C table — append one row (last existing is MA-10; use MA-11):
  - `MA-11 | The Government Warning is the last statement block on the label, so anchoring on the case-insensitive "government warning" text and taking to end captures it without vision bounding boxes | The prototype vision extractor returns fields, not coordinates | Low — true for standard TTB layouts; unusual layouts make the reads disagree -> NEEDS_REVIEW`
- §E — append one item (next number in sequence): "The literal-OCR warning cross-check requires the Tesseract binary; where it is absent (e.g. local dev without the install) the warning verdict falls back to the vision transcription (prompt-guarded only). The deployed container installs tesseract-ocr so the cross-check is always active in production."

**REQUIREMENTS.md** (ADD-ONLY — do not reword/remove anything existing)
- §5, the MR-04/05 acceptance-detail area — append: "As an additional safeguard the prototype cross-checks the vision transcription of the warning against a literal OCR (Tesseract) read of the same image; if the two reads disagree on wording (beyond a fuzzy tolerance) or on the all-caps prefix, a warning that would otherwise PASS is routed to NEEDS_REVIEW. The strict character-for-character verdict itself is unchanged — the cross-check only makes a PASS more conservative, never a FAIL less so."

**TEST_PLAN.md**
- Read the file, then APPEND a new section at the end titled
  "## Handoff #4b-2 — literal-OCR warning cross-check: real end-to-end results".
  Fill it with the ACTUAL results from the acceptance harness run below: whether
  Tesseract was available, the per-label table (id / overall / expected / MATCH or
  DIFFERS / seconds), the min/median/max timing, and a one-line note for any label
  whose warning verdict changed because of the cross-check (candidates: label_09 tiny,
  label_10 degraded), stating why. Do not edit earlier sections.

## DO NOT TOUCH
- app/matching/* (rules.py, normalize.py, canonical.py), app/models.py, app/fields.py,
  tests/test_matching.py, tests/test_quality.py, app/quality_gate.py — frozen; the
  matcher core must stay green.
- app/extraction/vision_llm.py, base.py, router.py, prompt.py — unchanged this pass
  (the image-downscale change is a LATER, pre-deploy pass, not here).
- The existing `LocalOCRExtractor` stub in ocr_local.py — leave it; only ADD the
  cross-check code below it.
- app/main.py, templates/*, static/* (UI #5); app/batch.py, cache.py (#6);
  Dockerfile, fly.toml (deploy / tesseract system pkg = #7); ARCHITECTURE.md.
- Do NOT git add, commit, or push. Do NOT touch .env or print the API key.

## ACCEPTANCE TEST
1. `pip install -r requirements.txt`  (now includes pytesseract)
2. `pytest -q` — report the summary. Expected: the 40 existing tests still pass PLUS
   the ~10 new pure-function cross-check tests, all passing. If anything in the 40
   existing tests fails, STOP and paste it.
3. In a quick python check, confirm `is_tesseract_available()` returns True on this
   machine (the binary was installed via winget). Report the result. If it returns
   False, STOP and report — the binary path needs troubleshooting before the harness.
4. Confirm API_KEY is present (report only "present"/"absent", never the key). If
   present, run `python tools/run_catalog.py` and paste the full per-label table +
   timing summary. Then report, explicitly:
   - that Tesseract was available (so the cross-check was ACTIVE), and
   - any label whose warning field is now NEEDS_REVIEW with the note "vision and
     literal-OCR reads of the warning disagree" (i.e. the cross-check downgraded it),
     and whether that label now shows MATCH or DIFFERS vs TEST_PLAN.
   Expected: labels 01–08 keep their prior verdicts; labels 09 (tiny) and/or 10
   (rotated) MAY shift PASS -> NEEDS_REVIEW — that is a finding to report, not a bug.
   Timing should stay within ~5s typical (the reads run in parallel).
5. Paste back: the pytest summary, the harness table + timing, the exact doc lines
   added to ASSUMPTIONS_AND_TRADEOFFS.md / REQUIREMENTS.md and the TEST_PLAN.md section
   you appended, and confirmation that nothing in the DO NOT TOUCH list changed and
   nothing was committed or pushed.
