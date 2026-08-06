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

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from app.batch import (
    build_demo_items,
    build_uploaded_items,
    image_bytes_for,
    run_batch_stream,
)
from app.config import get_settings
from app.data_source import get_application_source
from app.fields import FIELD_REGISTRY
from app.models import LabelResult, ResultState
from app.triage import bucket_tags_for, is_clean
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
FAVICON_PATH = "app/static/favicon.svg"


def _short(text, limit=80):
    if text is None:
        return None
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _build_rows(result: LabelResult):
    rows = []
    for fr in result.fields:
        if fr.field == "warning":
            expected_disp = "matches the official regulation text (27 CFR 16.21)"
            extracted_disp = _short(fr.extracted) if fr.extracted else "— not found —"
        else:
            expected_disp = _short(fr.expected) if fr.expected else "— (blank) —"
            extracted_disp = _short(fr.extracted) if fr.extracted else "— not read —"
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
        return "Problems found — " + ", ".join(parts)
    plural = "s" if review != 1 else ""
    return f"Needs a human look — {review} field{plural} to review"


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
        # Triage: which per-field buckets this label belongs in, whether it
        # auto-clears, and the full per-field readout for the review-screen detail.
        "bucket_tags": [t.model_dump() for t in bucket_tags_for(result)],
        "clean": is_clean(result),
        "fields": _build_rows(result),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _render(request)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/favicon.ico")
async def favicon():
    """Serve the SVG favicon (ends the /favicon.ico 404)."""
    return FileResponse(FAVICON_PATH, media_type="image/svg+xml")


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
    try:
        demo_count = len(get_application_source(get_settings()).list_applications())
    except Exception:
        demo_count = 0
    return templates.TemplateResponse(request, "batch.html", {"demo_count": demo_count})


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

    # The trusted bundled demo (~300) is exempt from the per-upload cap; the cap
    # still guards user CSV uploads (MAX_BATCH_ITEMS).
    if mode != "demo" and len(items) > settings.MAX_BATCH_ITEMS:
        items = items[: settings.MAX_BATCH_ITEMS]

    pairing_errors = [{"reference": e.reference, "problem": e.problem} for e in errors]
    if not items:
        return JSONResponse({"error": "No labels to check.", "pairing_errors": pairing_errors}, status_code=400)

    job_id = uuid.uuid4().hex
    BATCH_JOBS[job_id] = items
    return JSONResponse({"job_id": job_id, "item_count": len(items), "pairing_errors": pairing_errors})


def _sniff_image_mime(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


@app.get("/batch/{job_id}/image/{image_filename}")
async def batch_image(job_id: str, image_filename: str):
    """Serve one label's submitted photo for the triage review screen.

    Safe lookup only: the item is found by EXACT image_filename match within the
    job's stored items (never a filesystem path built from the URL), so unknown
    names or traversal strings return 404.
    """
    items = BATCH_JOBS.get(job_id)
    if items is None:
        return JSONResponse({"error": "Unknown or expired batch."}, status_code=404)
    data = image_bytes_for(items, image_filename)
    if data is None:
        return JSONResponse({"error": "Image not found in this batch."}, status_code=404)
    return Response(content=data, media_type=_sniff_image_mime(data))


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
