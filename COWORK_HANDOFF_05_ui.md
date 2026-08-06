# COWORK HANDOFF #5 — The Single-Page UI + Routes

## OBJECTIVE
Turn the UI/route stubs into the real, working single page: an upload zone, an
expected-values form (the 6 typed fields — NOT the Government Warning), one primary
"Verify label" button, and a color-coded extracted-vs-expected results table with an
overall banner. Server-rendered (a plain form POST that re-renders with results) so it
works even with JavaScript off; JS only enhances (filename, thumbnail, "Checking…"
state). A missing/bad upload produces a clear message, never a crash (NFR-06). The
engine (matcher, verify, extraction, quality gate, cross-check) is NOT touched. Batch
is a later pass (#6). Do not git commit or push.

## FILES TO CREATE / EDIT
Create:
- C:\Users\finan\Documents\ttb-label-verify\tests\test_app.py
Overwrite (these are stubs — replace their full contents):
- C:\Users\finan\Documents\ttb-label-verify\app\main.py
- C:\Users\finan\Documents\ttb-label-verify\app\templates\index.html
- C:\Users\finan\Documents\ttb-label-verify\app\static\style.css
- C:\Users\finan\Documents\ttb-label-verify\app\static\app.js
Edit (add-only):
- C:\Users\finan\Documents\ttb-label-verify\ASSUMPTIONS_AND_TRADEOFFS.md
- C:\Users\finan\Documents\ttb-label-verify\REQUIREMENTS.md
- C:\Users\finan\Documents\ttb-label-verify\requirements.txt  (only if a dep is missing — see below)

## CHANGES

### 1) requirements.txt
Confirm `jinja2` and `python-multipart` are present (they should be from the scaffold).
If EITHER is missing, append it. Change nothing else.

### 2) app/main.py — replace the entire file with:
```python
"""FastAPI application — serves the single-page UI and runs single-label verify.

Routes:
    GET  /         -> the one page (upload + expected-values form + results)
    POST /verify   -> run one verification, re-render the page with the results
    GET  /health   -> liveness check (for the deploy platform)

Batch (/batch) is a later pass (#6). "AI reads, code judges" lives in app.verify;
this module is only the HTTP + presentation surface, and it must never crash on a
bad upload — malformed input becomes a clear message (NFR-06).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.fields import FIELD_REGISTRY
from app.models import LabelResult, ResultState
from app.verify import verify_label

app = FastAPI(title="TTB Label Verification")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# The agent types every field EXCEPT the Government Warning — that is checked
# against the stored regulation text, not a typed value.
FORM_FIELDS = [f for f in FIELD_REGISTRY if f.key != "warning"]
FIELD_LABELS = {f.key: f.label for f in FIELD_REGISTRY}

PLACEHOLDERS = {
    "brand": "OLD TOM DISTILLERY",
    "alcohol_content": "45% Alc./Vol. (90 Proof)",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "net_contents": "750 mL",
    "producer": "Old Tom Distillery, Bardstown, KY",
    "country_of_origin": "Leave blank if domestic",
}

VERDICT_LABELS = {
    ResultState.PASS: "Pass",
    ResultState.FAIL: "Fail",
    ResultState.NEEDS_REVIEW: "Needs review",
}


def _short(text, limit=80):
    if text is None:
        return None
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


def _build_rows(result: LabelResult):
    rows = []
    for fr in result.fields:
        if fr.field == "warning":
            expected_disp = "matches the official regulation text (27 CFR 16.21)"
            extracted_disp = _short(fr.extracted) if fr.extracted else "\u2014 not found \u2014"
        else:
            expected_disp = _short(fr.expected) if fr.expected else "\u2014 (blank) \u2014"
            extracted_disp = _short(fr.extracted) if fr.extracted else "\u2014 not read \u2014"
        rows.append({
            "label": FIELD_LABELS.get(fr.field, fr.field),
            "extracted": extracted_disp,
            "expected": expected_disp,
            "verdict": fr.verdict.value,
            "verdict_label": VERDICT_LABELS.get(fr.verdict, fr.verdict.value),
            "reason": fr.note if fr.verdict != ResultState.PASS else None,
        })
    return rows


def _overall_message(result: LabelResult):
    fail = sum(1 for f in result.fields if f.verdict == ResultState.FAIL)
    review = sum(1 for f in result.fields if f.verdict == ResultState.NEEDS_REVIEW)
    if result.overall == ResultState.PASS:
        return "All checks passed"
    if result.overall == ResultState.FAIL:
        parts = [f"{fail} failed"]
        if review:
            parts.append(f"{review} to review")
        return "Problems found \u2014 " + ", ".join(parts)
    plural = "s" if review != 1 else ""
    return f"Needs a human look \u2014 {review} field{plural} to review"


def _render(request, values=None, error=None, result=None):
    ctx = {
        "request": request,
        "form_fields": FORM_FIELDS,
        "placeholders": PLACEHOLDERS,
        "values": values or {},
        "error": error,
        "rows": _build_rows(result) if result else None,
        "overall_state": result.overall.value if result else None,
        "overall_message": _overall_message(result) if result else None,
    }
    return templates.TemplateResponse("index.html", ctx)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _render(request)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.post("/verify", response_class=HTMLResponse)
async def verify_route(request: Request):
    settings = get_settings()
    form = await request.form()
    values = {f.key: (str(form.get(f.key) or "")).strip() for f in FORM_FIELDS}
    upload = form.get("label_image")

    if upload is None or not getattr(upload, "filename", ""):
        return _render(request, values=values, error="Choose a label image to check.")

    try:
        image_bytes = await upload.read()
    except Exception:
        return _render(request, values=values,
                       error="Couldn't read that file. Choose the image again.")

    if not image_bytes:
        return _render(request, values=values,
                       error="That file was empty. Choose a label image to check.")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(image_bytes) > max_bytes:
        return _render(request, values=values,
                       error=f"That image is too large (max {settings.MAX_UPLOAD_MB} MB). Choose a smaller file.")

    expected = {f.key: values.get(f.key, "") for f in FORM_FIELDS}
    try:
        result = verify_label(image_bytes, expected)
    except Exception:
        return _render(request, values=values,
                       error="Something went wrong reading that label. Try again, or use a clearer image.")

    return _render(request, values=values, result=result)
```

### 3) app/templates/index.html — replace the entire file with:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TTB Label Verification</title>
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>
  <main class="page">
    <header class="head">
      <h1>TTB label verification</h1>
      <p class="tagline">Upload a label, enter what it should say, and check them against each other.</p>
    </header>

    <form class="verify-form" method="post" action="/verify" enctype="multipart/form-data" id="verify-form">
      <div class="grid">
        <section class="upload-zone" id="upload-zone">
          <label for="label-file" class="upload-label">
            <span class="upload-title">Drop a label image here, or click to choose</span>
            <span class="file-name" id="file-name"></span>
          </label>
          <input type="file" id="label-file" name="label_image" accept="image/*" class="file-input" required />
          <img id="thumb" class="thumb" alt="" hidden />
        </section>

        <section class="fields">
          <p class="fields-title">What the label should say</p>
          {% for f in form_fields %}
          <div class="field">
            <label for="f_{{ f.key }}">
              {{ f.label }}{% if not f.required %} <span class="muted">— imports only</span>{% endif %}
            </label>
            <input type="text" id="f_{{ f.key }}" name="{{ f.key }}"
                   value="{{ values.get(f.key, '') }}"
                   placeholder="{{ placeholders.get(f.key, '') }}" />
          </div>
          {% endfor %}
        </section>
      </div>

      <p class="warning-note">
        The Government Warning has no box — the app checks the label against the official regulation text automatically.
      </p>

      <button type="submit" id="verify-button" class="primary-button">Verify label</button>
    </form>

    {% if error %}
    <div class="error-banner" role="alert">{{ error }}</div>
    {% endif %}

    {% if rows %}
    <section class="results" aria-label="Results">
      <div class="overall overall-{{ overall_state }}">{{ overall_message }}</div>
      <table id="results-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>On the label</th>
            <th>Expected</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
          <tr>
            <td class="cell-field">{{ row.label }}</td>
            <td class="cell-val">{{ row.extracted }}</td>
            <td class="cell-val">{{ row.expected }}</td>
            <td class="cell-result">
              <span class="badge badge-{{ row.verdict }}">{{ row.verdict_label }}</span>
              {% if row.reason %}<div class="reason">{{ row.reason }}</div>{% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </section>
    {% endif %}
  </main>

  <script src="/static/app.js"></script>
</body>
</html>
```

### 4) app/static/style.css — replace the entire file with:
```css
:root {
  --fg: #12181f;
  --muted: #5a626c;
  --bg: #ffffff;
  --panel: #f7f8fa;
  --accent: #0b5fff;
  --border: #c8ced6;
  --pass-bg: #e6f4ea; --pass-fg: #12692c;
  --fail-bg: #fdecea; --fail-fg: #a3161c;
  --review-bg: #fbf1d3; --review-fg: #7a5600;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: var(--font);
  font-size: 18px;
  line-height: 1.5;
  color: var(--fg);
  background: var(--bg);
}

.page { max-width: 960px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
.head h1 { font-size: 2rem; margin: 0 0 0.25rem; }
.tagline { color: var(--muted); margin: 0 0 1.75rem; }

.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; align-items: start; }
@media (max-width: 680px) { .grid { grid-template-columns: 1fr; } }

.upload-zone {
  position: relative;
  background: var(--panel);
  border: 3px dashed var(--border);
  border-radius: 14px;
  min-height: 200px;
  display: flex; align-items: center; justify-content: center;
  padding: 1.25rem;
}
.upload-zone.dragover { border-color: var(--accent); background: #eef4ff; }
.upload-label { text-align: center; cursor: pointer; display: block; width: 100%; }
.upload-title { display: block; font-size: 1.05rem; color: var(--muted); }
.file-name { display: block; margin-top: 0.6rem; font-weight: 700; color: var(--fg); word-break: break-all; }
.file-input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.thumb { display: block; max-width: 100%; max-height: 180px; margin: 0.75rem auto 0; border-radius: 8px; }

.fields { background: var(--panel); border-radius: 14px; padding: 1.1rem 1.2rem; }
.fields-title { margin: 0 0 0.75rem; font-size: 0.95rem; font-weight: 700; color: var(--muted); }
.field { margin-bottom: 0.7rem; }
.field label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 0.2rem; }
.field .muted { color: #99a0aa; }
.field input {
  width: 100%; padding: 0.6rem 0.7rem; font-size: 1rem; font-family: inherit;
  color: var(--fg); background: #fff; border: 1px solid var(--border); border-radius: 8px;
}
.field input:focus { outline: 2px solid var(--accent); outline-offset: 1px; border-color: var(--accent); }

.warning-note {
  margin: 1rem 0 0; font-size: 0.9rem; color: var(--muted);
  background: var(--panel); border-radius: 10px; padding: 0.7rem 0.9rem;
}

.primary-button {
  display: block; width: 100%; margin: 1.25rem 0 0;
  padding: 1rem 1.5rem; font-size: 1.2rem; font-weight: 700; font-family: inherit;
  color: #fff; background: var(--accent); border: none; border-radius: 12px; cursor: pointer;
}
.primary-button:hover { background: #0a54e0; }
.primary-button:disabled { opacity: 0.6; cursor: default; }

.error-banner {
  margin: 1.5rem 0 0; padding: 0.9rem 1.1rem; font-weight: 700;
  color: var(--fail-fg); background: var(--fail-bg);
  border: 1px solid #f2b8b5; border-radius: 12px;
}

.results { margin-top: 2rem; }
.overall {
  padding: 0.9rem 1.1rem; font-size: 1.2rem; font-weight: 700;
  border-radius: 12px; margin-bottom: 1rem;
}
.overall-PASS { color: var(--pass-fg); background: var(--pass-bg); }
.overall-FAIL { color: var(--fail-fg); background: var(--fail-bg); }
.overall-NEEDS_REVIEW { color: var(--review-fg); background: var(--review-bg); }

#results-table { width: 100%; border-collapse: collapse; }
#results-table th, #results-table td {
  text-align: left; padding: 0.8rem 0.7rem; border-bottom: 1px solid var(--border); vertical-align: top;
}
#results-table th { font-size: 0.85rem; color: var(--muted); font-weight: 700; }
.cell-field { font-weight: 700; white-space: nowrap; }
.cell-val { color: #3a424c; word-break: break-word; }
.cell-result { white-space: nowrap; }

.badge {
  display: inline-block; padding: 0.15rem 0.7rem; border-radius: 999px;
  font-size: 0.85rem; font-weight: 700;
}
.badge-PASS { color: var(--pass-fg); background: var(--pass-bg); }
.badge-FAIL { color: var(--fail-fg); background: var(--fail-bg); }
.badge-NEEDS_REVIEW { color: var(--review-fg); background: var(--review-bg); }
.reason { margin-top: 0.35rem; font-size: 0.8rem; color: var(--muted); white-space: normal; max-width: 220px; }
```

### 5) app/static/app.js — replace the entire file with:
```javascript
"use strict";

(function () {
  var fileInput = document.getElementById("label-file");
  var fileName = document.getElementById("file-name");
  var thumb = document.getElementById("thumb");
  var zone = document.getElementById("upload-zone");
  var form = document.getElementById("verify-form");
  var button = document.getElementById("verify-button");

  function showFile(file) {
    if (!file) return;
    if (fileName) fileName.textContent = file.name;
    if (thumb && file.type && file.type.indexOf("image/") === 0) {
      thumb.src = URL.createObjectURL(file);
      thumb.hidden = false;
    }
  }

  if (fileInput) {
    fileInput.addEventListener("change", function () {
      if (fileInput.files && fileInput.files[0]) showFile(fileInput.files[0]);
    });
  }

  if (zone) {
    ["dragenter", "dragover"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("dragover"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove("dragover"); });
    });
    zone.addEventListener("drop", function (e) {
      var files = e.dataTransfer && e.dataTransfer.files;
      if (files && files[0] && fileInput) { fileInput.files = files; showFile(files[0]); }
    });
  }

  if (form && button) {
    form.addEventListener("submit", function () {
      button.disabled = true;
      button.textContent = "Checking\u2026 (about 5 seconds)";
    });
  }
})();
```

### 6) tests/test_app.py — NEW, fully offline (no API key, no network):
```python
"""Route/UI tests for the FastAPI app (offline — no API key, no network).

The blank-image case exercises the whole /verify route end to end: the quality
gate short-circuits a blank upload to NEEDS_REVIEW BEFORE any API call, so the
route + template render without a key or network.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _blank_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), (127, 127, 127)).save(buf, format="PNG")
    return buf.getvalue()


def test_index_get_ok():
    r = client.get("/")
    assert r.status_code == 200
    assert "Verify label" in r.text
    assert "Brand Name" in r.text
    assert "Government Warning has no box" in r.text


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_verify_no_file_shows_message():
    r = client.post("/verify", data={"brand": "OLD TOM"})
    assert r.status_code == 200
    assert "Choose a label image" in r.text


def test_verify_blank_image_needs_review():
    r = client.post(
        "/verify",
        data={"brand": "OLD TOM DISTILLERY", "alcohol_content": "45%"},
        files={"label_image": ("blank.png", _blank_png(), "image/png")},
    )
    assert r.status_code == 200
    assert "Needs review" in r.text
    assert "clearer photo" in r.text
```

### 7) DOC SYNC (add-only)
**ASSUMPTIONS_AND_TRADEOFFS.md**
- §B table — append one row (next id after D-20 is D-21):
  `D-21 | **UI: server-rendered single page** | One page: an upload zone, an expected-values form (the 6 typed fields), one primary button, and a color-coded extracted-vs-expected results table with an overall banner; the Government Warning has no input (checked against the canonical text). Progressive-enhancement JS (filename/thumbnail/"Checking…" state) only — the plain form works with JS off | Meets the no-training / 73-year-old bar (NFR-03): one obvious action, no hunting; robust because the core works without JavaScript | A full-page reload clears the file input, so re-checking the same image after editing a value needs re-selecting it | JS fetch (no reload) or a richer role-based UI in production |`
- §E — append one item (next number in sequence): "The single-label UI is server-rendered (full-page form POST); after a result the browser clears the file input, so re-checking the same image with edited expected values requires re-selecting the image. Minor; a no-reload JS submit is the production refinement."

**REQUIREMENTS.md** (ADD-ONLY)
- §6 (NFR-03 / NFR-06 area) — append: "The single-page UI (one upload zone, one expected-values form, one primary button, a color-coded extracted-vs-expected results table with an overall banner) is server-rendered and operable with no training (NFR-03); a missing or malformed upload produces a clear message rather than an error or crash (NFR-06). The Government Warning is verified against the stored regulation text and therefore has no input field."

## DO NOT TOUCH
- app/matching/*, app/models.py, app/fields.py, app/verify.py, app/quality_gate.py,
  app/extraction/* (ocr_local, vision_llm, base, router, prompt), app/config.py,
  tools/*, TEST_PLAN.md, ARCHITECTURE.md — all unchanged.
- app/batch.py, app/cache.py (batch = #6); Dockerfile, fly.toml (deploy = #7).
- All existing tests (test_matching, test_quality, test_ocr_local, test_vision_image) — unchanged.
- Do NOT git add, commit, or push. Do NOT touch .env or print the API key.

## ACCEPTANCE TEST
1. `pip install -r requirements.txt`  (ensure jinja2 + python-multipart are installed)
2. `pytest -q` — report the summary. Expected: the 53 existing tests still pass PLUS the
   4 new route tests = 57 passed. If any existing test fails, STOP and paste it.
3. Boot check (no server needed): run
   `python -c "from fastapi.testclient import TestClient; from app.main import app; print(TestClient(app).get('/').status_code)"`
   and confirm it prints `200`.
4. Paste back: the pytest summary (57 passed), the boot-check `200`, the exact doc lines
   added to ASSUMPTIONS_AND_TRADEOFFS.md / REQUIREMENTS.md, confirmation that only the
   files listed above changed, and confirmation that nothing was committed or pushed.
   (The user will then run `uvicorn app.main:app --reload` and view the page in a browser.)
