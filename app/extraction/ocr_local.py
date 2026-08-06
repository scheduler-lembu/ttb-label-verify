"""Local OCR: the live Government-Warning cross-check + a reserved offline stub.

This module has two clearly separate parts:

  * LIVE (used today): the Tesseract-based Government-Warning cross-check —
    ``is_tesseract_available``, ``read_warning``, ``warning_reads_agree`` (plus
    their helpers). ``verify.py`` imports these to re-read the warning region
    with literal OCR and compare it to the vision read; on disagreement a
    warning PASS is downgraded to NEEDS_REVIEW. This is the accuracy blend that
    guards the one field where paraphrase is dangerous — it never judges any
    other field.
  * RESERVED (not wired in): the ``LocalOCRExtractor`` class below is a retained,
    not-yet-implemented stub kept as the documented production/offline extraction
    path (ASM-02) — TTB's firewall blocks some outbound ML endpoints, so a
    local/on-tenant OCR engine (or Azure Document Intelligence over a private
    endpoint) is the production-safe alternative. It is NOT used by batch today:
    batch extraction currently runs on ``OpenAIVisionExtractor(BATCH_MODEL)`` (see
    ``router.get_batch_extractor``).

Like every extractor, the reserved class would ONLY transcribe; it never judges.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO

from rapidfuzz import fuzz

from app.extraction.base import Extractor


class LocalOCRExtractor(Extractor):
    """Unimplemented, unused stub reserved for the offline/local-OCR production
    path (ASM-02). Nothing instantiates it today — batch does NOT use it; batch
    runs on ``OpenAIVisionExtractor(BATCH_MODEL)`` via ``router.get_batch_extractor``.
    Kept in place to mark where an on-tenant/offline engine would slot in behind
    the ``Extractor`` interface without touching callers."""

    def extract(self, image_bytes: bytes):
        """Intentional stub — not live. Raises until the offline-OCR path is
        implemented (ASM-02)."""
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Literal-OCR warning cross-check (Handoff #4b-2)
# --------------------------------------------------------------------------- #
# A vision LLM tends to paraphrase / "clean up" text — the false-PASS failure
# mode on the one graded exact field. Tesseract reads the same image literally;
# if the two warning reads disagree, verify.py downgrades a PASS to NEEDS_REVIEW.
# This is a safety-only cross-check: it can never relax a FAIL/REVIEW, and the
# strict verdict itself still runs on the vision read via the unchanged matcher.
# pytesseract / PIL are imported LAZILY so importing this module never fails when
# the binary or wrapper is absent.

_WINDOWS_DEFAULT_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


@dataclass
class LiteralWarningRead:
    """Result of the literal-OCR warning read.
    available: False means Tesseract is not usable -> caller falls back to the
        vision read (no cross-check).
    text: the literal warning region ('GOVERNMENT WARNING...' onward) or None.
    """
    available: bool
    text: "str | None"


def _configure_tesseract() -> None:
    """Point pytesseract at the Windows default install if it is not on PATH.
    No-op if pytesseract is missing or on non-Windows."""
    try:
        import pytesseract
    except ImportError:
        return
    if os.name == "nt" and os.path.exists(_WINDOWS_DEFAULT_TESSERACT):
        pytesseract.pytesseract.tesseract_cmd = _WINDOWS_DEFAULT_TESSERACT


@lru_cache(maxsize=1)
def is_tesseract_available() -> bool:
    """True iff the Tesseract binary can be invoked. Cached (checked once)."""
    try:
        import pytesseract
    except ImportError:
        return False
    _configure_tesseract()
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def read_full_text(image_bytes: bytes) -> str:
    """Literal OCR of the whole image -> raw text (may raise; callers guard)."""
    import pytesseract
    from PIL import Image
    _configure_tesseract()
    with Image.open(BytesIO(image_bytes)) as img:
        return pytesseract.image_to_string(img)


def extract_warning_region(text: "str | None") -> "str | None":
    """Return the warning block: from the case-insensitive 'government warning'
    anchor to the end of the text (the warning is the last statement on a label).
    Pure function — no Tesseract needed.

    Anchoring on the case-insensitive text and taking to the end lets us isolate
    the warning region without vision bounding boxes, relying on the layout
    assumption that the Government Warning is the last statement block (MA-11).
    Case-insensitive match is intentional: we must still capture a title-cased
    prefix so the case check downstream can flag it (MR-05)."""
    if not text:
        return None
    idx = text.lower().find("government warning")
    if idx == -1:
        return None
    region = text[idx:].strip()
    return region or None


def read_warning(image_bytes: bytes) -> LiteralWarningRead:
    """Literal-OCR the image and return the warning region, guarded end to end.

    Two-layer graceful fallback (D-19): if the binary is absent, return
    available=False so verify.py skips the cross-check and trusts the vision read;
    if the binary is present but the read itself throws, return available=True
    with text=None — a present-but-empty read means 'OCR found no warning', which
    warning_reads_agree can still reason about, rather than crashing (NFR-05)."""
    if not is_tesseract_available():
        return LiteralWarningRead(available=False, text=None)
    try:
        return LiteralWarningRead(available=True,
                                  text=extract_warning_region(read_full_text(image_bytes)))
    except Exception:
        return LiteralWarningRead(available=True, text=None)


def _prefix_is_allcaps(text: "str | None") -> "bool | None":
    """True/False if a 'government warning' prefix is present and is/ isn't all
    caps; None if the prefix is absent. Pure function."""
    if not text:
        return None
    idx = text.lower().find("government warning")
    if idx == -1:
        return None
    matched = text[idx: idx + len("government warning")]
    return matched == matched.upper()


def warning_reads_agree(vlm_warning: "str | None", ocr_warning: "str | None",
                        threshold: float) -> bool:
    """Do the vision read and the literal-OCR read of the warning concur?
    Tolerant of OCR noise (case-folded fuzzy body compare) but catches genuine
    wording divergence and prefix-case divergence. Pure function.

    The two divergence checks are deliberately different in spirit: the fuzzy
    body compare uses a threshold so ordinary OCR jitter doesn't trip a false
    disagreement, while the prefix-case check is exact — an all-caps vs. title-case
    'GOVERNMENT WARNING' prefix is precisely the format-evasion the exact rule
    targets (MR-05/MR-06), so a case split there must count as disagreement even
    when the words match."""
    if not vlm_warning and not ocr_warning:
        return True                       # both say "no warning" -> agree
    if bool(vlm_warning) != bool(ocr_warning):
        return False                      # one found a warning, the other didn't
    if fuzz.token_sort_ratio(vlm_warning.lower(), ocr_warning.lower()) < threshold:
        return False                      # wording diverges beyond tolerance
    if _prefix_is_allcaps(vlm_warning) != _prefix_is_allcaps(ocr_warning):
        return False                      # prefix case diverges (evasion catch)
    return True
