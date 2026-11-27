"""Gemini native image generation (Interactions API) - generates background scenes only.

The real product photo and logo are never generated: they are composited on top
in compose.py, so the label stays pixel-exact.
"""

import base64
import io
from pathlib import Path

from google import genai
from PIL import Image

from .config import PRICES, Settings
from .llm import AIError


class ImageBudgetExceeded(AIError):
    pass


class Gemini:
    def __init__(self, settings: Settings, client: genai.Client | None = None):
        if client is None:
            if not settings.gemini_api_key:
                raise AIError("GEMINI_API_KEY is not set (copy .env.example to .env and add your key)")
            client = genai.Client(api_key=settings.gemini_api_key)
        self.client = client
        self.model = settings.image_model
        self.size = settings.image_size
        self.max_images = settings.max_images_per_run

    def generate(self, prompt: str, *, references: list[Path] = (), aspect_ratio: str = "4:5",
                 images_so_far: int = 0, on_usage=None) -> bytes:
        if images_so_far >= self.max_images:
            raise ImageBudgetExceeded(
                f"Image limit reached ({self.max_images} per run, MAX_IMAGES_PER_RUN) - stopping to protect your credit"
            )

        content: list[dict] | str = prompt
        if references:
            content = [{"type": "text", "text": prompt}] + [_image_part(p) for p in references]

        interaction = self.client.interactions.create(
            model=self.model,
            input=content,
            response_format={"type": "image", "aspect_ratio": aspect_ratio, "image_size": self.size},
        )
        if on_usage:
            cost = PRICES["image"].get(self.size, 0.05)
            on_usage(images=1, gemini_cost_usd=cost, cost_usd=cost)

        image = getattr(interaction, "output_image", None)
        if image is None or not image.data:
            raise AIError("Gemini returned no image (the prompt may have been blocked) - try rephrasing the scene")
        return base64.b64decode(image.data)


def _image_part(path: Path) -> dict:
    img = Image.open(path)
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=88)
    return {"type": "image", "data": base64.b64encode(buf.getvalue()).decode(), "mime_type": "image/jpeg"}
