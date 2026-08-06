"""Unit tests for the pre-extraction image quality gate.

Fully offline — no API key, no network, no OCR engine. Images are built with
numpy and encoded to PNG bytes via cv2, then run through ``check_quality`` with
the default thresholds.
"""

import cv2
import numpy as np

from app.quality_gate import check_quality

BLUR_THRESHOLD = 60.0
BLANK_STDDEV = 8.0


def _png_bytes(arr: np.ndarray) -> bytes:
    """Encode a grayscale uint8 array to PNG bytes."""
    ok, buf = cv2.imencode(".png", arr)
    assert ok
    return buf.tobytes()


def test_sharp_noise_ok():
    """A high-variance random-noise image passes the gate."""
    arr = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
    result = check_quality(
        _png_bytes(arr), blur_threshold=BLUR_THRESHOLD, blank_stddev=BLANK_STDDEV
    )
    assert result.ok is True
    assert result.reason == "ok"


def test_blank_image_flagged():
    """A solid mid-gray image is flagged as blank."""
    arr = np.full((200, 200), 127, dtype=np.uint8)
    result = check_quality(
        _png_bytes(arr), blur_threshold=BLUR_THRESHOLD, blank_stddev=BLANK_STDDEV
    )
    assert result.ok is False
    assert result.reason == "blank"


def test_blurry_image_flagged():
    """A smooth horizontal gradient has few edges → flagged as blurry."""
    arr = np.tile(np.linspace(0, 255, 200).astype(np.uint8), (200, 1))
    result = check_quality(
        _png_bytes(arr), blur_threshold=BLUR_THRESHOLD, blank_stddev=BLANK_STDDEV
    )
    assert result.ok is False
    assert result.reason == "blurry"


def test_undecodable_bytes():
    """Bytes that are not an image → undecodable, never a crash."""
    result = check_quality(
        b"not an image", blur_threshold=BLUR_THRESHOLD, blank_stddev=BLANK_STDDEV
    )
    assert result.ok is False
    assert result.reason == "undecodable"
