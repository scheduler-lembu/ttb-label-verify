"""Matching package — "code judges" half of "AI reads, code judges".

Single responsibility: mark ``app.matching`` as a package. Everything here is
DETERMINISTIC Python. It compares extracted values against expected values
under each field's rule and produces PASS / FAIL / NEEDS_REVIEW. No AI, no
model judgment — this is what makes verdicts auditable, repeatable, and
unit-testable (the graded core).

No business logic in this scaffold pass.
"""
