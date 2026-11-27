"""Command line entry point.

    python cli.py new inputs/zmajska/brief.yaml                 # run all phases
    python cli.py new inputs/zmajska/brief.yaml --stop-after plan
    python cli.py resume <run_id>                               # continue from the first unfinished phase
    python cli.py resume <run_id> --from plan --note "More humor, less beer-geek jargon"
    python cli.py recompose <run_id>                            # re-composite slides from saved scenes (free)
    python cli.py status <run_id>
    python cli.py list
"""

import argparse
import json
import sys
from pathlib import Path

from recipe.config import Settings
from recipe.llm import AIError
from recipe.pipeline import Services, recompose, run_pipeline, start_run
from recipe.store import PHASES, Run


def print_status(run: Run) -> None:
    state = run.state
    print(f"\nRun {run.id}  ({run.path})")
    for phase in PHASES:
        info = state["phases"][phase]
        mark = {"done": "✔", "failed": "✘", "running": "…"}.get(info["status"], "·")
        error = f"  {info['error']}" if info.get("error") else ""
        print(f"  {mark} {phase:<9} {info['status']}{error}")
    u = state["usage"]
    print(f"  Cost so far: ${u['cost_usd']:.2f}")
    print(f"    Claude  ${u.get('claude_cost_usd', 0):.2f}  ({u['claude_input_tokens']:,} input / "
          f"{u['claude_output_tokens']:,} output tokens)")
    print(f"    Gemini  ${u.get('gemini_cost_usd', 0):.2f}  ({u['images']} images)")


def main() -> int:
    parser = argparse.ArgumentParser(description="AI recipe: Instagram brand -> three finished posts")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="start a new run from a brief YAML file")
    new.add_argument("brief", type=Path)
    new.add_argument("--stop-after", choices=PHASES)

    resume = sub.add_parser("resume", help="continue a saved run")
    resume.add_argument("run_id")
    resume.add_argument("--from", dest="from_phase", choices=PHASES, help="re-run from this phase (and all after it)")
    resume.add_argument("--stop-after", choices=PHASES)
    resume.add_argument("--note", help="feedback for the re-run phase, e.g. what to change in the plan")

    again = sub.add_parser("recompose", help="re-composite slides from saved AI scenes after a text/layout change (no API cost)")
    again.add_argument("run_id")

    status = sub.add_parser("status")
    status.add_argument("run_id")
    sub.add_parser("list")

    args = parser.parse_args()
    settings = Settings()
    services = Services(settings)

    if args.command == "list":
        for path in sorted(settings.runs_dir.glob("*/state.json")):
            run = Run(path.parent)
            done = sum(p["status"] == "done" for p in run.state["phases"].values())
            print(f"{run.id}  {done}/{len(PHASES)} phases")
        return 0

    if args.command == "recompose":
        run = Run.load(settings.runs_dir, args.run_id)
        recompose(run)
        print_status(run)
        print(f"\nRun the review again: python cli.py resume {run.id}")
        return 0

    if args.command == "status":
        print_status(Run.load(settings.runs_dir, args.run_id))
        return 0

    run = start_run(args.brief, settings) if args.command == "new" else Run.load(settings.runs_dir, args.run_id)
    try:
        run_pipeline(run, services, from_phase=getattr(args, "from_phase", None),
                     stop_after=args.stop_after, note=getattr(args, "note", None))
    except (AIError, RuntimeError, ValueError, FileNotFoundError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        print_status(run)
        print(f"\nFix the problem, then: python cli.py resume {run.id}")
        return 1
    print_status(run)
    if run.state["phases"]["deliver"]["status"] == "done":
        print(f"\nFinished posts: {run.path / 'final'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
