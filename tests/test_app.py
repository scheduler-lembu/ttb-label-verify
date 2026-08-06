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


def test_home_serves_the_app():
    # The site home now serves the batch/triage app (Pipeline · Dashboard · History).
    r = client.get("/")
    assert r.status_code == 200
    assert "Run the demo batch" in r.text
    assert 'data-nav="pipeline"' in r.text


def test_single_label_page_kept_at_single():
    # The single-label page is kept in code, unlinked, served at /single.
    r = client.get("/single")
    assert r.status_code == 200
    assert "Verify label" in r.text
    assert "Brand Name" in r.text
    assert "Government Warning has no box" in r.text


def test_health_ok():
    # Liveness/health probe returns {"status": "ok"} (used by the deploy platform).
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_verify_no_file_shows_message():
    # guards FR-01/NFR-06: POST with no image returns a clear "choose a file" message, not a crash.
    r = client.post("/verify", data={"brand": "OLD TOM"})
    assert r.status_code == 200
    assert "Choose a label image" in r.text


def test_verify_blank_image_needs_review():
    # guards FR-09/D-15: a blank upload trips the quality gate -> NEEDS_REVIEW BEFORE any API call, asks for a clearer photo.
    r = client.post(
        "/verify",
        data={"brand": "OLD TOM DISTILLERY", "alcohol_content": "45%"},
        files={"label_image": ("blank.png", _blank_png(), "image/png")},
    )
    assert r.status_code == 200
    assert "Needs review" in r.text
    assert "clearer photo" in r.text
