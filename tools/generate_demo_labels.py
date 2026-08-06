"""Generate the ~300-label DEMO corpus (Handoff #7) — offline, deterministic.

Renders ~300 synthetic alcohol-label PNGs into ``demo_labels/`` and writes the
matching application data to ``sample_data/demo_applications.csv`` in lockstep,
so the one-click demo batch can be shown at realistic importer scale (200-300).

This is a SEPARATE, larger demo set — the graded 10-label catalog
(``test_labels/``, ``sample_data/test_labels.csv``, ``tools/generate_test_labels.py``)
is NOT touched. The corpus is "realistic-mostly-clean" with EVERY exception type
represented, so every future exception-folder has contents.

Offline only: Pillow + Python stdlib (+ numpy for the degraded variant if
available). No AI, no network. Idempotent — a fixed seed means re-running
overwrites cleanly with the same labels.

Run from the repo root:
    python tools/generate_demo_labels.py
"""

from __future__ import annotations

import csv
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.matching.canonical import CANONICAL_GOVERNMENT_WARNING  # noqa: E402

# Fixed seed -> reproducible/idempotent corpus.
random.seed(20260806)

DEMO_LABELS_DIR = os.path.join(ROOT, "demo_labels")
CSV_PATH = os.path.join(ROOT, "sample_data", "demo_applications.csv")

# Warning variants derived from the canonical constant (never retyped).
WARNING_CANONICAL = CANONICAL_GOVERNMENT_WARNING
WARNING_TITLECASE = CANONICAL_GOVERNMENT_WARNING.replace(
    "GOVERNMENT WARNING", "Government Warning", 1
)
WARNING_ALTERED = CANONICAL_GOVERNMENT_WARNING.replace(
    "birth defects", "birth defect", 1
)

CSV_HEADER = [
    "application_id",
    "display_name",
    "image_filename",
    "brand",
    "alcohol_content",
    "class_type",
    "net_contents",
    "producer",
    "country_of_origin",
    "beverage_type",
]

# --------------------------------------------------------------------------- #
# Variety pools (internally consistent between image and CSV row).
# --------------------------------------------------------------------------- #
BRANDS = [
    "Old Tom Distillery", "Stone's Throw", "Iron Gate", "Cedar Ridge",
    "Harbor Light", "Maple Hill", "Silver Creek", "Copper Kettle",
    "Founders Oak", "Blue Mountain", "Red Barn", "Golden Valley",
    "Highland Crest", "Riverbend", "Twin Pines", "Emerald Isle",
    "Black Rock", "White Oak", "Sunset Ridge", "Northern Star",
    "Prairie Wind", "Coastal Bluff", "Amber Fields", "Old Mill", "Granite Peak",
]

# (class/type, beverage category)
CLASSES = [
    ("Kentucky Straight Bourbon Whiskey", "spirits"),
    ("Straight Rye Whiskey", "spirits"),
    ("London Dry Gin", "spirits"),
    ("Vodka", "spirits"),
    ("Aged Rum", "spirits"),
    ("Silver Tequila", "spirits"),
    ("Blended Whiskey", "spirits"),
    ("Single Malt Scotch Whisky", "spirits"),
    ("India Pale Ale", "malt"),
    ("Amber Lager", "malt"),
    ("Hefeweizen", "malt"),
    ("Oatmeal Stout", "malt"),
    ("Cabernet Sauvignon", "wine"),
    ("Chardonnay", "wine"),
    ("Pinot Noir", "wine"),
    ("Sparkling Wine", "wine"),
]
SPIRIT_CLASSES = [c for c in CLASSES if c[1] == "spirits"]
BEER_CLASSES = [c for c in CLASSES if c[1] == "malt"]

PRODUCERS = [
    "Old Tom Distillery, Louisville, KY", "Stone's Throw Distillers, Portland, OR",
    "Iron Gate Distilling, Nashville, TN", "Cedar Ridge Spirits, Swisher, IA",
    "Harbor Light Brewing, Seattle, WA", "Maple Hill Distillery, Burlington, VT",
    "Silver Creek Spirits, Boulder, CO", "Copper Kettle Distillery, Bardstown, KY",
    "Founders Oak Distillers, Key West, FL", "Blue Mountain Cellars, Napa, CA",
    "Red Barn Brewing, Madison, WI", "Golden Valley Winery, Salem, OR",
    "Highland Crest Distillers, Asheville, NC", "Riverbend Spirits, Austin, TX",
    "Twin Pines Brewing, Bend, OR", "Emerald Isle Imports, Boston, MA",
    "Black Rock Distilling, Reno, NV", "White Oak Cellars, Sonoma, CA",
    "Sunset Ridge Winery, Paso Robles, CA", "Northern Star Distillery, Duluth, MN",
    "Prairie Wind Spirits, Lincoln, NE", "Coastal Bluff Brewing, Monterey, CA",
    "Amber Fields Distillers, Lawrence, KS", "Old Mill Distillery, Frankfort, KY",
    "Granite Peak Cellars, Bozeman, MT",
]

NETS = ["750 mL", "355 mL", "1 L", "500 mL", "1.75 L", "12 fl oz"]
IMPORT_COUNTRIES = ["Scotland", "France", "Mexico", "Ireland", "Japan", "Canada"]

ABV_BY_CAT = {
    "spirits": ["40", "43", "45", "46", "47", "50"],
    "wine": ["12.5", "13", "13.5", "14"],
    "malt": ["4.8", "5.2", "5.5", "6.5", "7.2"],
}

# (ascii app value, accented printed value) — for the non-ASCII brand exceptions.
ACCENT_PAIRS = [
    ("Chateau Lumiere", "Château Lumière"),
    ("Cafe Noir", "Café Noir"),
    ("Maison Elysee", "Maison Élysée"),
    ("Vina Del Sol", "Viña Del Sol"),
    ("Coeur Sauvage", "Cœur Sauvage"),
    ("Reserva Anejo", "Reserva Añejo"),
    ("Bodega Corazon", "Bodega Corazón"),
]

# Category plan (sums to 300).
PLAN = [
    ("compliant", 200),
    ("brand_case", 20),
    ("brand_diff", 15),
    ("abv_mismatch", 15),
    ("proof_only", 10),
    ("beer_no_abv", 10),
    ("warn_titlecase", 10),
    ("warn_altered", 10),
    ("warn_missing", 5),
    ("degraded", 5),
]

# Canvas + layout.
CANVAS_W, CANVAS_H = 850, 1100
MARGIN = 60


def pick(pool, k):
    return pool[k % len(pool)]


def _proof(pct: str) -> int:
    return int(round(float(pct) * 2))


def _printed_abv(pct: str, cat: str) -> str:
    if cat == "spirits":
        return f"{pct}% Alc./Vol. ({_proof(pct)} Proof)"
    return f"{pct}% Alc./Vol."


def base_fields(seq: int, cls=None):
    """Build a self-consistent compliant field set for item ``seq``."""
    cls = cls or pick(CLASSES, seq * 7 + 3)
    class_type, cat = cls
    pct = pick(ABV_BY_CAT[cat], seq)
    country = IMPORT_COUNTRIES[seq % len(IMPORT_COUNTRIES)] if seq % 11 == 0 else ""
    return {
        "brand": pick(BRANDS, seq),
        "class_type": class_type,
        "cat": cat,
        "pct": pct,
        "net_contents": pick(NETS, seq * 5 + 2),
        "producer": pick(PRODUCERS, seq * 3 + 1),
        "country_of_origin": country,
    }


def make_item(category: str, seq: int):
    """Return (app_row, printed, warning_text, degrade) for one label.

    ``app_row`` = the application data (what the agent entered).
    ``printed`` = what appears on the rendered image. They differ in exactly the
    one twisted field for exception categories; identical for compliant ones.
    """
    # APP-0001 is pinned to a known compliant label so the data-source contract
    # test (brand "Old Tom Distillery", ABV "45%") stays valid.
    if category == "compliant" and seq == 0:
        base = {
            "brand": "Old Tom Distillery",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "cat": "spirits",
            "pct": "45",
            "net_contents": "750 mL",
            "producer": "Old Tom Distillery, Louisville, KY",
            "country_of_origin": "",
        }
    else:
        base = base_fields(seq)

    cat = base["cat"]
    app_brand = base["brand"]
    printed_brand = base["brand"]
    app_abv = f"{base['pct']}%"
    printed_abv = _printed_abv(base["pct"], cat)
    warning_text = WARNING_CANONICAL
    degrade = False

    if category == "compliant":
        pass  # printed == app

    elif category == "brand_case":
        printed_brand = base["brand"].upper()  # differs only by case

    elif category == "brand_diff":
        if seq % 2 == 0:  # accented / non-ASCII
            app_brand, printed_brand = pick(ACCENT_PAIRS, seq)
        else:  # a genuinely different brand printed on the label
            other = pick(BRANDS, seq + 7)
            if other == app_brand:
                other = pick(BRANDS, seq + 8)
            printed_brand = other

    elif category == "abv_mismatch":
        printed_pct = float(base["pct"]) - 5
        printed_abv = f"{printed_pct:g}% Alc./Vol."  # 5 points off -> FAIL

    elif category == "proof_only":
        base["class_type"], cat = SPIRIT_CLASSES[seq % len(SPIRIT_CLASSES)]
        base["cat"] = cat
        app_abv = f"{base['pct']}%"
        printed_abv = f"{_proof(base['pct'])} Proof"  # proof-only -> equivalence PASS

    elif category == "beer_no_abv":
        base["class_type"], cat = BEER_CLASSES[seq % len(BEER_CLASSES)]
        base["cat"] = cat
        app_abv = ""            # nothing expected
        printed_abv = None      # nothing printed -> blank_expected NEEDS_REVIEW

    elif category == "warn_titlecase":
        warning_text = WARNING_TITLECASE

    elif category == "warn_altered":
        warning_text = WARNING_ALTERED

    elif category == "warn_missing":
        warning_text = None

    elif category == "degraded":
        degrade = True

    printed = {
        "brand": printed_brand,
        "class_type": base["class_type"],
        "alcohol_content": printed_abv,
        "net_contents": base["net_contents"],
        "producer": base["producer"],
        "country_of_origin": base["country_of_origin"] or None,
    }
    app_row = {
        "brand": app_brand,
        "alcohol_content": app_abv,
        "class_type": base["class_type"],
        "net_contents": base["net_contents"],
        "producer": base["producer"],
        "country_of_origin": base["country_of_origin"],
        "beverage_type": {"spirits": "distilled spirits", "wine": "wine",
                          "malt": "malt beverage"}[base["cat"]],
    }
    return app_row, printed, warning_text, degrade


# --------------------------------------------------------------------------- #
# Rendering (mirrors tools/generate_test_labels.py style).
# --------------------------------------------------------------------------- #
def load_font(size: int, bold: bool = False):
    candidates = (["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else []) + [
        "arial.ttf", "Arial.ttf", "DejaVuSans.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def wrap_text(draw, text, font, max_w):
    words = text.split()
    lines, current = [], ""
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


def render_label(printed: dict, warning_text):
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    draw = ImageDraw.Draw(img)
    max_w = CANVAS_W - 2 * MARGIN

    y = 70
    draw.text((MARGIN, y), printed["brand"], fill="black", font=load_font(46, bold=True))
    y += 95

    body = load_font(28)
    for key in ("class_type", "alcohol_content", "net_contents", "producer", "country_of_origin"):
        value = printed.get(key)
        if not value:
            continue
        draw.text((MARGIN, y), value, fill="black", font=body)
        y += 50

    if warning_text:
        warn_font = load_font(20)
        y += 30
        for line in wrap_text(draw, warning_text, warn_font, max_w):
            draw.text((MARGIN, y), line, fill="black", font=warn_font)
            y += 28

    return img


def degrade(img: Image.Image) -> Image.Image:
    rotated = img.rotate(-7, expand=True, fillcolor="white")
    try:
        import numpy as np

        arr = np.asarray(rotated).astype(np.int16)
        rng = np.random.default_rng(42)
        noise = rng.normal(0, 12, arr.shape)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(arr, mode="RGB")
    except Exception:
        return rotated


def _display_name(app_row: dict, application_id: str) -> str:
    brand = app_row["brand"]
    class_type = app_row["class_type"]
    if brand and class_type:
        return f"{brand} — {class_type}"
    if brand:
        return brand
    return application_id


def main() -> None:
    os.makedirs(DEMO_LABELS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    breakdown = {name: 0 for name, _ in PLAN}
    png_count = 0

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)

        n = 0
        for category, count in PLAN:
            for seq in range(count):
                n += 1
                application_id = f"APP-{n:04d}"
                image_filename = f"demo_{n:04d}.png"

                app_row, printed, warning_text, do_degrade = make_item(category, seq)

                img = render_label(printed, warning_text)
                if do_degrade:
                    img = degrade(img)
                img.save(os.path.join(DEMO_LABELS_DIR, image_filename), "PNG")
                png_count += 1
                breakdown[category] += 1

                writer.writerow([
                    application_id,
                    _display_name(app_row, application_id),
                    image_filename,
                    app_row["brand"],
                    app_row["alcohol_content"],
                    app_row["class_type"],
                    app_row["net_contents"],
                    app_row["producer"],
                    app_row["country_of_origin"],
                    app_row["beverage_type"],
                ])

    print(f"Generated {png_count} label PNGs in {DEMO_LABELS_DIR}")
    print(f"Wrote {n} application rows to {CSV_PATH}")
    print("Category breakdown (intended verdict):")
    labels = {
        "compliant": "all PASS",
        "brand_case": "brand PASS (MR-01)",
        "brand_diff": "brand FAIL / NEEDS_REVIEW",
        "abv_mismatch": "ABV FAIL",
        "proof_only": "ABV PASS (equivalence)",
        "beer_no_abv": "ABV NEEDS_REVIEW (blank_expected)",
        "warn_titlecase": "warning FAIL (prefix_not_allcaps)",
        "warn_altered": "warning FAIL (warning_wording)",
        "warn_missing": "warning NEEDS_REVIEW (unreadable)",
        "degraded": "PASS if read, else NEEDS_REVIEW",
    }
    for name, _ in PLAN:
        print(f"  {breakdown[name]:>3}  {name:<16} -> {labels[name]}")


if __name__ == "__main__":
    main()
