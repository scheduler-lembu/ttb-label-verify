# COWORK HANDOFF #6 — Batch Mode (concurrent + live-streamed)

## OBJECTIVE
Add batch verification: many label + application pairs in one submission, verified
CONCURRENTLY under a capped pool, with each result STREAMED to the browser (SSE) as it
finishes, ending with a pass/fail/needs-review summary (FR-10/11, NFR-02). Two entry
modes: a one-click demo (the bundled demo application DB paired to the catalog images on
disk) and a CSV-of-expected-values + label-images upload. Batch REUSES the finished
engine (app.verify.verify_label) unchanged — this pass is pairing + concurrency +
streaming, NOT new verification logic. It lives on its own /batch page; the single-label
page is untouched except for one link to it. No image-hash dedup this pass. Do not git
commit or push.

## FILES TO CREATE / EDIT
Create:
- C:\Users\finan\Documents\ttb-label-verify\app\templates\batch.html
- C:\Users\finan\Documents\ttb-label-verify\app\static\batch.js
- C:\Users\finan\Documents\ttb-label-verify\tests\test_batch.py
Overwrite (stub -> real):
- C:\Users\finan\Documents\ttb-label-verify\app\batch.py
Overwrite (full file, given below — it is the #5 file plus the batch routes):
- C:\Users\finan\Documents\ttb-label-verify\app\main.py
Edit (append / one-line add):
- C:\Users\finan\Documents\ttb-label-verify\app\static\style.css   (append the batch block)
- C:\Users\finan\Documents\ttb-label-verify\app\templates\index.html (add one link line)
- C:\Users\finan\Documents\ttb-label-verify\ASSUMPTIONS_AND_TRADEOFFS.md (add-only)
- C:\Users\finan\Documents\ttb-label-verify\REQUIREMENTS.md (add-only)
- C:\Users\finan\Documents\ttb-label-verify\requirements.txt (only if a dep is missing)

## CHANGES

### 1) requirements.txt
Confirm `sse-starlette` is present (it should be from the scaffold). If missing, append
it. Change nothing else.

### 2) app/batch.py — replace the entire file with:
```python
"""Batch runner — pairing + concurrent, progressively-streamed verification.

Reuses the finished single-label engine (app.verify.verify_label) unchanged:
batch is pairing + a capped concurrency pool + SSE streaming, NOT new
verification logic (FR-10/11, NFR-02). Each item is paired to its image by
filename, run concurrently under MAX_CONCURRENCY, and yielded the moment it
finishes so the UI can stream rows. No image-hash dedup in the prototype (a
documented cost optimization); the per-item quality gate already pre-screens
blank/unreadable uploads inside verify_label.
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
from dataclasses import dataclass

from app.config import get_settings
from app.data_source import get_application_source
from app.fields import FIELD_REGISTRY
from app.verify import verify_label

# Registry keys the agent supplies (the warning is checked against the canonical
# text, not the application — MA-8 — so it is never a supplied expected value).
_EXPECTED_KEYS = [f.key for f in FIELD_REGISTRY if f.key != "warning"]
_TEST_LABELS_DIR = "test_labels"


@dataclass
class BatchItem:
    """One paired label ready to verify."""
    name: str
    image_filename: str
    expected: "dict[str, str]"
    image_bytes: bytes


@dataclass
class PairingError:
    """A row/image that could not be paired (reported, not fatal)."""
    reference: str
    problem: str


def build_demo_items(settings=None):
    """Pair the bundled demo applications to their images on disk (no upload)."""
    settings = settings or get_settings()
    source = get_application_source(settings)
    items: list[BatchItem] = []
    errors: list[PairingError] = []
    for app in source.list_applications():
        fn = app.image_filename
        if not fn:
            errors.append(PairingError(app.application_id, "no image file named in the application"))
            continue
        path = os.path.join(_TEST_LABELS_DIR, fn)
        if not os.path.exists(path):
            errors.append(PairingError(fn, "image not found on the server"))
            continue
        with open(path, "rb") as fh:
            data = fh.read()
        expected = {k: (app.expected.get(k) or "") for k in _EXPECTED_KEYS}
        items.append(BatchItem(name=app.display_name or app.application_id,
                               image_filename=fn, expected=expected, image_bytes=data))
    return items, errors


def build_uploaded_items(csv_bytes: bytes, images: "dict[str, bytes]"):
    """Pair rows from an uploaded CSV to uploaded images by image_filename."""
    try:
        text = csv_bytes.decode("utf-8-sig")
    except Exception:
        text = csv_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    if "image_filename" not in headers:
        raise ValueError("The CSV needs an 'image_filename' column (see the template).")

    items: list[BatchItem] = []
    errors: list[PairingError] = []
    referenced = set()
    for row in reader:
        fn = (row.get("image_filename") or "").strip()
        if not fn:
            errors.append(PairingError("(row)", "blank image_filename"))
            continue
        referenced.add(fn)
        if fn not in images:
            errors.append(PairingError(fn, "no matching image was uploaded"))
            continue
        expected = {k: (row.get(k) or "").strip() for k in _EXPECTED_KEYS}
        name = expected.get("brand") or fn
        items.append(BatchItem(name=name, image_filename=fn, expected=expected, image_bytes=images[fn]))

    for fn in images:
        if fn not in referenced:
            errors.append(PairingError(fn, "image uploaded but no CSV row uses it"))
    return items, errors


async def run_batch_stream(items: "list[BatchItem]", max_concurrency: int):
    """Verify items concurrently (capped), yielding (item, LabelResult) as each finishes."""
    sem = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def process(item: BatchItem):
        async with sem:
            result = await asyncio.to_thread(verify_label, item.image_bytes, item.expected)
            return item, result

    tasks = [asyncio.create_task(process(it)) for it in items]
    for coro in asyncio.as_completed(tasks):
        yield await coro
```

### 3) app/main.py — replace the entire file with:
```python
"""FastAPI application — serves the UI and runs single-label + batch verification.

Routes:
    GET  /                       -> single-label page (upload + form + results)
    POST /verify                 -> run one verification, re-render with results
    GET  /batch                  -> the batch page (demo button + CSV/images upload)
    POST /batch                  -> create a batch job (pair items); returns job_id
    GET  /batch/{job_id}/stream  -> SSE: stream each result as it finishes + summary
    GET  /template.csv           -> download the batch CSV template
    GET  /health                 -> liveness check (for the deploy platform)

"AI reads, code judges" lives in app.verify; batch reuses it unchanged. This module
is the HTTP + presentation surface and must never crash on a bad upload (NFR-06).
"""

from __future__ import annotations

import json
import os
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from app.batch import build_demo_items, build_uploaded_items, run_batch_stream
from app.config import get_settings
from app.fields import FIELD_REGISTRY
from app.models import LabelResult, ResultState
from app.verify import verify_label

app = FastAPI(title="TTB Label Verification")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

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

# In-memory batch jobs (single-process prototype; dropped after streaming).
BATCH_JOBS: dict = {}
BATCH_TEMPLATE_PATH = "sample_data/batch_template.csv"


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
    return templates.TemplateResponse(request, "index.html", ctx)


def _batch_item_payload(item, result: LabelResult):
    attention = [
        f"{FIELD_LABELS.get(fr.field, fr.field)}: {VERDICT_LABELS.get(fr.verdict, fr.verdict.value)}"
        for fr in result.fields if fr.verdict != ResultState.PASS
    ]
    return {
        "name": item.name,
        "image_filename": item.image_filename,
        "overall": result.overall.value,
        "overall_label": VERDICT_LABELS.get(result.overall, result.overall.value),
        "attention": "; ".join(attention) if attention else "All fields pass",
    }


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


@app.get("/batch", response_class=HTMLResponse)
async def batch_page(request: Request):
    return templates.TemplateResponse(request, "batch.html", {})


@app.get("/template.csv")
async def batch_template():
    return FileResponse(BATCH_TEMPLATE_PATH, media_type="text/csv", filename="batch_template.csv")


@app.post("/batch")
async def batch_create(request: Request):
    settings = get_settings()
    form = await request.form()
    mode = form.get("mode") or "demo"
    try:
        if mode == "upload":
            csv_upload = form.get("csv_file")
            if csv_upload is None or not getattr(csv_upload, "filename", ""):
                return JSONResponse({"error": "Choose a CSV of expected values, or use the demo."}, status_code=400)
            csv_bytes = await csv_upload.read()
            images = {}
            for up in form.getlist("images"):
                fn = getattr(up, "filename", "")
                if fn:
                    images[os.path.basename(fn)] = await up.read()
            items, errors = build_uploaded_items(csv_bytes, images)
        else:
            items, errors = build_demo_items(settings)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception:
        return JSONResponse({"error": "Couldn't prepare that batch. Check the CSV and images."}, status_code=400)

    if len(items) > settings.MAX_BATCH_ITEMS:
        items = items[: settings.MAX_BATCH_ITEMS]

    pairing_errors = [{"reference": e.reference, "problem": e.problem} for e in errors]
    if not items:
        return JSONResponse({"error": "No labels to check.", "pairing_errors": pairing_errors}, status_code=400)

    job_id = uuid.uuid4().hex
    BATCH_JOBS[job_id] = items
    return JSONResponse({"job_id": job_id, "item_count": len(items), "pairing_errors": pairing_errors})


@app.get("/batch/{job_id}/stream")
async def batch_stream(job_id: str):
    items = BATCH_JOBS.get(job_id)
    if items is None:
        return JSONResponse({"error": "Unknown or expired batch."}, status_code=404)
    settings = get_settings()

    async def event_gen():
        counts = {"PASS": 0, "FAIL": 0, "NEEDS_REVIEW": 0}
        try:
            async for item, result in run_batch_stream(items, settings.MAX_CONCURRENCY):
                counts[result.overall.value] = counts.get(result.overall.value, 0) + 1
                yield {"event": "item", "data": json.dumps(_batch_item_payload(item, result))}
            yield {"event": "summary", "data": json.dumps({
                "total": len(items),
                "pass": counts["PASS"],
                "fail": counts["FAIL"],
                "needs_review": counts["NEEDS_REVIEW"],
            })}
        finally:
            BATCH_JOBS.pop(job_id, None)

    return EventSourceResponse(event_gen())
```

### 4) app/templates/batch.html — create with:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TTB Batch Verification</title>
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>
  <main class="page">
    <header class="head">
      <h1>Check a batch of labels</h1>
      <p class="tagline">Check many labels at once. Results appear as each one finishes.</p>
      <p><a class="back-link" href="/">&larr; Check a single label instead</a></p>
    </header>

    <section class="batch-entry">
      <div class="entry-card">
        <h2>Try the demo</h2>
        <p>Run the 10 built-in sample labels — no files needed.</p>
        <button type="button" id="demo-button" class="primary-button">Run the demo batch</button>
      </div>

      <div class="entry-card">
        <h2>Use your own</h2>
        <p>Upload a CSV of expected values and the label images (matched by file name).</p>
        <p><a href="/template.csv" download>Download the CSV template</a></p>
        <form id="upload-form">
          <label class="upload-sub" for="csv-file">Expected-values CSV</label>
          <input type="file" id="csv-file" name="csv_file" accept=".csv" />
          <label class="upload-sub" for="images-file">Label images (select all)</label>
          <input type="file" id="images-file" name="images" accept="image/*" multiple />
          <button type="submit" class="primary-button secondary">Check my batch</button>
        </form>
      </div>
    </section>

    <div class="error-banner" id="batch-error" role="alert" hidden></div>

    <section class="results" id="batch-results" hidden>
      <div class="overall" id="batch-summary">Starting&hellip;</div>
      <table id="batch-table">
        <thead>
          <tr><th>Label</th><th>Result</th><th>Needs attention</th></tr>
        </thead>
        <tbody id="batch-tbody"></tbody>
      </table>
    </section>
  </main>

  <script src="/static/batch.js"></script>
</body>
</html>
```

### 5) app/static/batch.js — create with:
```javascript
"use strict";

(function () {
  var demoBtn = document.getElementById("demo-button");
  var uploadForm = document.getElementById("upload-form");
  var errorBox = document.getElementById("batch-error");
  var resultsSec = document.getElementById("batch-results");
  var summaryEl = document.getElementById("batch-summary");
  var tbody = document.getElementById("batch-tbody");
  var counts;

  function showError(msg) { errorBox.textContent = msg; errorBox.hidden = false; }
  function clearError() { errorBox.hidden = true; errorBox.textContent = ""; }

  function reset() {
    clearError();
    tbody.innerHTML = "";
    counts = { total: 0, done: 0, PASS: 0, FAIL: 0, NEEDS_REVIEW: 0 };
    resultsSec.hidden = false;
    summaryEl.textContent = "Starting\u2026";
    summaryEl.className = "overall";
  }

  function updateRunning() {
    summaryEl.textContent = counts.done + " of " + counts.total + " checked  \u00b7  "
      + counts.PASS + " pass \u00b7 " + counts.FAIL + " fail \u00b7 " + counts.NEEDS_REVIEW + " needs review";
  }

  function appendRow(item) {
    counts.done += 1;
    if (counts[item.overall] !== undefined) counts[item.overall] += 1;
    var tr = document.createElement("tr");
    var td1 = document.createElement("td"); td1.className = "cell-field"; td1.textContent = item.name;
    var td2 = document.createElement("td");
    var badge = document.createElement("span");
    badge.className = "badge badge-" + item.overall;
    badge.textContent = item.overall_label;
    td2.appendChild(badge);
    var td3 = document.createElement("td"); td3.className = "cell-val"; td3.textContent = item.attention;
    tr.appendChild(td1); tr.appendChild(td2); tr.appendChild(td3);
    tbody.appendChild(tr);
    updateRunning();
  }

  function finalSummary(s) {
    summaryEl.textContent = "Done \u2014 " + s.total + " labels  \u00b7  "
      + s.pass + " pass \u00b7 " + s.fail + " fail \u00b7 " + s.needs_review + " needs review";
  }

  function startStream(jobId, itemCount, pairingErrors) {
    counts.total = itemCount;
    if (pairingErrors && pairingErrors.length) {
      showError(pairingErrors.length + " item(s) couldn't be paired: "
        + pairingErrors.slice(0, 5).map(function (e) { return e.reference + " (" + e.problem + ")"; }).join(", "));
    }
    var es = new EventSource("/batch/" + jobId + "/stream");
    es.addEventListener("item", function (ev) { appendRow(JSON.parse(ev.data)); });
    es.addEventListener("summary", function (ev) { finalSummary(JSON.parse(ev.data)); es.close(); });
    es.onerror = function () { es.close(); };
  }

  function submitBatch(formData) {
    reset();
    fetch("/batch", { method: "POST", body: formData })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) { resultsSec.hidden = true; showError((res.j && res.j.error) || "Couldn't start the batch."); return; }
        startStream(res.j.job_id, res.j.item_count, res.j.pairing_errors);
      })
      .catch(function () { resultsSec.hidden = true; showError("Couldn't reach the server."); });
  }

  if (demoBtn) {
    demoBtn.addEventListener("click", function () {
      var fd = new FormData();
      fd.append("mode", "demo");
      submitBatch(fd);
    });
  }

  if (uploadForm) {
    uploadForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var fd = new FormData();
      fd.append("mode", "upload");
      var csv = document.getElementById("csv-file");
      var imgs = document.getElementById("images-file");
      if (csv && csv.files[0]) fd.append("csv_file", csv.files[0]);
      if (imgs) { for (var i = 0; i < imgs.files.length; i++) fd.append("images", imgs.files[i]); }
      submitBatch(fd);
    });
  }
})();
```

### 6) app/static/style.css — APPEND this block to the END of the file (change nothing above):
```css
/* Batch page */
.back-link { color: var(--accent); text-decoration: none; font-size: 0.95rem; }
.back-link:hover { text-decoration: underline; }
.batch-entry { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-top: 1rem; }
@media (max-width: 680px) { .batch-entry { grid-template-columns: 1fr; } }
.entry-card { background: var(--panel); border-radius: 14px; padding: 1.25rem; }
.entry-card h2 { font-size: 1.15rem; margin: 0 0 0.4rem; }
.entry-card p { margin: 0 0 0.8rem; font-size: 0.95rem; color: var(--muted); }
.entry-card a { color: var(--accent); }
.upload-sub { display: block; font-size: 0.85rem; color: var(--muted); margin: 0.6rem 0 0.25rem; }
.entry-card input[type="file"] { width: 100%; font-size: 0.95rem; }
.primary-button.secondary { background: #33404f; }
.primary-button.secondary:hover { background: #283442; }
#batch-table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
#batch-table th, #batch-table td { text-align: left; padding: 0.7rem 0.7rem; border-bottom: 1px solid var(--border); vertical-align: top; }
#batch-table th { font-size: 0.85rem; color: var(--muted); font-weight: 700; }
```

### 7) app/templates/index.html — add ONE link line. Find:
```html
      <p class="tagline">Upload a label, enter what it should say, and check them against each other.</p>
```
and add a line immediately after it:
```html
      <p><a class="back-link" href="/batch">Checking many labels at once? Use batch mode &rarr;</a></p>
```
Change nothing else in the file.

### 8) tests/test_batch.py — create with:
```python
"""Batch tests (offline — no API key, no network).

Pairing and route-creation are exercised offline; the SSE stream (which calls the
vision model per item) is validated by the user in the browser, not here.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.batch import build_demo_items, build_uploaded_items
from app.main import app

client = TestClient(app)


def test_build_demo_items_pairs_ten():
    items, errors = build_demo_items()
    assert len(items) == 10
    assert errors == []
    assert all(it.image_bytes for it in items)
    assert all("warning" not in it.expected for it in items)


def test_build_uploaded_items_pairs_and_flags():
    csv_text = "image_filename,brand,alcohol_content\nl1.png,BRAND ONE,45%\nl2.png,BRAND TWO,40%\n"
    images = {"l1.png": b"img1", "l3.png": b"orphan"}
    items, errors = build_uploaded_items(csv_text.encode("utf-8"), images)
    assert len(items) == 1
    assert items[0].expected["brand"] == "BRAND ONE"
    refs = {e.reference for e in errors}
    assert "l2.png" in refs
    assert "l3.png" in refs


def test_build_uploaded_items_requires_filename_column():
    import pytest
    with pytest.raises(ValueError):
        build_uploaded_items(b"brand,alcohol_content\nX,45%\n", {})


def test_batch_page_ok():
    r = client.get("/batch")
    assert r.status_code == 200
    assert "Run the demo batch" in r.text


def test_template_csv_download():
    r = client.get("/template.csv")
    assert r.status_code == 200
    assert "image_filename" in r.text


def test_post_batch_demo_creates_job():
    r = client.post("/batch", data={"mode": "demo"})
    assert r.status_code == 200
    body = r.json()
    assert body["item_count"] == 10
    assert body["job_id"]


def test_post_batch_upload_no_csv_errors():
    r = client.post("/batch", data={"mode": "upload"})
    assert r.status_code == 400
    assert "CSV" in r.json()["error"]
```

### 9) DOC SYNC (add-only)
**ASSUMPTIONS_AND_TRADEOFFS.md**
- §B table — append one row (next id after D-21 is D-22):
  `D-22 | **Batch = concurrent + progressively streamed** | Many label+application pairs in one submission; each paired to its image by filename; verified CONCURRENTLY under a capped pool (MAX_CONCURRENCY) reusing verify_label unchanged; each result streamed to the browser via SSE as it finishes; ends with pass/fail/needs-review counts. Two entry modes: a one-click demo (the bundled demo DB paired to the on-disk catalog images) and a CSV+images upload | Meets FR-10/11 + NFR-02 (progressive, never blocked); the same graded engine judges single and batch, so verdicts are identical | Batch requires JavaScript (SSE); jobs are in-memory and dropped after streaming; no image-hash dedup and it runs on PRIMARY_MODEL (not the cheaper BATCH_MODEL) at demo scale | Cheap batch model (Luna), image-hash dedup, per-batch cost ceiling, and a queue/worker system for sustained volume |`
- §E — append one item (next number in sequence): "Batch results stream via SSE and therefore require JavaScript (the single-label page works without it). Batch jobs are held in memory and dropped after the stream completes — no persistence (D-8/CON-02)."

**REQUIREMENTS.md** (ADD-ONLY)
- §4 (FR-10/FR-11 area) — append: "Batch is provided at /batch: many label+application pairs in one submission (a one-click demo over the bundled application DB, or an uploaded CSV of expected values + label images paired by filename), verified concurrently under a capped pool, with per-item results streamed progressively (NFR-02) and a final pass/fail/needs-review summary (FR-11)."

## DO NOT TOUCH
- app/matching/*, app/models.py, app/fields.py, app/verify.py, app/quality_gate.py,
  app/extraction/*, app/config.py, app/data_source.py (CALL it, do not modify), app/cache.py
  (leave the stub — no dedup this pass), tools/*, TEST_PLAN.md, ARCHITECTURE.md,
  BATCH_TRIAGE_DESIGN.md — unchanged.
- Dockerfile, fly.toml (deploy = #7).
- All existing tests (test_matching, test_quality, test_ocr_local, test_vision_image,
  test_app, test_data_source) — unchanged.
- Do NOT git add, commit, or push. Do NOT touch .env or print the API key.

## ACCEPTANCE TEST
1. `pip install -r requirements.txt`  (ensure sse-starlette is installed)
2. `pytest -q` — report the summary. Expected: the 62 existing tests still pass PLUS the
   7 new batch tests = 69 passed. If any existing test fails, STOP and paste it.
3. Boot check: run
   `python -c "from fastapi.testclient import TestClient; from app.main import app; print(TestClient(app).get('/batch').status_code)"`
   and confirm it prints `200`.
4. Paste back: the pytest summary (69 passed), the boot-check `200`, the exact doc lines
   added, confirmation that only the listed files changed, and confirmation that nothing
   was committed or pushed. (The user will then run the server and watch a demo batch
   stream in the browser at /batch.)
