"""Premium cloud vision extractor (prototype primary / single-label).

Single responsibility: implement the ``Extractor`` interface using OpenAI's
vision-capable LLM. This is the primary engine for single labels — robust to
phone-photo glare/angle/lighting and fast enough for the ~5s bar. The model id
is a **config value** (``PRIMARY_MODEL``); the GPT-5.6 family has an Azure
OpenAI twin, so the prototype → production swap is a config change, not a
rewrite.

This engine ONLY transcribes (using the prompt/schema in ``prompt.py``); it
never judges. Any error/timeout yields ``ok=False`` so the pipeline degrades to
NEEDS_REVIEW rather than crashing or guessing.
"""

from __future__ import annotations

import base64
import json
from io import BytesIO

from app.config import Settings, get_settings
from app.extraction.base import ExtractionResult, Extractor
from app.extraction.prompt import EXPECTED_KEYS, EXTRACTION_PROMPT


def _image_mime(image_bytes: bytes) -> str:
    """Best-effort MIME sniff from magic bytes; default to PNG."""
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/png"


def _prepare_image(image_bytes: bytes, max_dim: int) -> "tuple[bytes, str]":
    """Downscale to a longest side of max_dim if larger; return (bytes, mime).
    Small images pass through unchanged. Fail-safe: on any error, send the
    original bytes so extraction still proceeds."""
    try:
        from PIL import Image
        with Image.open(BytesIO(image_bytes)) as img:
            w, h = img.size
            if max(w, h) <= max_dim:
                return image_bytes, _image_mime(image_bytes)
            scale = max_dim / float(max(w, h))
            resized = img.convert("RGB").resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.LANCZOS,
            )
            buf = BytesIO()
            resized.save(buf, format="JPEG", quality=90)
            return buf.getvalue(), "image/jpeg"
    except Exception:
        return image_bytes, _image_mime(image_bytes)


def _coerce_fields(parsed: dict) -> "dict[str, str | None]":
    """Map a parsed JSON object to exactly the 7 keys (missing/non-str → None)."""
    fields: dict[str, str | None] = {}
    for key in EXPECTED_KEYS:
        value = parsed.get(key)
        if value is None:
            fields[key] = None
        elif isinstance(value, str):
            fields[key] = value
        else:
            # Model returned a non-string (e.g. a number) — stringify defensively.
            fields[key] = str(value)
    return fields


def _parse_json(raw: str) -> dict:
    """Parse the model's text into a JSON object, tolerating stray fences/text."""
    text = (raw or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the first {...} block if the model wrapped it in prose/fences.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no JSON object found in model response")


class OpenAIVisionExtractor(Extractor):
    """OpenAI vision-LLM transcription. Config-selected via API_KEY + a model id.

    ``model`` defaults to ``PRIMARY_MODEL`` (the single-label path, unchanged);
    the batch factory passes ``BATCH_MODEL`` (the cheap tier). Everything else —
    prompt, JSON parsing, downscale, timeout, fail-safe — is identical.
    """

    def __init__(
        self,
        settings: "Settings | None" = None,
        model: "str | None" = None,
        timeout_s: "float | None" = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model = model or self.settings.PRIMARY_MODEL
        # Single-label keeps its fail-fast budget; batch passes a longer timeout.
        self.timeout_s = (
            timeout_s if timeout_s is not None else self.settings.SINGLE_LABEL_TIMEOUT_S
        )

    def extract(self, image_bytes: bytes) -> ExtractionResult:
        """Transcribe the label via the primary vision model, fail-fast.

        One attempt within ``SINGLE_LABEL_TIMEOUT_S``. Any exception/timeout →
        ``ExtractionResult(fields={}, ok=False, error=...)``.
        """
        try:
            # Imported lazily so the rest of the app imports without the SDK.
            from openai import OpenAI

            # Latency hardening (D-20/NFR-01). Each knob keeps a slow call inside
            # the ~5s single-label budget by degrading to NEEDS_REVIEW instead of
            # blowing it: max_retries=0 stops the SDK from silently multiplying a
            # slow request into a retry-balloon (batch retry is the router's job);
            # timeout is the per-request hang ceiling — a stall raises and fails
            # safe rather than hanging.
            client = OpenAI(
                api_key=self.settings.API_KEY,
                timeout=self.timeout_s,
                max_retries=0,  # no silent retry-balloon; batch retry is handled in the router
            )
            # Downscale oversized images before the vision call (D-20): fewer image
            # tokens = faster upload + faster model read, without hurting a legible
            # label. _prepare_image is fail-safe — a resize error sends originals.
            proc_bytes, mime = _prepare_image(image_bytes, self.settings.VISION_MAX_IMAGE_DIM)
            b64 = base64.b64encode(proc_bytes).decode("ascii")
            data_url = f"data:{mime};base64,{b64}"

            response = client.responses.create(
                model=self.model,
                # Low reasoning effort + a hard output-token cap (D-20): this is a
                # transcribe-only job (GA-1), so deep reasoning would only burn
                # latency, and the reply is a small fixed-shape JSON object — no
                # reason to let it run long.
                reasoning={"effort": "low"},  # transcription needs no deep reasoning
                max_output_tokens=self.settings.MAX_OUTPUT_TOKENS,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": EXTRACTION_PROMPT},
                            {"type": "input_image", "image_url": data_url},
                        ],
                    }
                ],
                text={"format": {"type": "json_object"}},
            )

            parsed = _parse_json(response.output_text)
            return ExtractionResult(fields=_coerce_fields(parsed), ok=True)
        except Exception as exc:  # timeout, network, auth, parse — all fail-safe
            return ExtractionResult(fields={}, ok=False, error=str(exc))
