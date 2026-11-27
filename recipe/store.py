"""A run = one execution of the recipe, saved in runs/<run_id>/.

    runs/<run_id>/
      state.json            phase statuses, usage and cost
      inputs/               copy of the brief and every reference file
      01_brief.json  02_analysis.json  03_plan.json  04_create.json  05_review.json
      images/               raw scenes and composed slides (every attempt is kept)
      final/                deliverable: posts, captions, summary, ZIP

Every phase reads the previous phase's JSON file and writes its own, so a run
can be resumed from any phase after a crash or after a human edits a JSON file.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

PHASES = ["brief", "analysis", "plan", "create", "review", "deliver"]
PHASE_FILES = {name: f"{i:02d}_{name}.json" for i, name in enumerate(PHASES, start=1)}

M = TypeVar("M", bound=BaseModel)
_lock = threading.Lock()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Run:
    def __init__(self, path: Path):
        self.path = path
        self.id = path.name

    # ------------------------------------------------------------ creation

    @classmethod
    def create(cls, runs_dir: Path, slug: str) -> "Run":
        run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{slug}"
        path = runs_dir / run_id
        (path / "inputs").mkdir(parents=True)
        run = cls(path)
        run._write_state({
            "id": run_id,
            "created": now(),
            "phases": {p: {"status": "pending"} for p in PHASES},
            "notes": {},
            "usage": {"claude_input_tokens": 0, "claude_output_tokens": 0, "claude_cache_read_tokens": 0,
                      "images": 0, "claude_cost_usd": 0.0, "gemini_cost_usd": 0.0, "cost_usd": 0.0},
            "log": [],
        })
        return run

    @classmethod
    def load(cls, runs_dir: Path, run_id: str) -> "Run":
        path = runs_dir / run_id
        if not (path / "state.json").exists():
            raise FileNotFoundError(f"Run '{run_id}' does not exist in {runs_dir}")
        return cls(path)

    # ------------------------------------------------------------ state

    @property
    def state(self) -> dict:
        return json.loads((self.path / "state.json").read_text())

    def _write_state(self, state: dict) -> None:
        tmp = self.path / "state.json.tmp"
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
        tmp.replace(self.path / "state.json")  # atomic: readers never see a half-written file

    def update(self, fn) -> dict:
        with _lock:
            state = self.state
            fn(state)
            self._write_state(state)
            return state

    def set_phase(self, phase: str, status: str, **extra) -> None:
        def apply(s):
            entry = s["phases"][phase]
            entry["status"] = status
            entry.update(extra)
            if status == "running":
                entry["started"] = now()
                entry.pop("error", None)
            if status in ("done", "failed"):
                entry["finished"] = now()
        self.update(apply)

    def log(self, message: str) -> None:
        print(f"[{self.id}] {message}", flush=True)
        self.update(lambda s: s["log"].append(f"{now()} {message}"))

    def add_usage(self, **delta) -> None:
        def apply(s):
            for key, value in delta.items():
                s["usage"][key] = round(s["usage"].get(key, 0) + value, 6)
        self.update(apply)

    # ------------------------------------------------------------ phase outputs

    def phase_file(self, phase: str) -> Path:
        return self.path / PHASE_FILES[phase]

    def save(self, phase: str, model: BaseModel) -> None:
        self.phase_file(phase).write_text(model.model_dump_json(indent=2))

    def read(self, phase: str, model: type[M]) -> M:
        file = self.phase_file(phase)
        if not file.exists():
            raise RuntimeError(f"Phase '{phase}' has no output yet - run it first")
        return model.model_validate_json(file.read_text())

    def has(self, phase: str) -> bool:
        return self.phase_file(phase).exists()

    def invalidate_from(self, phase: str) -> None:
        """Mark a phase and everything after it as pending (their old files stay until overwritten)."""
        later = PHASES[PHASES.index(phase):]

        def apply(s):
            for p in later:
                s["phases"][p] = {"status": "pending"}
        self.update(apply)

    def next_phase(self) -> str | None:
        phases = self.state["phases"]
        return next((p for p in PHASES if phases[p]["status"] != "done"), None)

    def rel(self, path: Path) -> str:
        """Path relative to the run folder (stored in JSON so runs can be moved)."""
        return str(path.relative_to(self.path))
