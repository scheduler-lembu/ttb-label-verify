"""Batch runner — pairing + concurrent, progressively-streamed verification.

Reuses the finished verification core (app.verify.verify_label_with) — same
quality gate, warning cross-check, and matcher as single-label — but routes
extraction through the CHEAP batch engine (BATCH_MODEL / Luna) with an in-memory
image-hash dedup cache, so a public demo is affordable. Batch is pairing + a
capped concurrency pool + SSE streaming (FR-10/11, NFR-02); each item is paired
to its image by filename, run concurrently under MAX_CONCURRENCY, and yielded the
moment it finishes so the UI can stream rows. The dedup cache stores the
EXTRACTION (not the verdict), so identical images are transcribed once while the
matcher still runs per item against that item's expected values.
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
from dataclasses import dataclass

from app.cache import ImageCache
from app.config import get_settings
from app.data_source import get_application_source
from app.extraction.router import extract_batch
from app.fields import FIELD_REGISTRY
from app.verify import verify_label_with

# Registry keys the agent supplies (the warning is checked against the canonical
# text, not the application — MA-8 — so it is never a supplied expected value).
_EXPECTED_KEYS = [f.key for f in FIELD_REGISTRY if f.key != "warning"]
# The one-click demo pairs the demo application DB (~300) to its images here.
# Absolute path (relative to the repo root) so it resolves regardless of the
# server's working directory.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEMO_LABELS_DIR = os.path.join(_REPO_ROOT, "demo_labels")


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
    """Pair rows from an uploaded CSV to uploaded images by image_filename.

    Pairing is case-insensitive on the filename (case-fold only) and compares
    basenames, so a CSV ``Label1.PNG`` or ``folder/label1.png`` still pairs with
    an uploaded ``label1.png`` — a real tester's export path/casing shouldn't
    cause a silent mis-pair (#10/#11). It deliberately does NOT guess extensions:
    ``label1`` still does not match ``label1.png`` (extension-guessing would
    create silent mis-pairs). If two uploaded images differ only by case (their
    casefolded basenames collide), the pairing is ambiguous and any row naming it
    is skipped with a clear error rather than guessing which file was meant.
    """
    try:
        text = csv_bytes.decode("utf-8-sig")
    except Exception:
        text = csv_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    if "image_filename" not in headers:
        raise ValueError("The CSV needs an 'image_filename' column (see the template).")

    # Casefolded-basename lookup of the uploaded images. A key that two distinct
    # uploads collide on is recorded as ambiguous (we refuse to guess for it).
    lookup: "dict[str, str]" = {}
    ambiguous: set = set()
    for orig in images:
        key = os.path.basename(orig).casefold()
        if key in lookup:
            ambiguous.add(key)
        else:
            lookup[key] = orig

    items: list[BatchItem] = []
    errors: list[PairingError] = []
    referenced = set()
    for row in reader:
        fn = (row.get("image_filename") or "").strip()
        if not fn:
            errors.append(PairingError("(row)", "blank image_filename"))
            continue
        key = os.path.basename(fn).casefold()
        referenced.add(key)
        if key in ambiguous:
            errors.append(PairingError(fn, "ambiguous image filename — two uploaded files differ only by case"))
            continue
        if key not in lookup:
            errors.append(PairingError(fn, "no matching image was uploaded"))
            continue
        expected = {k: (row.get(k) or "").strip() for k in _EXPECTED_KEYS}
        stored_name = os.path.basename(fn)  # path-free so the image/re-ingest URLs resolve
        name = expected.get("brand") or stored_name
        items.append(BatchItem(name=name, image_filename=stored_name,
                               expected=expected, image_bytes=images[lookup[key]]))

    for orig in images:
        if os.path.basename(orig).casefold() not in referenced:
            errors.append(PairingError(orig, "image uploaded but no CSV row uses it"))
    return items, errors


def item_for(items: "list[BatchItem]", image_filename: str) -> "BatchItem | None":
    """Return the job item whose image_filename matches EXACTLY, else None.

    Safe lookup (same discipline as the image endpoint): compares against the
    job's stored filenames — never builds a filesystem path from the URL value,
    so path-traversal strings match nothing and return None.
    """
    for item in items:
        if item.image_filename == image_filename:
            return item
    return None


def image_bytes_for(items: "list[BatchItem]", image_filename: str) -> "bytes | None":
    """Return the stored bytes of the item whose image_filename matches EXACTLY."""
    item = item_for(items, image_filename)
    return item.image_bytes if item is not None else None


async def run_batch_stream(items: "list[BatchItem]", max_concurrency: int):
    """Verify items concurrently (capped), yielding (item, LabelResult) as each finishes.

    Uses the CHEAP batch engine + ONE shared dedup cache for the whole run, so an
    identical image is transcribed once (and reused on repeat runs in the same
    process). The matcher still runs per item against its expected values.
    """
    sem = asyncio.Semaphore(max(1, int(max_concurrency)))
    cache = ImageCache()  # one shared cache for this batch run

    def batch_extract(image_bytes: bytes):
        return extract_batch(image_bytes, cache)

    async def process(item: BatchItem):
        async with sem:
            result = await asyncio.to_thread(
                verify_label_with, item.image_bytes, item.expected, batch_extract
            )
            return item, result

    tasks = [asyncio.create_task(process(it)) for it in items]
    for coro in asyncio.as_completed(tasks):
        yield await coro
