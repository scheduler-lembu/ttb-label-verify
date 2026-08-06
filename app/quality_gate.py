"""Pre-extraction image quality gate.

Single responsibility: a cheap, dependency-light pre-flight check of whether an
uploaded image is readable enough to bother extracting. It is the pre-extraction
OpenCV quality gate (D-15): it runs BEFORE any AI/API call, so an undecodable,
blank, or too-blurry upload costs nothing and is routed to the "request a better
image" path (NFR-05) instead of spending a paid vision call on something no human
could read either.

This is a **heuristic** guard, not a calibrated image-quality model:
  * blur  → variance of the Laplacian (low variance = few edges = blurry/out of focus)
  * blank → standard deviation of pixel intensities (near-zero = uniform/empty)
Thresholds are config-tunable (QUALITY_BLUR_THRESHOLD / QUALITY_BLANK_STDDEV).
The gate must never raise: any unexpected failure resolves to "undecodable",
which the caller treats as NEEDS_REVIEW — never a crash, never a guess.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class QualityResult:
    """Outcome of the quality gate.

    ``reason`` is one of: "ok", "blank", "blurry", "undecodable".
    """

    ok: bool
    reason: str


def check_quality(
    image_bytes: bytes,
    *,
    blur_threshold: float,
    blank_stddev: float,
) -> QualityResult:
    """Decide whether ``image_bytes`` is readable enough to extract.

    Returns a ``QualityResult``; never raises. An unreadable image yields
    ``ok=False`` with a specific reason so the caller can tell the user what to
    fix.
    """
    try:
        arr = np.frombuffer(image_bytes, np.uint8)
        if arr.size == 0:
            return QualityResult(False, "undecodable")

        gray = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            return QualityResult(False, "undecodable")

        # Blank/uniform: almost no variation in pixel intensity.
        if float(gray.std()) < blank_stddev:
            return QualityResult(False, "blank")

        # Blur: low Laplacian variance means few sharp edges (out of focus).
        if float(cv2.Laplacian(gray, cv2.CV_64F).var()) < blur_threshold:
            return QualityResult(False, "blurry")

        return QualityResult(True, "ok")
    except Exception:
        # The gate must never raise — degrade to "undecodable" (→ NEEDS_REVIEW).
        return QualityResult(False, "undecodable")
