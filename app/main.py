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
    # Starlette's current API takes `request` as the first positional arg; the
    # context still carries "request" too (harmless/required for older versions).
    return templates.TemplateResponse(request, "index.html", ctx)


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
