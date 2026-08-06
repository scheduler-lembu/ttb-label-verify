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
    # guards FR-10: CSV rows pair to uploaded images; a CSV row with no image (l2) and an
    # image with no CSV row (l3) are both surfaced as errors, not silently dropped.
    csv_text = "image_filename,brand,alcohol_content\nl1.png,BRAND ONE,45%\nl2.png,BRAND TWO,40%\n"
    images = {"l1.png": b"img1", "l3.png": b"orphan"}
    items, errors = build_uploaded_items(csv_text.encode("utf-8"), images)
    assert len(items) == 1
    assert items[0].expected["brand"] == "BRAND ONE"
    refs = {e.reference for e in errors}
    assert "l2.png" in refs
    assert "l3.png" in refs


def test_build_uploaded_items_requires_filename_column():
    # guards NFR-06: a CSV missing the image_filename column raises a clear ValueError, not a crash.
    import pytest
    with pytest.raises(ValueError):
        build_uploaded_items(b"brand,alcohol_content\nX,45%\n", {})


def test_batch_page_ok():
    # guards FR-10: the batch page renders and offers the one-click demo run.
    r = client.get("/batch")
    assert r.status_code == 200
    assert "Run the demo batch" in r.text


def test_template_csv_download():
    # guards FR-10: the downloadable upload template carries the required image_filename column.
    r = client.get("/template.csv")
    assert r.status_code == 200
    assert "image_filename" in r.text


def test_post_batch_demo_creates_job():
    # guards FR-10/FR-11: POST /batch in demo mode creates a job with one item per demo application.
    expected_n = len(build_demo_items()[0])
    r = client.post("/batch", data={"mode": "demo"})
    assert r.status_code == 200
    body = r.json()
    assert body["item_count"] == expected_n
    assert body["job_id"]


def test_post_batch_upload_no_csv_errors():
    # guards NFR-06: upload mode with no CSV returns 400 + a clear message, not a crash.
    r = client.post("/batch", data={"mode": "upload"})
    assert r.status_code == 400
    assert "CSV" in r.json()["error"]


def test_demo_run_image_and_reverify(monkeypatch):
    """Real demo-run path: image + re-ingest resolve a DEMO job (the UAT bug)."""
    from app import verify as verify_mod
    from app.extraction.base import ExtractionResult

    job = client.post("/batch", data={"mode": "demo"}).json()["job_id"]

    im = client.get(f"/batch/{job}/image/demo_0001.png")
    assert im.status_code == 200
    assert im.headers["content-type"] == "image/png"
    assert len(im.content) > 1000
    assert client.get(f"/batch/{job}/image/nope.png").status_code == 404

    def fake_extract(image_bytes):
        return ExtractionResult(fields={
            "brand": "WRONG", "alcohol_content": "45%", "warning": None,
            "class_type": "Kentucky Straight Bourbon Whiskey", "net_contents": "750 mL",
            "producer": "Old Tom Distillery, Louisville, KY", "country_of_origin": "",
        }, ok=True)
    monkeypatch.setattr(verify_mod, "extract_single", fake_extract)

    rv = client.post(f"/batch/{job}/reverify/demo_0001.png")
    assert rv.status_code == 200
    assert set(["fields", "bucket_tags", "clean"]).issubset(rv.json())
    assert client.post(f"/batch/{job}/reverify/nope.png").status_code == 404


def test_stream_keeps_job_after_completion(monkeypatch):
    """The stream must NOT drop the job — image/re-ingest need it after streaming."""
    from app.extraction import router
    from app.extraction.base import ExtractionResult
    from app.main import BATCH_JOBS

    keys = ["brand", "alcohol_content", "warning", "class_type",
            "net_contents", "producer", "country_of_origin"]

    class _Fake:
        def extract(self, image_bytes):
            return ExtractionResult(fields={k: "" for k in keys}, ok=True)

    monkeypatch.setattr(router, "get_batch_extractor", lambda: _Fake())
    items, _ = build_demo_items()
    BATCH_JOBS["streamjob"] = items[:2]

    with client.stream("GET", "/batch/streamjob/stream") as resp:
        assert resp.status_code == 200
        for _ in resp.iter_lines():
            pass

    assert "streamjob" in BATCH_JOBS  # survived streaming (was popped before the fix)
    im = client.get(f"/batch/streamjob/image/{items[0].image_filename}")
    assert im.status_code == 200
    assert im.headers["content-type"].startswith("image/")


def test_reverify_endpoint_offline(monkeypatch):
    """POST /batch/{job}/reverify/{filename} runs the single-label path with a
    MOCKED extractor (no real model) and returns {fields, bucket_tags, clean}."""
    from app import verify as verify_mod
    from app.extraction.base import ExtractionResult
    from app.main import BATCH_JOBS

    # Mock the single-label extractor -> a known read (brand deliberately wrong).
    def fake_extract(image_bytes):
        return ExtractionResult(fields={
            "brand": "A COMPLETELY DIFFERENT BRAND",
            "alcohol_content": "45%", "warning": None,
            "class_type": "Kentucky Straight Bourbon Whiskey", "net_contents": "750 mL",
            "producer": "Old Tom Distillery, Louisville, KY", "country_of_origin": "",
        }, ok=True)
    monkeypatch.setattr(verify_mod, "extract_single", fake_extract)

    items, _ = build_demo_items()
    BATCH_JOBS["reverify-job"] = items
    fn = items[0].image_filename  # demo_0001 (expected brand "Old Tom Distillery")

    r = client.post(f"/batch/reverify-job/reverify/{fn}")
    assert r.status_code == 200
    body = r.json()
    assert set(["fields", "bucket_tags", "clean"]).issubset(body)
    assert body["clean"] is False                       # brand mismatch -> not clean
    assert "brand" in [t["bucket_id"] for t in body["bucket_tags"]]

    # Unknown filename / unknown job -> 404, no crash.
    assert client.post("/batch/reverify-job/reverify/nope.png").status_code == 404
    assert client.post(f"/batch/no-such-job/reverify/{fn}").status_code == 404


# --------------------------------------------------------------------------- #
# Upload hardening (#26): case-insensitive pairing, size skip, truncation notice
# --------------------------------------------------------------------------- #
def test_pairing_is_case_insensitive():
    # guards #10: CSV filename casing differs from the uploaded file -> still pairs
    # (case-fold match), not a silent mis-pair.
    csv_text = "image_filename,brand\nLabel1.PNG,BRAND ONE\n"
    items, errors = build_uploaded_items(csv_text.encode("utf-8"), {"label1.png": b"img1"})
    assert len(items) == 1
    assert items[0].image_bytes == b"img1"
    assert errors == []


def test_pairing_ambiguous_case_is_rejected():
    # guards #10: two uploads that differ ONLY by case -> the row is skipped with an
    # explicit ambiguity error rather than the matcher guessing which file was meant.
    csv_text = "image_filename,brand\nlabel1.png,BRAND ONE\n"
    images = {"label1.png": b"lower", "LABEL1.PNG": b"upper"}
    items, errors = build_uploaded_items(csv_text.encode("utf-8"), images)
    assert items == []
    assert any("ambiguous" in e.problem for e in errors)


def test_pairing_csv_path_is_basenamed():
    # guards #11: a CSV that carries a folder path pairs on the basename with a
    # flat-uploaded image.
    csv_text = "image_filename,brand\nfolder/label1.png,BRAND ONE\n"
    items, errors = build_uploaded_items(csv_text.encode("utf-8"), {"label1.png": b"img1"})
    assert len(items) == 1
    assert items[0].image_filename == "label1.png"  # stored path-free so URLs resolve
    assert errors == []


def test_pairing_no_extension_still_unmatched():
    # guards #11: extensions are NOT guessed -> 'label1' does not match 'label1.png';
    # it surfaces as an unmatched-row error, never a silent (wrong) pair.
    csv_text = "image_filename,brand\nlabel1,BRAND ONE\n"
    items, errors = build_uploaded_items(csv_text.encode("utf-8"), {"label1.png": b"img1"})
    assert items == []
    assert any(e.reference == "label1" and "no matching image" in e.problem for e in errors)


def test_oversized_image_skipped_with_error(monkeypatch):
    # guards #15: an image over MAX_UPLOAD_MB is skipped (not processed) and surfaced
    # as a "too large" notice, while a normal-sized image in the same batch still runs.
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")  # 1 MB cap for the test
    small = b"\x89PNG\r\n\x1a\n" + b"s" * 100
    big = b"\x89PNG\r\n\x1a\n" + b"b" * (1024 * 1024 + 10)  # just over 1 MB
    csv_text = "image_filename,brand\nsmall.png,OK BRAND\nbig.png,TOO BIG\n"
    r = client.post(
        "/batch",
        data={"mode": "upload"},
        files=[
            ("csv_file", ("in.csv", csv_text.encode("utf-8"), "text/csv")),
            ("images", ("small.png", small, "image/png")),
            ("images", ("big.png", big, "image/png")),
        ],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["item_count"] == 1  # only the small image became an item
    problems = [e["problem"] for e in body["pairing_errors"]]
    assert any("too large" in p for p in problems)


def test_batch_truncation_notice(monkeypatch):
    # guards #17: an upload over MAX_BATCH_ITEMS is truncated but the user is TOLD how
    # many were dropped (a visible notice), not silently discarded.
    monkeypatch.setenv("MAX_BATCH_ITEMS", "2")  # cap at 2 for the test
    csv_text = ("image_filename,brand\n"
                "a.png,A\nb.png,B\nc.png,C\n")
    r = client.post(
        "/batch",
        data={"mode": "upload"},
        files=[
            ("csv_file", ("in.csv", csv_text.encode("utf-8"), "text/csv")),
            ("images", ("a.png", b"aaa", "image/png")),
            ("images", ("b.png", b"bbb", "image/png")),
            ("images", ("c.png", b"ccc", "image/png")),
        ],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["item_count"] == 2  # truncated to the cap
    problems = [e["problem"] for e in body["pairing_errors"]]
    assert any("capped at 2" in p and "1 not processed" in p for p in problems)


def test_run_batch_stream_dedups_identical_images(monkeypatch):
    """Two batch items with the SAME image bytes extract exactly ONCE (shared cache).

    Fully offline: a fake batch extractor counts calls (no real model). Serialized
    with max_concurrency=1 so the second item is a deterministic cache hit.
    """
    import asyncio

    from app.batch import BatchItem, run_batch_stream
    from app.extraction import router
    from app.extraction.base import ExtractionResult

    counter = {"n": 0}

    class _Fake:
        def extract(self, image_bytes):
            counter["n"] += 1
            return ExtractionResult(
                fields={k: "" for k in
                        ["brand", "alcohol_content", "warning", "class_type",
                         "net_contents", "producer", "country_of_origin"]},
                ok=True,
            )

    monkeypatch.setattr(router, "get_batch_extractor", lambda: _Fake())

    with open("test_labels/label_01_compliant.png", "rb") as fh:
        img = fh.read()
    items = [
        BatchItem(name="A", image_filename="a.png", expected={"brand": "X"}, image_bytes=img),
        BatchItem(name="B", image_filename="b.png", expected={"brand": "Y"}, image_bytes=img),
    ]

    async def run():
        out = []
        async for pair in run_batch_stream(items, 1):  # serialized -> deterministic hit
            out.append(pair)
        return out

    results = asyncio.run(run())
    assert len(results) == 2
    assert counter["n"] == 1  # identical image transcribed once; second is a cache hit
