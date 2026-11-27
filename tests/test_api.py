import io
import json
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import api.main as main
from recipe.pipeline import Services
from tests.conftest import ROOT
from tests.fakes import FakeClaude, FakeGemini, FakeWeb, plan


@pytest.fixture
def client(settings, monkeypatch):
    monkeypatch.setattr(main, "settings", settings)
    fake = Services(settings, claude=FakeClaude(), gemini=FakeGemini(), web=FakeWeb())
    monkeypatch.setattr(main, "services", lambda: fake)
    return TestClient(main.app)


def jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (108, 135), "gray").save(buffer, "JPEG")
    return buffer.getvalue()


def wait_idle(client, run_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f"/api/runs/{run_id}").json()
        if not data["busy"]:
            return data
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_health_reports_missing_keys(client):
    data = client.get("/api/health").json()
    assert data["claude"] is False and data["phases"][0] == "brief"


def test_example_run_through_all_phases(client):
    run_id = client.post("/api/runs/example").json()["id"]
    data = wait_idle(client, run_id)
    assert data["phases"]["brief"]["status"] == "done"
    assert "brief" in data["outputs"]

    assert client.post(f"/api/runs/{run_id}/continue").status_code == 202
    data = wait_idle(client, run_id)
    assert all(p["status"] == "done" for p in data["phases"].values())

    slide = data["outputs"]["deliver"]["posts"][0]["files"][0]
    image = client.get(f"/api/runs/{run_id}/files/{slide}")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert client.get("/api/runs").json()[0]["id"] == run_id


def test_cannot_skip_phases_or_escape_run_folder(client):
    run_id = client.post("/api/runs/example").json()["id"]
    wait_idle(client, run_id)
    assert client.post(f"/api/runs/{run_id}/phases/create").status_code == 409
    assert client.get(f"/api/runs/{run_id}/files/../../etc/passwd").status_code == 404
    assert client.get("/api/runs/nope").status_code == 404


def test_text_edit_reuses_scenes_and_scene_edit_regenerates(client):
    run_id = client.post("/api/runs/example").json()["id"]
    wait_idle(client, run_id)
    client.post(f"/api/runs/{run_id}/continue")
    images_before = wait_idle(client, run_id)["usage"]["images"]

    # Headline and caption edits: slides are re-composited from the saved scenes, no new images
    edited = plan().model_dump()
    edited["posts"][0]["caption"] = "Ručno uređeno"
    edited["posts"][0]["slides"][0]["headline"] = "Novi naslov"
    response = client.put(f"/api/runs/{run_id}/plan", json=edited).json()
    assert response["recomposed"] is True
    data = wait_idle(client, run_id)
    assert data["outputs"]["plan"]["posts"][0]["caption"] == "Ručno uređeno"
    assert data["phases"]["create"]["status"] == "done"
    assert data["phases"]["review"]["status"] == "pending"
    assert data["usage"]["images"] == images_before

    # A new scene prompt needs a new image
    edited["posts"][0]["slides"][0]["scene_prompt"] = "A rooftop terrace at sunset"
    response = client.put(f"/api/runs/{run_id}/plan", json=edited).json()
    assert response["recomposed"] is False and response["phases"]["create"]["status"] == "pending"

    edited["posts"] = edited["posts"][:2]
    assert client.put(f"/api/runs/{run_id}/plan", json=edited).status_code == 422


def test_usage_is_split_between_claude_and_gemini(client):
    run_id = client.post("/api/runs/example").json()["id"]
    wait_idle(client, run_id)
    client.post(f"/api/runs/{run_id}/continue")
    usage = wait_idle(client, run_id)["usage"]
    assert usage["gemini_cost_usd"] > 0
    assert abs(usage["claude_cost_usd"] + usage["gemini_cost_usd"] - usage["cost_usd"]) < 1e-6


def test_create_run_from_uploads(client):
    inputs = ROOT / "inputs" / "zmajska"
    brief = {
        "brand": "Test", "instagram": "https://instagram.com/test", "website": "https://example.com",
        "products": [{"name": "Pale Ale", "image": ""}], "audience": "Adults", "goals": ["Sales"],
    }
    files = [
        ("logo", ("logo.png", (inputs / "logo.png").read_bytes(), "image/png")),
        ("products", ("p.png", (inputs / "products" / "pale_ale.png").read_bytes(), "image/png")),
        ("screenshots", ("s.jpg", jpeg_bytes(), "image/jpeg")),
    ]
    response = client.post("/api/runs", data={"brief": json.dumps(brief), "captions": "Bok!"}, files=files)
    assert response.status_code == 201, response.text
    data = wait_idle(client, response.json()["id"])
    saved = data["outputs"]["brief"]
    assert saved["captions"] == "Bok!" and saved["brief"]["post_screenshots"] == ["post_01.jpg"]


def test_upload_requires_one_photo_per_product(client):
    brief = {"brand": "T", "instagram": "x", "website": "x", "audience": "a", "goals": [],
             "products": [{"name": "A", "image": ""}, {"name": "B", "image": ""}]}
    files = [("logo", ("l.png", b"x", "image/png")), ("products", ("p.png", b"x", "image/png"))]
    response = client.post("/api/runs", data={"brief": json.dumps(brief)}, files=files)
    assert response.status_code == 422


def test_only_phases_of_this_container_are_marked_interrupted(client, settings):
    import socket

    from recipe.store import Run

    run_id = client.post("/api/runs/example").json()["id"]
    wait_idle(client, run_id)
    run = Run.load(settings.runs_dir, run_id)

    # Running in the CLI container: must stay "running"
    run.set_phase("analysis", "running")
    run.update(lambda s: s["phases"]["analysis"].__setitem__("worker", {"host": "cli-container", "pid": 1}))
    assert client.get(f"/api/runs/{run_id}").json()["phases"]["analysis"]["status"] == "running"

    # Started here by a process that no longer exists (server restart): marked failed
    run.update(lambda s: s["phases"]["analysis"].__setitem__("worker", {"host": socket.gethostname(), "pid": 999999}))
    phase = client.get(f"/api/runs/{run_id}").json()["phases"]["analysis"]
    assert phase["status"] == "failed" and "Interrupted" in phase["error"]
