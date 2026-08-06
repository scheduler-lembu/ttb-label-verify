"""Offline tests for the image-hash dedup cache + batch extraction dedup.

No real model, no network — a fake extractor counts calls to prove dedup.
"""

from __future__ import annotations

from app.cache import ImageCache
from app.config import get_settings
from app.extraction import router
from app.extraction.base import ExtractionResult


# --------------------------------------------------------------------------- #
# ImageCache
# --------------------------------------------------------------------------- #
def test_key_stable_and_distinct():
    c = ImageCache()
    assert c.key(b"same-bytes") == c.key(b"same-bytes")
    assert c.key(b"image-A") != c.key(b"image-B")


def test_put_get_roundtrip():
    c = ImageCache()
    k = c.key(b"img")
    value = ExtractionResult(fields={"brand": "X"}, ok=True)
    c.put(k, value)
    assert c.get(k) is value


def test_get_missing_returns_none_no_raise():
    c = ImageCache()
    assert c.get("no-such-key") is None


# --------------------------------------------------------------------------- #
# extract_batch dedup (fake extractor counts calls)
# --------------------------------------------------------------------------- #
class _FakeExtractor:
    def __init__(self, counter, ok=True):
        self.counter = counter
        self.ok = ok

    def extract(self, image_bytes):
        self.counter["n"] += 1
        return ExtractionResult(fields={"brand": "X"}, ok=self.ok)


def test_extract_batch_dedups_same_image(monkeypatch):
    counter = {"n": 0}
    monkeypatch.setattr(router, "get_batch_extractor", lambda: _FakeExtractor(counter))
    cache = ImageCache()

    router.extract_batch(b"same-image", cache)
    router.extract_batch(b"same-image", cache)   # cache hit -> no second call
    assert counter["n"] == 1

    router.extract_batch(b"different-image", cache)  # distinct -> one more call
    assert counter["n"] == 2


def test_extract_batch_does_not_cache_failures(monkeypatch):
    monkeypatch.setattr(router, "_RETRY_BACKOFF_S", 0.0)  # keep the test instant
    counter = {"n": 0}
    monkeypatch.setattr(router, "get_batch_extractor", lambda: _FakeExtractor(counter, ok=False))
    cache = ImageCache()

    r1 = router.extract_batch(b"img", cache)
    r2 = router.extract_batch(b"img", cache)
    assert r1.ok is False and r2.ok is False
    # A failure is not cached, so the SECOND call re-attempts from scratch. Each
    # extract_batch makes 1 + BATCH_MAX_RETRIES attempts (retry is on now).
    per_call = 1 + get_settings().BATCH_MAX_RETRIES
    assert counter["n"] == 2 * per_call


# --------------------------------------------------------------------------- #
# Model wiring: batch = BATCH_MODEL, single = PRIMARY_MODEL
# --------------------------------------------------------------------------- #
def test_batch_extractor_uses_batch_model_single_uses_primary():
    s = get_settings()
    batch = router.get_batch_extractor()
    single = router.get_single_extractor()
    assert batch.model == s.BATCH_MODEL
    assert single.model == s.PRIMARY_MODEL
    # Batch gets the longer timeout; single keeps the fail-fast budget.
    assert batch.timeout_s == s.BATCH_LABEL_TIMEOUT_S
    assert single.timeout_s == s.SINGLE_LABEL_TIMEOUT_S


# --------------------------------------------------------------------------- #
# Batch reliability: bounded retry on transient failure (offline, fast backoff)
# --------------------------------------------------------------------------- #
class _FailThenSucceed:
    """Fails the first ``fail_first`` calls, then succeeds."""

    def __init__(self, counter, fail_first):
        self.counter = counter
        self.fail_first = fail_first

    def extract(self, image_bytes):
        self.counter["n"] += 1
        ok = self.counter["n"] > self.fail_first
        return ExtractionResult(fields={"brand": "X"} if ok else {}, ok=ok,
                                error=None if ok else "transient")


def test_extract_batch_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(router, "_RETRY_BACKOFF_S", 0.0)  # keep the test instant
    counter = {"n": 0}
    monkeypatch.setattr(router, "get_batch_extractor",
                        lambda: _FailThenSucceed(counter, fail_first=1))
    cache = ImageCache()

    result = router.extract_batch(b"img", cache)
    assert result.ok is True
    assert counter["n"] == 2   # one failure + one retry that succeeds


def test_extract_batch_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(router, "_RETRY_BACKOFF_S", 0.0)
    counter = {"n": 0}
    # fail_first huge -> always fails
    monkeypatch.setattr(router, "get_batch_extractor",
                        lambda: _FailThenSucceed(counter, fail_first=999))
    cache = ImageCache()

    result = router.extract_batch(b"img", cache)
    assert result.ok is False
    assert counter["n"] == 1 + get_settings().BATCH_MAX_RETRIES   # capped, no infinite loop


def test_extract_batch_cache_hit_skips_calls_and_retry(monkeypatch):
    monkeypatch.setattr(router, "_RETRY_BACKOFF_S", 0.0)
    counter = {"n": 0}
    monkeypatch.setattr(router, "get_batch_extractor",
                        lambda: _FailThenSucceed(counter, fail_first=0))  # always ok
    cache = ImageCache()

    router.extract_batch(b"img", cache)   # miss -> 1 call, cached
    assert counter["n"] == 1
    router.extract_batch(b"img", cache)   # HIT -> zero calls, no retry
    assert counter["n"] == 1
