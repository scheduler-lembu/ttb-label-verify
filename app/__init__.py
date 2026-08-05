"""TTB AI Label Verification prototype — application package.

Single responsibility: mark ``app`` as a Python package. The app follows the
"AI reads, code judges" principle — extraction (``app.extraction``) only
transcribes a label into structured fields; all comparison lives in
deterministic code (``app.matching``). See ARCHITECTURE.md.

No business logic in this scaffold pass.
"""
