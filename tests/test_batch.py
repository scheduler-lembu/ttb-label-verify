"""Batch tests (offline — no API key, no network).

Pairing and route-creation are exercised offline; the SSE stream (which calls the
vision model per item) is validated by the user in the browser, not here.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.batch import build_demo_items, build_uploaded_items
from app.main import app

client = TestClient(app)


def test_build_demo_items_pairs_all():
    # Count-agnostic: every demo application (~300) pairs to an on-disk image.
    from app.config import get_settings
    from app.data_source import get_application_source

    n = len(get_application_source(get_settings()).list_applications())
    items, errors = build_demo_items()
    assert len(items) == n
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
    expected_n = len(build_demo_items()[0])
    r = client.post("/batch", data={"mode": "demo"})
    assert r.status_code == 200
    body = r.json()
    assert body["item_count"] == expected_n
    assert body["job_id"]


def test_post_batch_upload_no_csv_errors():
    r = client.post("/batch", data={"mode": "upload"})
    assert r.status_code == 400
    assert "CSV" in r.json()["error"]
