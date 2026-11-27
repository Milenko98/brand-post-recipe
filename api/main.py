"""HTTP API over the same recipe the CLI runs. Interactive docs: http://localhost:8001/docs

Long phases (analysis, image generation) run in a background thread; the UI polls
GET /api/runs/{id} for progress. All state lives in runs/<id>/, so the server can
restart at any time and runs continue from the last finished phase.
"""

import json
import tempfile
import threading
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError

from recipe.config import ROOT, Settings
from recipe.pipeline import Services, run_phase, run_pipeline, start_run
from recipe.schemas import Brief, ContentPlan
from recipe.store import PHASES, Run

app = FastAPI(title="Brand post recipe", description="Instagram brand -> three finished posts")
settings = Settings()

EXAMPLE_BRIEF = ROOT / "inputs" / "zmajska" / "brief.yaml"

_active: set[str] = set()  # runs with a phase currently executing in this process
_active_lock = threading.Lock()


def services() -> Services:
    return Services(settings)


def load_run(run_id: str) -> Run:
    try:
        return Run.load(settings.runs_dir, run_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Run '{run_id}' not found")


def run_in_background(run: Run, fn) -> None:
    with _active_lock:
        if run.id in _active:
            raise HTTPException(409, "A phase of this run is already running")
        _active.add(run.id)

    def target():
        try:
            fn()
        except Exception:
            pass  # the error is stored in state.json by run_phase
        finally:
            with _active_lock:
                _active.discard(run.id)

    threading.Thread(target=target, daemon=True).start()


def run_payload(run: Run) -> dict:
    state = run.state
    # A phase marked "running" with no worker means the server was restarted mid-phase
    if run.id not in _active:
        for phase, info in state["phases"].items():
            if info["status"] == "running":
                run.set_phase(phase, "failed", error="Interrupted (server restarted) - run the phase again")
        state = run.state

    outputs = {}
    for phase in PHASES:
        if state["phases"][phase]["status"] == "done" and run.has(phase):
            outputs[phase] = json.loads(run.phase_file(phase).read_text())
    return {**state, "busy": run.id in _active, "outputs": outputs}


# ---------------------------------------------------------------- endpoints

@app.get("/api/health")
def health():
    return {
        "claude": bool(settings.anthropic_api_key),
        "gemini": bool(settings.gemini_api_key),
        "claude_model": settings.claude_model,
        "image_model": settings.image_model,
        "max_images_per_run": settings.max_images_per_run,
        "phases": PHASES,
    }


@app.get("/api/example-brief")
def example_brief():
    return yaml.safe_load(EXAMPLE_BRIEF.read_text())


@app.get("/api/runs")
def list_runs():
    runs = []
    for path in sorted(settings.runs_dir.glob("*/state.json"), reverse=True):
        state = json.loads(path.read_text())
        runs.append({
            "id": state["id"],
            "created": state["created"],
            "phases": {p: i["status"] for p, i in state["phases"].items()},
            "cost_usd": state["usage"]["cost_usd"],
        })
    return runs


@app.post("/api/runs/example", status_code=201)
def create_example_run():
    """Start a run from the bundled Zmajska pivovara brief (the demonstration inputs)."""
    run = start_run(EXAMPLE_BRIEF, settings)
    run_in_background(run, lambda: run_phase(run, "brief", services()))
    return {"id": run.id}


@app.post("/api/runs", status_code=201)
async def create_run(
    brief: Annotated[str, Form(description="Brief as JSON; file fields are filled from the uploads")],
    logo: Annotated[UploadFile, File()],
    products: Annotated[list[UploadFile], File(description="One cut-out photo per product, same order as brief.products")],
    screenshots: Annotated[list[UploadFile], File()] = [],
    captions: Annotated[str, Form()] = "",
):
    try:
        data = json.loads(brief)
    except json.JSONDecodeError:
        raise HTTPException(422, "brief must be valid JSON")
    if len(products) != len(data.get("products", [])):
        raise HTTPException(422, "Upload exactly one photo per product")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        async def save(upload: UploadFile, name: str) -> str:
            (tmp_path / name).write_bytes(await upload.read())
            return name

        data["logo"] = await save(logo, "logo" + Path(logo.filename or ".png").suffix)
        for i, (product, upload) in enumerate(zip(data["products"], products), start=1):
            product["image"] = await save(upload, f"product_{i}" + Path(upload.filename or ".png").suffix)
        data["post_screenshots"] = [
            await save(s, f"post_{i:02d}" + Path(s.filename or ".jpg").suffix) for i, s in enumerate(screenshots, 1)
        ]
        if captions.strip():
            (tmp_path / "captions.txt").write_text(captions)
            data["captions_file"] = "captions.txt"

        try:
            Brief.model_validate(data)
        except ValidationError as e:
            raise HTTPException(422, json.loads(e.json()))
        (tmp_path / "brief.yaml").write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        run = start_run(tmp_path / "brief.yaml", settings)

    run_in_background(run, lambda: run_phase(run, "brief", services()))
    return {"id": run.id}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return run_payload(load_run(run_id))


class PhaseRequest(BaseModel):
    note: str | None = None


@app.post("/api/runs/{run_id}/phases/{phase}", status_code=202)
def start_phase(run_id: str, phase: str, body: PhaseRequest | None = None):
    """Run (or re-run with a note) one phase. Later phases become pending again."""
    run = load_run(run_id)
    if phase not in PHASES:
        raise HTTPException(404, f"Unknown phase '{phase}'")
    missing = [p for p in PHASES[:PHASES.index(phase)] if run.state["phases"][p]["status"] != "done"]
    if missing:
        raise HTTPException(409, f"Run these phases first: {missing}")
    run_in_background(run, lambda: run_phase(run, phase, services(), body.note if body else None))
    return {"status": "started"}


@app.post("/api/runs/{run_id}/continue", status_code=202)
def continue_run(run_id: str):
    """Run all remaining phases without stopping."""
    run = load_run(run_id)
    if run.next_phase() is None:
        raise HTTPException(409, "All phases are done")
    run_in_background(run, lambda: run_pipeline(run, services()))
    return {"status": "started"}


@app.put("/api/runs/{run_id}/plan")
def edit_plan(run_id: str, plan: ContentPlan):
    """Human edit of the plan before images are generated. Invalidates create/review/deliver."""
    run = load_run(run_id)
    if run.id in _active:
        raise HTTPException(409, "Wait until the current phase finishes")
    if run.state["phases"]["plan"]["status"] != "done":
        raise HTTPException(409, "The plan phase has not finished yet")
    if len(plan.posts) != 3:
        raise HTTPException(422, "The plan must contain exactly 3 posts")
    run.save("plan", plan)
    run.invalidate_from("create")
    run.log("Plan edited by a human")
    return run_payload(run)


@app.get("/api/runs/{run_id}/files/{file_path:path}")
def get_file(run_id: str, file_path: str):
    run = load_run(run_id)
    path = (run.path / file_path).resolve()
    if not path.is_relative_to(run.path.resolve()) or not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path)
