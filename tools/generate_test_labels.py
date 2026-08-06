"""Generate the deterministic test-label catalog (HANDOFF #3).

Renders ~10 alcohol-label PNGs into ``test_labels/`` — one fully compliant, the
rest each breaking exactly one matching rule — plus a companion CSV of the
matching application data into ``sample_data/test_labels.csv``. These are the
known inputs the extraction pass (#4) will be verified against.

Single source of truth: one ``LABELS`` list drives BOTH the rendered image text
and the CSV app-data, so the two can't drift. The compliant warning is imported
from ``app.matching.canonical`` — NEVER retyped — and the broken warning variants
are derived from that constant, so the compliant label is guaranteed to match the
stored reference.

Offline only: no AI, no API, no network. Idempotent: re-running overwrites cleanly.

Run from the repo root:
    python tools/generate_test_labels.py
"""

from __future__ import annotations

import csv
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# Make the ``app`` package importable when run as a script (sys.path[0] is tools/).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.matching.canonical import CANONICAL_GOVERNMENT_WARNING  # noqa: E402

TEST_LABELS_DIR = os.path.join(ROOT, "test_labels")
CSV_PATH = os.path.join(ROOT, "sample_data", "test_labels.csv")

# Warning variants derived from the canonical constant (never retyped).
WARNING_CANONICAL = CANONICAL_GOVERNMENT_WARNING
WARNING_TITLECASE = CANONICAL_GOVERNMENT_WARNING.replace(
    "GOVERNMENT WARNING", "Government Warning", 1
)
WARNING_ALTERED = CANONICAL_GOVERNMENT_WARNING.replace(
    "birth defects", "birth defect", 1
)

# CSV header = field-registry keys, same order as batch_template.csv.
CSV_HEADER = [
    "image_filename",
    "brand",
    "alcohol_content",
    "warning",
    "class_type",
    "net_contents",
    "producer",
    "country_of_origin",
]

# --------------------------------------------------------------------------- #
# The catalog. ``printed`` = text rendered on the image; ``app`` = the CSV row
# (what an agent would enter). ``warning`` is one of the module-level variants
# or None (no warning printed). ``post`` triggers image degradation.
# --------------------------------------------------------------------------- #
LABELS = [
    {
        "id": "label_01_compliant",
        "printed": {
            "brand": "OLD TOM DISTILLERY",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content": "45% Alc./Vol. (90 Proof)",
            "net_contents": "750 mL",
            "producer": "Old Tom Distillery, Louisville, KY",
        },
        "warning": WARNING_CANONICAL,
        "app": {
            "brand": "Old Tom Distillery",
            "alcohol_content": "45%",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "net_contents": "750 mL",
            "producer": "Old Tom Distillery, Louisville, KY",
            "country_of_origin": "",
        },
    },
    {
        "id": "label_02_brand_case",
        "printed": {
            "brand": "STONE'S THROW",
            "class_type": "Gin",
            "alcohol_content": "40% Alc./Vol.",
            "net_contents": "750 mL",
            "producer": "Stone's Throw Distillers, Portland, OR",
        },
        "warning": WARNING_CANONICAL,
        "app": {
            "brand": "Stone's Throw",
            "alcohol_content": "40%",
            "class_type": "Gin",
            "net_contents": "750 mL",
            "producer": "Stone's Throw Distillers, Portland, OR",
            "country_of_origin": "",
        },
    },
    {
        "id": "label_03_proof_only",
        "printed": {
            "brand": "IRON GATE WHISKEY",
            "class_type": "Straight Rye Whiskey",
            "alcohol_content": "90 Proof",
            "net_contents": "750 mL",
            "producer": "Iron Gate Distilling, Nashville, TN",
        },
        "warning": WARNING_CANONICAL,
        "app": {
            "brand": "Iron Gate Whiskey",
            "alcohol_content": "45%",
            "class_type": "Straight Rye Whiskey",
            "net_contents": "750 mL",
            "producer": "Iron Gate Distilling, Nashville, TN",
            "country_of_origin": "",
        },
    },
    {
        "id": "label_04_abv_mismatch",
        "printed": {
            "brand": "CEDAR RIDGE VODKA",
            "class_type": "Vodka",
            "alcohol_content": "40% Alc./Vol.",
            "net_contents": "750 mL",
            "producer": "Cedar Ridge Spirits, Swisher, IA",
        },
        "warning": WARNING_CANONICAL,
        "app": {
            "brand": "Cedar Ridge Vodka",
            "alcohol_content": "45%",  # app expects 45%, label shows 40% -> FAIL
            "class_type": "Vodka",
            "net_contents": "750 mL",
            "producer": "Cedar Ridge Spirits, Swisher, IA",
            "country_of_origin": "",
        },
    },
    {
        "id": "label_05_beer_no_abv",
        "printed": {
            "brand": "HARBOR LIGHT LAGER",
            "class_type": "Malt Beverage",
            "alcohol_content": None,  # legitimately no ABV printed
            "net_contents": "12 FL OZ",
            "producer": "Harbor Light Brewing, Seattle, WA",
        },
        "warning": WARNING_CANONICAL,
        "app": {
            "brand": "Harbor Light Lager",
            "alcohol_content": "",  # blank -> NEEDS_REVIEW / blank_expected (D-12)
            "class_type": "Malt Beverage",
            "net_contents": "12 fl oz",
            "producer": "Harbor Light Brewing, Seattle, WA",
            "country_of_origin": "",
        },
    },
    {
        "id": "label_06_warning_titlecase",
        "printed": {
            "brand": "MAPLE HILL RESERVE",
            "class_type": "Blended Whiskey",
            "alcohol_content": "43% Alc./Vol.",
            "net_contents": "750 mL",
            "producer": "Maple Hill Distillery, Burlington, VT",
        },
        "warning": WARNING_TITLECASE,  # title-case prefix -> FAIL
        "app": {
            "brand": "Maple Hill Reserve",
            "alcohol_content": "43%",
            "class_type": "Blended Whiskey",
            "net_contents": "750 mL",
            "producer": "Maple Hill Distillery, Burlington, VT",
            "country_of_origin": "",
        },
    },
    {
        "id": "label_07_warning_altered",
        "printed": {
            "brand": "SILVER CREEK GIN",
            "class_type": "London Dry Gin",
            "alcohol_content": "47% Alc./Vol.",
            "net_contents": "750 mL",
            "producer": "Silver Creek Spirits, Boulder, CO",
        },
        "warning": WARNING_ALTERED,  # one word changed -> FAIL
        "app": {
            "brand": "Silver Creek Gin",
            "alcohol_content": "47%",
            "class_type": "London Dry Gin",
            "net_contents": "750 mL",
            "producer": "Silver Creek Spirits, Boulder, CO",
            "country_of_origin": "",
        },
    },
    {
        "id": "label_08_warning_missing",
        "printed": {
            "brand": "COPPER KETTLE BOURBON",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content": "50% Alc./Vol. (100 Proof)",
            "net_contents": "750 mL",
            "producer": "Copper Kettle Distillery, Bardstown, KY",
        },
        "warning": None,  # no warning printed -> NEEDS_REVIEW / unreadable
        "app": {
            "brand": "Copper Kettle Bourbon",
            "alcohol_content": "50%",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "net_contents": "750 mL",
            "producer": "Copper Kettle Distillery, Bardstown, KY",
            "country_of_origin": "",
        },
    },
    {
        "id": "label_09_warning_tiny",
        "printed": {
            "brand": "FOUNDERS OAK RUM",
            "class_type": "Aged Rum",
            "alcohol_content": "40% Alc./Vol.",
            "net_contents": "750 mL",
            "producer": "Founders Oak Distillers, Key West, FL",
        },
        "warning": WARNING_CANONICAL,  # correct text, tiny font (MR-06 deferred)
        "warning_tiny": True,
        "app": {
            "brand": "Founders Oak Rum",
            "alcohol_content": "40%",
            "class_type": "Aged Rum",
            "net_contents": "750 mL",
            "producer": "Founders Oak Distillers, Key West, FL",
            "country_of_origin": "",
        },
    },
    {
        "id": "label_10_degraded",
        "printed": {
            "brand": "OLD TOM DISTILLERY",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content": "45% Alc./Vol. (90 Proof)",
            "net_contents": "750 mL",
            "producer": "Old Tom Distillery, Louisville, KY",
        },
        "warning": WARNING_CANONICAL,
        "post": "degraded",  # rotate ~7 deg + light noise (NFR-05)
        "app": {
            "brand": "Old Tom Distillery",
            "alcohol_content": "45%",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "net_contents": "750 mL",
            "producer": "Old Tom Distillery, Louisville, KY",
            "country_of_origin": "",
        },
    },
]

# Canvas + layout constants.
CANVAS_W, CANVAS_H = 850, 1100
MARGIN = 60


def load_font(size: int, bold: bool = False) -> "ImageFont.FreeTypeFont | ImageFont.ImageFont":
    """Load a TrueType font at ``size``; fall back to PIL default gracefully."""
    candidates = []
    if bold:
        candidates += ["arialbd.ttf", "DejaVuSans-Bold.ttf"]
    candidates += ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf"]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    # Last resort: PIL's built-in bitmap font (size arg supported on Pillow >=10.1).
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> "list[str]":
    """Word-wrap ``text`` to fit ``max_w`` pixels using the font's metrics."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_w:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_label(entry: dict) -> Image.Image:
    """Render one label's text onto a fresh white canvas (before any degradation)."""
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    draw = ImageDraw.Draw(img)
    printed = entry["printed"]
    max_w = CANVAS_W - 2 * MARGIN

    y = 70
    # Brand — large, near the top.
    brand_font = load_font(46, bold=True)
    draw.text((MARGIN, y), printed["brand"], fill="black", font=brand_font)
    y += 95

    # Supporting fields, one per line (skip an absent ABV).
    body_font = load_font(28)
    for key in ("class_type", "alcohol_content", "net_contents", "producer"):
        value = printed.get(key)
        if not value:
            continue
        draw.text((MARGIN, y), value, fill="black", font=body_font)
        y += 50

    # Warning block at the bottom.
    warning = entry.get("warning")
    if warning:
        tiny = entry.get("warning_tiny", False)
        warn_font = load_font(9 if tiny else 20)
        line_h = 13 if tiny else 28
        y += 30
        for line in wrap_text(draw, warning, warn_font, max_w):
            draw.text((MARGIN, y), line, fill="black", font=warn_font)
            y += line_h

    return img


def degrade(img: Image.Image) -> Image.Image:
    """Rotate ~7 degrees and add light noise to simulate an imperfect photo."""
    rotated = img.rotate(-7, expand=True, fillcolor="white")
    try:
        import numpy as np

        arr = np.asarray(rotated).astype(np.int16)
        # Fixed seed keeps the catalog deterministic across runs.
        rng = np.random.default_rng(42)
        noise = rng.normal(0, 12, arr.shape)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(arr, mode="RGB")
    except Exception:
        # numpy unavailable — the rotation alone still exercises NFR-05.
        return rotated


def main() -> None:
    """Render every catalog PNG (degrading where flagged) and write the companion app-data CSV
    from the same LABELS list, so the images and expected values can never drift apart."""
    os.makedirs(TEST_LABELS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    generated = []
    for entry in LABELS:
        img = render_label(entry)
        if entry.get("post") == "degraded":
            img = degrade(img)
        filename = f"{entry['id']}.png"
        out_path = os.path.join(TEST_LABELS_DIR, filename)
        img.save(out_path, "PNG")
        generated.append((filename, os.path.getsize(out_path)))
        entry["_filename"] = filename

    # Write the companion CSV (app-data), driven by the same LABELS list.
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)
        for entry in LABELS:
            app = entry["app"]
            writer.writerow(
                [
                    entry["_filename"],
                    app["brand"],
                    app["alcohol_content"],
                    "",  # warning: matcher compares to the canonical constant (MA-8)
                    app["class_type"],
                    app["net_contents"],
                    app["producer"],
                    app["country_of_origin"],
                ]
            )

    print(f"Generated {len(generated)} label PNGs in {TEST_LABELS_DIR}:")
    for name, size in generated:
        print(f"  {name:32s} {size:>7,} bytes")
    print(f"Wrote application-data CSV: {CSV_PATH}")


if __name__ == "__main__":
    main()
