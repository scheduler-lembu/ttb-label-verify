"""Single-label orchestrator (the ~5s interactive path).

Single responsibility: run one label through the pipeline
    router -> extractor -> matchers -> assemble LabelResult
under the fail-fast ~5s budget (NFR-01). On extractor failure or timeout the
affected field(s) resolve to NEEDS_REVIEW — there is NO serial cross-provider
retry here, because that would violate the 5-second bar (see ARCHITECTURE.md §3).

Scaffold pass: signature only. No routing, extraction, or matching this pass.
"""

from __future__ import annotations


def verify_single(image_bytes: bytes, expected: "dict[str, str]"):
    """Verify one label image against its expected application-data values.

    Args:
        image_bytes: the uploaded label image.
        expected: field-key -> expected value, from the on-screen form.

    Returns:
        A ``LabelResult`` (see ``app.models``) with a ``FieldResult`` per
        registry field, each showing extracted vs expected, the rule applied,
        and a PASS / FAIL / NEEDS_REVIEW verdict.

    Stub: no behavior this pass.
    """
    raise NotImplementedError
