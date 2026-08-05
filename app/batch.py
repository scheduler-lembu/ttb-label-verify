"""Batch runner (the throughput path).

Single responsibility: process many label + application-data pairs in one
submission, governed by throughput/progressiveness (NFR-02), not the single ~5s
bar. Pipeline (see ARCHITECTURE.md §4):

    pair images to CSV rows (by `image_filename`)
      -> pre-screen invalid/blank (reject before spending a call)
      -> image-hash dedup/cache
      -> concurrent extraction on the CHEAP/LOCAL engine (capped worker pool)
      -> per-item deterministic matching
      -> stream each result via SSE as it finishes
      -> final summary counts (PASS / FAIL / NEEDS_REVIEW)

Batch MAY retry serially across providers (per-item latency is relaxed).
Bounded by MAX_BATCH_ITEMS and PER_BATCH_COST_CEILING.

Scaffold pass: signatures only. No pairing, screening, concurrency, or
streaming logic this pass.
"""

from __future__ import annotations


def pair_items(csv_rows: "list[dict]", images: "dict[str, bytes]"):
    """Pair each CSV row to its image by the ``image_filename`` column.

    Unmatched rows and orphan images are flagged (not fatal). Stub.
    """
    raise NotImplementedError


def run_batch(csv_rows: "list[dict]", images: "dict[str, bytes]"):
    """Run a batch and yield per-item results progressively.

    Intended to be an async generator so ``main.py`` can stream each
    ``LabelResult`` over SSE the moment it is ready, then emit a final
    ``BatchResult`` summary. Stub: no behavior this pass.
    """
    raise NotImplementedError
