"""Generate the ~300-label DEMO corpus — offline, deterministic.

Renders ~300 synthetic alcohol-label PNGs into ``demo_labels/`` and writes the
matching application data to ``sample_data/demo_applications.csv`` in lockstep,
so the one-click demo batch can be shown at realistic importer scale (200-300).

This is a SEPARATE, larger demo set — the graded 10-label catalog
(``test_labels/``, ``sample_data/test_labels.csv``, ``tools/generate_test_labels.py``)
is NOT touched. The corpus is "realistic-mostly-clean" with EVERY exception type
represented, PLUS a few deliberate MULTI-FLAG labels (wrong on exactly two fields)
so the built-in demo showcases the multi-flag triage workflow.

Offline only: Pillow + Python stdlib (+ numpy for the degraded variant if
available). No AI, no network. Idempotent — a fixed seed means re-running
overwrites cleanly with the same labels + same filenames + same CSV schema.

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
WARNING_TITLECASE = CANONICAL_GOVERNMENT_WARNING.replace("GOVERNMENT WARNING", "Government Warning", 1)
WARNING_ALTERED = CANONICAL_GOVERNMENT_WARNING.replace("birth defects", "birth defect", 1)

CSV_HEADER = [
    "application_id", "display_name", "image_filename",
    "brand", "alcohol_content", "class_type", "net_contents",
    "producer", "country_of_origin", "beverage_type",
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

# Distinctive brands for the multi-flag labels, so a tester can find them fast.
MULTI_BRANDS = [
    "Double Fault Distillery", "Twin Flaw Distillers", "Two Strikes Spirits",
    "Split Decision Distillery", "Dual Defect Distillers",
]

CLASSES = [
    ("Kentucky Straight Bourbon Whiskey", "spirits"), ("Straight Rye Whiskey", "spirits"),
    ("London Dry Gin", "spirits"), ("Vodka", "spirits"), ("Aged Rum", "spirits"),
    ("Silver Tequila", "spirits"), ("Blended Whiskey", "spirits"),
    ("Single Malt Scotch Whisky", "spirits"),
    ("India Pale Ale", "malt"), ("Amber Lager", "malt"), ("Hefeweizen", "malt"), ("Oatmeal Stout", "malt"),
    ("Cabernet Sauvignon", "wine"), ("Chardonnay", "wine"), ("Pinot Noir", "wine"), ("Sparkling Wine", "wine"),
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
ACCENT_PAIRS = [
    ("Chateau Lumiere", "Château Lumière"), ("Cafe Noir", "Café Noir"),
    ("Maison Elysee", "Maison Élysée"), ("Vina Del Sol", "Viña Del Sol"),
    ("Coeur Sauvage", "Cœur Sauvage"), ("Reserva Anejo", "Reserva Añejo"),
    ("Bodega Corazon", "Bodega Corazón"),
]

# Each multi-flag combo breaks EXACTLY TWO fields (everything else matches).
MULTI_FLAG_COMBOS = [
    ("brand", "alcohol_content"),
    ("brand", "warning_titlecase"),
    ("alcohol_content", "net_contents"),
    ("brand", "net_contents"),
    ("alcohol_content", "warning_altered"),
]

# Category plan (sums to 300): 195 compliant + 100 single-flag + 5 multi-flag.
PLAN = [
    ("compliant", 195),
    ("brand_case", 20), ("brand_diff", 15), ("abv_mismatch", 15),
    ("proof_only", 10), ("beer_no_abv", 10),
    ("warn_titlecase", 10), ("warn_altered", 10), ("warn_missing", 5),
    ("degraded", 5),
    ("multi_flag", 5),
]

CANVAS_W, CANVAS_H = 850, 1100
MARGIN = 64


def pick(pool, k):
    return pool[k % len(pool)]


def _proof(pct: str) -> int:
    return int(round(float(pct) * 2))


def _printed_abv(pct: str, cat: str) -> str:
    """Format the ABV as it appears on the label — spirits also show the (proof) so the
    proof<->percent equivalence path (MR-02) gets exercised; wine/malt show percent only."""
    if cat == "spirits":
        return f"{pct}% Alc./Vol. ({_proof(pct)} Proof)"
    return f"{pct}% Alc./Vol."


def base_fields(seq: int, cls=None):
    """Deterministically pick a self-consistent field set (class -> category -> plausible ABV,
    plus brand/producer/net/country) for sequence ``seq`` from the variety pools."""
    cls = cls or pick(CLASSES, seq * 7 + 3)
    class_type, cat = cls
    pct = pick(ABV_BY_CAT[cat], seq)
    country = IMPORT_COUNTRIES[seq % len(IMPORT_COUNTRIES)] if seq % 11 == 0 else ""
    return {
        "brand": pick(BRANDS, seq), "class_type": class_type, "cat": cat, "pct": pct,
        "net_contents": pick(NETS, seq * 5 + 2), "producer": pick(PRODUCERS, seq * 3 + 1),
        "country_of_origin": country,
    }


def make_item(category: str, seq: int):
    """Return (app_row, printed, warning_text, degrade, broken).

    ``app_row`` = application data; ``printed`` = what's on the image. They differ
    only in the twisted field(s); ``broken`` lists them (used for multi-flag).
    """
    if category == "compliant" and seq == 0:
        base = {
            "brand": "Old Tom Distillery", "class_type": "Kentucky Straight Bourbon Whiskey",
            "cat": "spirits", "pct": "45", "net_contents": "750 mL",
            "producer": "Old Tom Distillery, Louisville, KY", "country_of_origin": "",
        }
    else:
        base = base_fields(seq)

    cat = base["cat"]
    app_brand = printed_brand = base["brand"]
    app_abv = f"{base['pct']}%"
    printed_abv = _printed_abv(base["pct"], cat)
    printed_net = base["net_contents"]
    warning_text = WARNING_CANONICAL
    degrade = False
    broken: list[str] = []

    if category == "compliant":
        pass
    elif category == "brand_case":
        printed_brand = base["brand"].upper()
    elif category == "brand_diff":
        if seq % 2 == 0:
            app_brand, printed_brand = pick(ACCENT_PAIRS, seq)
        else:
            other = pick(BRANDS, seq + 7)
            printed_brand = other if other != app_brand else pick(BRANDS, seq + 8)
    elif category == "abv_mismatch":
        printed_abv = f"{float(base['pct']) - 5:g}% Alc./Vol."
    elif category == "proof_only":
        base["class_type"], cat = SPIRIT_CLASSES[seq % len(SPIRIT_CLASSES)]
        printed_abv = f"{_proof(base['pct'])} Proof"
    elif category == "beer_no_abv":
        base["class_type"], cat = BEER_CLASSES[seq % len(BEER_CLASSES)]
        app_abv = ""
        printed_abv = None
    elif category == "warn_titlecase":
        warning_text = WARNING_TITLECASE
    elif category == "warn_altered":
        warning_text = WARNING_ALTERED
    elif category == "warn_missing":
        warning_text = None
    elif category == "degraded":
        degrade = True
    elif category == "multi_flag":
        # Spirits (so ABV/proof stay sensible), distinctive brand, domestic.
        base["class_type"], cat = SPIRIT_CLASSES[seq % len(SPIRIT_CLASSES)]
        base["pct"] = pick(ABV_BY_CAT["spirits"], seq * 3 + 1)
        base["brand"] = app_brand = printed_brand = MULTI_BRANDS[seq % len(MULTI_BRANDS)]
        base["country_of_origin"] = ""
        app_abv = f"{base['pct']}%"
        printed_abv = _printed_abv(base["pct"], "spirits")
        for tw in MULTI_FLAG_COMBOS[seq % len(MULTI_FLAG_COMBOS)]:
            if tw == "brand":
                other = pick(BRANDS, seq + 11)
                printed_brand = other if other != app_brand else pick(BRANDS, seq + 12)
                broken.append("brand")
            elif tw == "alcohol_content":
                printed_abv = f"{float(base['pct']) - 7:g}% Alc./Vol."
                broken.append("alcohol_content")
            elif tw == "net_contents":
                i = NETS.index(base["net_contents"])
                printed_net = NETS[(i + 2) % len(NETS)]
                if printed_net == base["net_contents"]:
                    printed_net = NETS[(i + 3) % len(NETS)]
                broken.append("net_contents")
            elif tw == "warning_titlecase":
                warning_text = WARNING_TITLECASE
                broken.append("warning")
            elif tw == "warning_altered":
                warning_text = WARNING_ALTERED
                broken.append("warning")

    printed = {
        "brand": printed_brand, "class_type": base["class_type"],
        "alcohol_content": printed_abv, "net_contents": printed_net,
        "producer": base["producer"], "country_of_origin": base["country_of_origin"] or None,
    }
    app_row = {
        "brand": app_brand, "alcohol_content": app_abv, "class_type": base["class_type"],
        "net_contents": base["net_contents"], "producer": base["producer"],
        "country_of_origin": base["country_of_origin"],
        "beverage_type": {"spirits": "distilled spirits", "wine": "wine", "malt": "malt beverage"}[cat],
    }
    return app_row, printed, warning_text, degrade, broken


# --------------------------------------------------------------------------- #
# Rendering — cleaner, more label-like hierarchy.
# --------------------------------------------------------------------------- #
def load_font(size: int, bold: bool = False):
    candidates = (
        (["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial_Bold.ttf"] if bold else [])
        + ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"]
    )
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
    words, lines, current = text.split(), [], ""
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


_INK = (24, 30, 42)
_SUB = (34, 42, 54)
_MUTED = (96, 104, 116)
_WARN = (70, 78, 90)
_RULE = (206, 212, 220)
_RULE_LIGHT = (228, 231, 236)


def render_label(printed: dict, warning_text):
    """Draw one label's ``printed`` fields (+ optional warning block) onto a white canvas."""
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    draw = ImageDraw.Draw(img)
    left, right = MARGIN, CANVAS_W - MARGIN
    max_w = CANVAS_W - 2 * MARGIN

    y = 84
    draw.text((left, y), printed["brand"], fill=_INK, font=load_font(56, bold=True))
    y += 84
    draw.line([(left, y), (right, y)], fill=_RULE, width=2)
    y += 34

    if printed.get("class_type"):
        draw.text((left, y), printed["class_type"], fill=_SUB, font=load_font(36)); y += 60
    if printed.get("alcohol_content"):
        draw.text((left, y), printed["alcohol_content"], fill=_SUB, font=load_font(30)); y += 50
    if printed.get("net_contents"):
        draw.text((left, y), printed["net_contents"], fill=_SUB, font=load_font(30)); y += 54
    if printed.get("producer"):
        draw.text((left, y), printed["producer"], fill=_MUTED, font=load_font(23)); y += 40
    if printed.get("country_of_origin"):
        draw.text((left, y), printed["country_of_origin"], fill=_MUTED, font=load_font(23)); y += 40

    if warning_text:
        wy = max(y + 48, CANVAS_H - 300)
        draw.line([(left, wy - 26), (right, wy - 26)], fill=_RULE_LIGHT, width=1)
        warn_font = load_font(19)
        for line in wrap_text(draw, warning_text, warn_font, max_w):
            draw.text((left, wy), line, fill=_WARN, font=warn_font); wy += 27
    return img


def degrade(img: Image.Image) -> Image.Image:
    """Rotate ~7deg + add fixed-seed noise to simulate an imperfect phone photo (NFR-05).
    Falls back to rotation-only if numpy is unavailable."""
    rotated = img.rotate(-7, expand=True, fillcolor="white")
    try:
        import numpy as np
        arr = np.asarray(rotated).astype(np.int16)
        rng = np.random.default_rng(42)
        arr = np.clip(arr + rng.normal(0, 12, arr.shape), 0, 255).astype(np.uint8)
        return Image.fromarray(arr, mode="RGB")
    except Exception:
        return rotated


def _display_name(app_row: dict, application_id: str) -> str:
    """Human-friendly "Brand — Class/Type" label for the review UI (falls back to id)."""
    brand, class_type = app_row["brand"], app_row["class_type"]
    if brand and class_type:
        return f"{brand} — {class_type}"
    return brand or application_id


def main() -> None:
    """Render every planned label PNG and write the lockstep application CSV, then print a
    per-category breakdown and the multi-flag manifest so a tester can spot-check the corpus."""
    os.makedirs(DEMO_LABELS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    breakdown = {name: 0 for name, _ in PLAN}
    multi_flags = []
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
                app_row, printed, warning_text, do_degrade, broken = make_item(category, seq)

                img = render_label(printed, warning_text)
                if do_degrade:
                    img = degrade(img)
                img.save(os.path.join(DEMO_LABELS_DIR, image_filename), "PNG")
                png_count += 1
                breakdown[category] += 1
                if category == "multi_flag":
                    multi_flags.append((image_filename, app_row["brand"], broken))

                writer.writerow([
                    application_id, _display_name(app_row, application_id), image_filename,
                    app_row["brand"], app_row["alcohol_content"], app_row["class_type"],
                    app_row["net_contents"], app_row["producer"],
                    app_row["country_of_origin"], app_row["beverage_type"],
                ])

    print(f"Generated {png_count} label PNGs in {DEMO_LABELS_DIR}")
    print(f"Wrote {n} application rows to {CSV_PATH}")
    labels = {
        "compliant": "all PASS", "brand_case": "brand PASS (MR-01)",
        "brand_diff": "brand FAIL / NEEDS_REVIEW", "abv_mismatch": "ABV FAIL",
        "proof_only": "ABV PASS (equivalence)", "beer_no_abv": "ABV NEEDS_REVIEW (blank_expected)",
        "warn_titlecase": "warning FAIL (prefix_not_allcaps)", "warn_altered": "warning FAIL (warning_wording)",
        "warn_missing": "warning NEEDS_REVIEW (unreadable)", "degraded": "PASS if read, else NEEDS_REVIEW",
        "multi_flag": "TWO fields flagged (multi-bucket)",
    }
    print("Category breakdown:")
    for name, _ in PLAN:
        print(f"  {breakdown[name]:>3}  {name:<16} -> {labels[name]}")

    print("\nMULTI-FLAG demo labels (each breaks exactly two fields):")
    for fn, brand, broken in multi_flags:
        print(f"  {fn}  —  {brand}  —  breaks: {', '.join(broken)}")


if __name__ == "__main__":
    main()
