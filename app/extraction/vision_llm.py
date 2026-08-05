"""Premium cloud vision extractor (prototype primary / single-label).

Single responsibility: implement the ``Extractor`` interface using a
vision-capable cloud LLM. This is the primary engine for single labels —
robust to phone-photo glare/angle/lighting and fast enough for the ~5s bar.
The chosen model has an **Azure OpenAI twin** (e.g. the GPT-4o family) so the
prototype -> production swap is a config change, not a rewrite.

This engine ONLY transcribes (using the prompt/schema in ``prompt.py``); it
never judges.

Scaffold pass: class + signature only. No API call, no SDK import, no key use.
The provider SDK dependency is added in a LATER phase.
"""

from __future__ import annotations

from app.extraction.base import Extractor


class VisionLLMExtractor(Extractor):
    """Cloud vision-LLM transcription. Config-selected via PRIMARY_MODEL/API_KEY."""

    def extract(self, image_bytes: bytes):
        """Transcribe the label via the cloud vision model. Stub — no call this pass."""
        raise NotImplementedError
