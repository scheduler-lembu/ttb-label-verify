"""Image-hash dedup / cache — a batch cost guard.

Single responsibility: avoid paying for the same extraction twice. Identical
images (by content hash) reuse a prior result instead of triggering another
extraction call. In-memory only for the prototype (no persistence, CON-02);
production would back this with a real store.

Scaffold pass: interface only. No hashing, no storage, no behavior.
"""

from __future__ import annotations


class ImageCache:
    """In-memory content-hash cache mapping image bytes -> prior result.

    Intended methods (implemented later):
        key(image_bytes) -> str          # stable content hash of the image
        get(key) -> LabelResult | None   # cached result, or None on miss
        put(key, result) -> None         # store a freshly computed result
    """

    def key(self, image_bytes: bytes) -> str:
        """Return a stable content hash for ``image_bytes``. Stub."""
        raise NotImplementedError

    def get(self, key: str):
        """Return the cached result for ``key``, or None. Stub."""
        raise NotImplementedError

    def put(self, key: str, result) -> None:
        """Store ``result`` under ``key``. Stub."""
        raise NotImplementedError
