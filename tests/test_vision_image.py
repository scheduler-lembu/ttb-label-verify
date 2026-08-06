"""Unit tests for the vision-input image preparation (downscale + fail-safe).

Fully offline — Pillow only, no API key, no network. Exercises ``_prepare_image``
and ``_image_mime`` from the vision extractor.
"""

from io import BytesIO

from PIL import Image

from app.extraction.vision_llm import _image_mime, _prepare_image


def _png_bytes(width: int, height: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), (200, 150, 100)).save(buf, format="PNG")
    return buf.getvalue()


def test_small_image_passthrough():
    """An image within the cap is returned unchanged, with a PNG mime."""
    original = _png_bytes(100, 100)
    out_bytes, mime = _prepare_image(original, 1536)
    assert out_bytes == original  # same content, no re-encode
    assert mime == "image/png"
    assert _image_mime(out_bytes) == "image/png"


def test_large_image_downscaled():
    """An oversized image is downscaled so its longest side == the cap (JPEG)."""
    original = _png_bytes(3000, 2000)
    out_bytes, mime = _prepare_image(original, 1536)
    assert mime == "image/jpeg"
    with Image.open(BytesIO(out_bytes)) as img:
        assert max(img.size) == 1536
        assert img.size == (1536, 1024)  # aspect ratio preserved


def test_prepare_image_failsafe():
    """Undecodable bytes return a 2-tuple without raising; original passes through."""
    junk = b"not an image"
    out = _prepare_image(junk, 1536)
    assert isinstance(out, tuple) and len(out) == 2
    assert out[0] == junk
