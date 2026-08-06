"""Single-label acceptance harness (HANDOFF #4).

Runs every label in the test-label catalog through the REAL extraction +
matching pipeline (``verify_label``) and reports, per label: the overall verdict,
each field's verdict(reason), the wall-clock seconds, and MATCH / DIFFERS versus
the TEST_PLAN expectation. Ends with a timing summary.

Requires an OpenAI key in ``.env`` (``API_KEY=sk-...``). If the key is blank the
harness prints a clear message and exits 0 (no crash).

Run from the repo root:
    python tools/run_catalog.py
"""

from __future__ import annotations

import csv
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Windows consoles default to cp1252; force UTF-8 so any transcribed text prints.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from app.config import get_settings  # noqa: E402
from app.fields import FIELD_REGISTRY  # noqa: E402
from app.models import ResultState  # noqa: E402
from app.verify import verify_label  # noqa: E402

CSV_PATH = os.path.join(ROOT, "sample_data", "test_labels.csv")
LABELS_DIR = os.path.join(ROOT, "test_labels")
FIELD_KEYS = [fd.key for fd in FIELD_REGISTRY]

# Expected OVERALL verdict per label, drawn from TEST_PLAN.md §3.
# (Labels 08-10 may legitimately DIFFER depending on how the model reads the
# image — that is a finding about the model, surfaced not hidden.)
EXPECTED_OVERALL = {
    "label_01_compliant.png": ResultState.PASS,
    "label_02_brand_case.png": ResultState.PASS,
    "label_03_proof_only.png": ResultState.PASS,
    "label_04_abv_mismatch.png": ResultState.FAIL,
    "label_05_beer_no_abv.png": ResultState.NEEDS_REVIEW,
    "label_06_warning_titlecase.png": ResultState.FAIL,
    "label_07_warning_altered.png": ResultState.FAIL,
    "label_08_warning_missing.png": ResultState.NEEDS_REVIEW,
    "label_09_warning_tiny.png": ResultState.PASS,
    "label_10_degraded.png": ResultState.PASS,
}


def _load_rows() -> "list[dict]":
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    settings = get_settings()
    if not settings.has_api_key():
        print(
            "No API key found.\n"
            f"Open {os.path.join(ROOT, '.env')} in Notepad, paste your OpenAI key "
            "so the line reads  API_KEY=sk-...  , save, then re-run this harness.\n"
            f"(Model in use: PRIMARY_MODEL={settings.PRIMARY_MODEL})"
        )
        sys.exit(0)

    rows = _load_rows()
    print(f"Running {len(rows)} labels through verify_label "
          f"(PRIMARY_MODEL={settings.PRIMARY_MODEL}, "
          f"timeout={settings.SINGLE_LABEL_TIMEOUT_S}s)\n")

    matched = 0
    times: list[float] = []

    for row in rows:
        filename = row["image_filename"]
        img_path = os.path.join(LABELS_DIR, filename)
        expected = {key: row.get(key, "") for key in FIELD_KEYS}

        if not os.path.exists(img_path):
            print(f"[SKIP] {filename}: image not found")
            continue

        with open(img_path, "rb") as fh:
            image_bytes = fh.read()

        start = time.perf_counter()
        result = verify_label(image_bytes, expected)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

        exp_overall = EXPECTED_OVERALL.get(filename)
        verdict_matches = exp_overall is None or result.overall == exp_overall
        matched += int(verdict_matches)
        flag = "MATCH " if verdict_matches else "DIFFERS"

        print(f"-- {filename}")
        print(f"   overall: {result.overall.value:12s} "
              f"expected: {exp_overall.value if exp_overall else '-':12s} "
              f"[{flag}]   {elapsed:5.2f}s")
        for f in result.fields:
            print(f"      {f.field:18s} {f.verdict.value:12s} {f.reason.value}")
        print()

    print("=" * 64)
    print(f"Verdict match vs TEST_PLAN: {matched}/{len(times)} labels")
    if times:
        print(f"Single-label seconds  min={min(times):.2f}  "
              f"median={statistics.median(times):.2f}  max={max(times):.2f}")


if __name__ == "__main__":
    main()
