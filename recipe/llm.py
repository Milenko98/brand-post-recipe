"""Claude: brand analysis, content planning and visual QA.

Every call uses structured outputs (client.beta.messages.parse + a Pydantic model),
so the response is a validated object, never free text we have to parse.
"""

import base64
import io
from pathlib import Path
from typing import TypeVar

import anthropic
from PIL import Image
from pydantic import BaseModel

from .config import PRICES, Settings

M = TypeVar("M", bound=BaseModel)

MAX_IMAGE_SIDE = 1568  # larger images are downscaled by the API anyway; sending less saves tokens


class AIError(RuntimeError):
    pass


def text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def image_block(path: Path, max_side: int = MAX_IMAGE_SIDE) -> dict:
    """Load any image (jpeg/png/webp), downscale it and return a base64 content block."""
    img = Image.open(path)
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    if img.mode in ("RGBA", "LA", "P"):
        img.convert("RGBA").save(buf, "PNG")
        media_type = "image/png"
    else:
        img.convert("RGB").save(buf, "JPEG", quality=88)
        media_type = "image/jpeg"
    data = base64.standard_b64encode(buf.getvalue()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


class Claude:
    def __init__(self, settings: Settings, client: anthropic.Anthropic | None = None):
        if client is None:
            if not settings.anthropic_api_key:
                raise AIError("ANTHROPIC_API_KEY is not set (copy .env.example to .env and add your key)")
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=4)
        self.client = client
        self.model = settings.claude_model

    def structured(self, *, system: str, content: list[dict], schema: type[M],
                   effort: str = "high", on_usage=None) -> M:
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=schema,
            output_config={"effort": effort},
            # If a safety classifier declines the request, the API retries it on a fallback model
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )

        if on_usage:
            on_usage(**self._usage(response.usage))

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise AIError(f"Claude declined the request ({getattr(details, 'category', None)})")
        if response.stop_reason == "max_tokens":
            raise AIError("Claude's answer was cut off at max_tokens - shorten the input or raise the limit")
        if response.parsed_output is None:
            raise AIError(f"Claude returned no structured output (stop_reason={response.stop_reason})")
        return response.parsed_output

    def _usage(self, usage) -> dict:
        price = PRICES.get(self.model, PRICES["claude-opus-5-5"])
        inp = usage.input_tokens or 0
        out = usage.output_tokens or 0
        cached = getattr(usage, "cache_read_input_tokens", 0) or 0
        cost = (inp * price["input"] + out * price["output"] + cached * price["cache_read"]) / 1_000_000
        return {"claude_input_tokens": inp, "claude_output_tokens": out,
                "claude_cache_read_tokens": cached, "claude_cost_usd": cost, "cost_usd": cost}
