"""Extraction prompt + expected output schema.

Single responsibility: hold the text of the transcription prompt and the JSON
schema the extractor is asked to return. The prompt instructs the model to
transcribe fields ONLY — no judgment — and to reproduce the Government Warning
**verbatim** (character-for-character), because the downstream exact-match check
(MR-04/05) depends on a faithful transcription. Structured JSON output plus low
temperature keep transcription stable.

Scaffold pass: placeholders only. The final prompt wording and schema are
filled in when extraction is implemented in a later phase.
"""

from __future__ import annotations

# The instruction given to the vision/OCR engine. Transcribe-only; verbatim
# warning. Final wording is authored in a later phase.
EXTRACTION_PROMPT: str = ""  # TODO: author transcribe-only, verbatim-warning prompt at build time

# The JSON shape the engine must return (field keys mirror the field registry).
# Filled in alongside the prompt in a later phase.
EXPECTED_JSON_SCHEMA: dict = {}  # TODO: define {brand, class_type, alcohol_content, net_contents, producer, country_of_origin, warning}
