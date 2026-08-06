"""Extraction prompt + expected output schema.

Single responsibility: hold the text of the transcription prompt and the JSON
key set the extractor asks for. The prompt instructs the model to transcribe
fields ONLY — no judgment — and to reproduce the Government Warning **verbatim**
(character-for-character, preserving case and punctuation), because the
downstream exact-match check (MR-04/05) depends on a faithful transcription and
a clean field boundary (MA-10).
"""

from __future__ import annotations

# The registry field keys the model must return (order documents intent).
EXPECTED_KEYS: list[str] = [
    "brand",
    "alcohol_content",
    "warning",
    "class_type",
    "net_contents",
    "producer",
    "country_of_origin",
]

# The JSON shape the engine must return (each value: string or null).
EXPECTED_JSON_SCHEMA: dict = {key: "string | null" for key in EXPECTED_KEYS}

EXTRACTION_PROMPT: str = """\
You are a transcription tool for U.S. alcohol beverage labels. Your ONLY job is
to read the label in the image and transcribe what is printed. You do NOT judge,
correct, complete, or evaluate anything — another system does that.

Return a single JSON object with EXACTLY these seven keys, each a string or null:
  "brand"              - the brand name as printed
  "alcohol_content"    - the alcohol strength exactly as printed (e.g. "45% Alc./Vol. (90 Proof)", "90 Proof", "40% Alc./Vol.")
  "warning"            - the Government Warning statement (see the strict rule below)
  "class_type"         - the class/type designation (e.g. "Kentucky Straight Bourbon Whiskey", "Gin")
  "net_contents"       - the net contents as printed (e.g. "750 mL", "12 FL OZ")
  "producer"           - the bottler/producer name and address as printed
  "country_of_origin"  - the country of origin if printed (imports); otherwise null

Rules:
- Transcribe ONLY what is actually printed on the label. Do not infer, translate,
  reformat, or fill in values from your own knowledge.
- If a field is not present or you cannot read it confidently, return null for
  that field. NEVER guess. A null is safe; a fabricated value is not.
- Preserve the original case, spelling, punctuation, and spacing of each value.

GOVERNMENT WARNING — strict:
- Transcribe the warning EXACTLY, character-for-character, preserving case and
  punctuation. Do NOT correct, complete, normalize, re-case, or "fix" it in any
  way, even if it looks wrong. If the label prints "Government Warning" in title
  case, transcribe it in title case. If a word is altered on the label,
  transcribe the altered word.
- Put ONLY the warning statement itself in the "warning" field. Do NOT scoop in
  neighboring text such as "CONTAINS SULFITES", allergen notes, or the net
  contents. If no warning statement appears on the label, return null.

Respond with the JSON object ONLY — no markdown, no code fences, no commentary.
"""
