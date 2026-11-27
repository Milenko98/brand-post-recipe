"""Runtime settings, read from environment variables (and .env if present)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _int(name: str, default: int) -> int:
    return int(os.getenv(name) or default)


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-opus-5-5"))

    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    image_model: str = field(default_factory=lambda: os.getenv("GEMINI_IMAGE_MODEL", "gemini-nano-banana-2.1"))
    image_size: str = field(default_factory=lambda: os.getenv("GEMINI_IMAGE_SIZE", "2K"))

    # Hard safety limit: a bug in a retry loop can never generate more than this per run
    max_images_per_run: int = field(default_factory=lambda: _int("MAX_IMAGES_PER_RUN", 30))
    # How many times the review phase may regenerate a slide that failed QA
    max_review_retries: int = field(default_factory=lambda: _int("MAX_REVIEW_RETRIES", 2))
    # Parallel image generations in the create phase
    image_workers: int = field(default_factory=lambda: _int("IMAGE_WORKERS", 3))

    runs_dir: Path = field(default_factory=lambda: Path(os.getenv("RUNS_DIR", ROOT / "runs")))


# USD prices used only for the cost estimate shown in the CLI / UI
PRICES = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20},  # per 1M tokens
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.10},
    # Per image, gemini-nano-banana-2.1. Calibrated on the billing console: 9 images at 1K cost
    # $0.50 (prompt tokens included), so the list price alone underestimated; 2K/4K scaled alike.
    "image": {"1K": 0.056, "2K": 0.084, "4K": 0.19},
}

# Instagram portrait post (4:5)
POST_SIZE = (1080, 1350)
