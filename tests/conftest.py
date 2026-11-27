import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from recipe.config import Settings  # noqa: E402
from recipe.pipeline import Services  # noqa: E402
from tests.fakes import FakeClaude, FakeGemini, FakeWeb  # noqa: E402

EXAMPLE_DIR = ROOT / "inputs" / "zmajska"


@pytest.fixture
def example_brief(tmp_path) -> Path:
    """The demo brief with placeholder Instagram screenshots and captions.

    The real screenshots are kept out of the public repo, so tests never depend on them.
    """
    folder = tmp_path / "brief"
    shutil.copytree(EXAMPLE_DIR, folder, ignore=shutil.ignore_patterns("posts", "captions.txt"))
    (folder / "posts").mkdir()
    for i in range(1, 15):
        Image.new("RGB", (108, 135), (40 + i * 10, 60, 90)).save(folder / "posts" / f"post_{i:02d}.jpg")
    (folder / "captions.txt").write_text("Placeholder caption one.\n---\nPlaceholder caption two.\n")
    return folder / "brief.yaml"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(anthropic_api_key="", gemini_api_key="", runs_dir=tmp_path / "runs",
                    max_images_per_run=30, max_review_retries=2, image_workers=2)


@pytest.fixture
def fakes(settings):
    claude, gemini = FakeClaude(), FakeGemini()
    return Services(settings, claude=claude, gemini=gemini, web=FakeWeb()), claude, gemini
