"""Image-hash dedup / cache — a batch cost guard.

Single responsibility: avoid paying to transcribe the same image twice. Identical
images (by content hash) reuse a prior EXTRACTION — the transcribed fields — so
the app never spends a second API call on bytes it has already read this process.

Crucially the cache stores the EXTRACTION (an ``ExtractionResult``), NOT the final
verdict (``LabelResult``). The free deterministic matcher always re-runs against
the *current* expected values, so a cached image checked against different
application data still produces the correct result.

In-memory only for the prototype (no persistence, CON-02 / D-8); lost on process
restart, by design. Small and dependency-free.
"""

from __future__ import annotations

import hashlib
import threading


class ImageCache:
    """In-memory content-hash cache mapping image bytes -> prior extraction."""

    def __init__(self) -> None:
        self._store: dict = {}
        self._lock = threading.Lock()

    def key(self, image_bytes: bytes) -> str:
        """Return a stable content hash (sha256 hexdigest) for ``image_bytes``."""
        return hashlib.sha256(image_bytes).hexdigest()

    def get(self, key: str):
        """Return the cached extraction for ``key``, or None on miss (never raises)."""
        with self._lock:
            return self._store.get(key)

    def put(self, key: str, value) -> None:
        """Store an extraction ``value`` under ``key`` (in memory)."""
        with self._lock:
            self._store[key] = value
