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
# The one-click demo pairs the demo application DB (~300) to its images here.
_DEMO_LABELS_DIR = "demo_labels"


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
        path = os.path.join(_DEMO_LABELS_DIR, fn)
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
