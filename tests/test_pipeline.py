import json
import shutil
import zipfile

import pytest
from PIL import Image

from recipe.config import Settings
from recipe.images import ImageBudgetExceeded
from recipe.pipeline import Services, run_phase, run_pipeline, start_run
from recipe.schemas import BriefResult, ContentPlan, CreateResult, ReviewResult
from recipe.store import PHASES
from tests.fakes import FakeClaude, FakeGemini, FakeWeb, PostReview, review


def test_full_run_produces_three_posts_and_zip(settings, fakes, example_brief):
    services, claude, gemini = fakes
    run = start_run(example_brief, settings)

    run_pipeline(run, services)

    assert all(p["status"] == "done" for p in run.state["phases"].values())
    final = run.path / "final"
    assert sorted(p.name for p in final.glob("post_*")) == ["post_1", "post_2", "post_3"]
    assert len(list((final / "post_2").glob("slide_*.png"))) == 3
    assert Image.open(final / "post_1" / "slide_1.png").size == (1080, 1350)
    assert "#craft" in (final / "post_1" / "caption.txt").read_text()

    zip_file = next(final.glob("*.zip"))
    names = zipfile.ZipFile(zip_file).namelist()
    assert "phases/03_plan.json" in names and "posts/post_3/slide_1.png" in names

    # 5 slides -> 5 images; analysis + plan + 3 reviews -> 5 Claude calls
    assert len(gemini.prompts) == 5
    assert [c["schema"] for c in claude.calls] == ["BrandAnalysis", "ContentPlan"] + ["PostReview"] * 3
    usage = run.state["usage"]
    assert usage["images"] == 5 and usage["cost_usd"] == pytest.approx(5 * 0.05 + 5 * 0.008)


def test_inputs_are_copied_and_analysis_sees_screenshots_and_web(settings, fakes, example_brief):
    services, claude, _ = fakes
    run = start_run(example_brief, settings)
    run_pipeline(run, services, stop_after="analysis")

    assert (run.path / "inputs" / "pale_ale.png").exists()
    content = claude.calls[0]["content"]
    texts = [b["text"] for b in content if b["type"] == "text"]
    assert sum(b["type"] == "image" for b in content) == 14 + 4 + 1  # screenshots + products + logo
    assert any("FAILED TO LOAD" in t for t in texts)  # failed sources are reported, not hidden
    assert run.state["phases"]["plan"]["status"] == "pending"


def test_plan_product_names_are_normalised(settings, fakes, example_brief):
    services, _, _ = fakes
    run = start_run(example_brief, settings)
    run_pipeline(run, services, stop_after="plan")

    plan = json.loads(run.phase_file("plan").read_text())
    assert plan["posts"][0]["slides"][0]["product"] == "Pale Ale"  # model wrote "pale ale"


def test_review_regenerates_failed_slide_and_keeps_best_attempt(settings, example_brief):
    failing = PostReview(slides=[review(1, ok=False, fix="Put the counter lower")], caption_issues=["Invented price"],
                         revised_caption="Ispravljeno!")
    claude, gemini = FakeClaude(reviews=[failing]), FakeGemini()
    services = Services(settings, claude=claude, gemini=gemini, web=FakeWeb())
    run = start_run(example_brief, settings)

    run_pipeline(run, services)

    created = run.read("create", CreateResult)
    attempts = created.posts[0].slides[0].attempts
    assert [a.attempt for a in attempts] == [1, 2]
    assert attempts[1].feedback == "Put the counter lower"
    assert "Put the counter lower" in gemini.prompts[-1]
    assert created.posts[0].slides[0].final_file == attempts[1].final_file  # score 9 beats 4

    reviewed = run.read("review", ReviewResult).posts[0]
    assert reviewed.regenerated_slides == [1] and reviewed.passed and len(reviewed.rounds) == 2
    assert (run.path / "final" / "post_1" / "caption.txt").read_text().startswith("Ispravljeno!")


def test_image_budget_stops_generation(tmp_path, example_brief):
    settings = Settings(anthropic_api_key="", gemini_api_key="", runs_dir=tmp_path, max_images_per_run=3, image_workers=1)
    services = Services(settings, claude=FakeClaude(), gemini=FakeGemini(), web=FakeWeb())
    run = start_run(example_brief, settings)

    with pytest.raises(ImageBudgetExceeded):
        run_pipeline(run, services)

    assert run.state["usage"]["images"] == 3
    assert run.state["phases"]["create"]["status"] == "failed"


def test_resume_from_phase_with_note_reruns_later_phases(settings, fakes, example_brief):
    services, claude, gemini = fakes
    run = start_run(example_brief, settings)
    run_pipeline(run, services)
    claude.calls.clear()

    run_pipeline(run, services, from_phase="plan", stop_after="plan", note="More humor")

    assert claude.calls[0]["schema"] == "ContentPlan"
    assert "More humor" in claude.calls[0]["content"][-1]["text"]
    assert run.state["notes"]["plan"] == "More humor"
    assert [run.state["phases"][p]["status"] for p in PHASES] == ["done"] * 3 + ["pending"] * 3


def test_phase_order_is_enforced(settings, fakes, example_brief):
    services, _, _ = fakes
    run = start_run(example_brief, settings)
    with pytest.raises(RuntimeError, match="Run these phases first"):
        run_phase(run, "plan", services)


def test_missing_api_key_gives_readable_error(settings, example_brief):
    run = start_run(example_brief, settings)
    services = Services(settings, web=FakeWeb())
    run_phase(run, "brief", services)
    with pytest.raises(Exception, match="ANTHROPIC_API_KEY is not set"):
        run_phase(run, "analysis", services)
    assert "ANTHROPIC_API_KEY" in run.state["phases"]["analysis"]["error"]


def test_missing_optional_inputs_are_skipped(settings, fakes, example_brief):
    shutil.rmtree(example_brief.parent / "posts")
    (example_brief.parent / "captions.txt").unlink()
    run = start_run(example_brief, settings)
    run_pipeline(run, fakes[0], stop_after="brief")

    result = run.read("brief", BriefResult)
    assert result.brief.post_screenshots == [] and result.captions == ""
    assert any("skipped" in line for line in run.state["log"])


def test_recompose_reuses_scenes_without_api_calls(settings, fakes, example_brief):
    from recipe.pipeline import recompose

    services, claude, gemini = fakes
    run = start_run(example_brief, settings)
    run_pipeline(run, services)
    calls = (len(claude.calls), len(gemini.prompts), run.state["usage"]["images"])

    recompose(run)

    assert (len(claude.calls), len(gemini.prompts), run.state["usage"]["images"]) == calls
    assert run.state["phases"]["create"]["status"] == "done"
    assert run.state["phases"]["review"]["status"] == "pending"
    created = run.read("create", CreateResult)
    assert all(a.score is None for p in created.posts for s in p.slides for a in s.attempts)


def test_budget_stops_a_phase_that_cannot_be_paid(settings, fakes, example_brief):
    from recipe.budget import BudgetExceeded, set_balance

    services = fakes[0]
    run = start_run(example_brief, settings)
    run_phase(run, "brief", services)
    set_balance(settings, "claude", 0.3)

    with pytest.raises(BudgetExceeded, match="budget --set claude"):
        run_phase(run, "analysis", services)  # needs ~$0.60, only $0.30 left
    assert run.state["phases"]["analysis"]["status"] == "pending"  # nothing was started


def test_gemini_balance_stops_image_generation(tmp_path, example_brief):
    from recipe.budget import BudgetExceeded, set_balance

    settings = Settings(anthropic_api_key="", gemini_api_key="", runs_dir=tmp_path / "runs",
                        image_size="2K", image_workers=1)
    services = Services(settings, claude=FakeClaude(), gemini=FakeGemini(), web=FakeWeb())
    run = start_run(example_brief, settings)
    run_pipeline(run, services, stop_after="plan")
    set_balance(settings, "gemini", 0.2)

    with pytest.raises(BudgetExceeded):
        run_phase(run, "create", services)  # the plan needs more images than $0.20 pays for
    assert run.state["usage"]["images"] == 0


def test_only_costs_after_the_balance_was_entered_are_subtracted(settings, example_brief):
    from recipe.budget import set_balance, spending

    run = start_run(example_brief, settings)
    run.add_usage(claude_cost_usd=0.5, cost_usd=0.5)  # already included in the console balance
    set_balance(settings, "claude", 2.0)
    run.update(lambda s: s["cost_events"].append({"at": "2999-01-01T00:00:00+00:00", "claude_cost_usd": 0.25}))

    claude, gemini = spending(settings)["claude"], spending(settings)["gemini"]
    assert claude.spent_since == 0.25 and claude.remaining == 1.75
    assert gemini.remaining is None  # no balance entered = no limit


def test_qa_only_suggests_changes_to_a_human_edited_caption(settings, example_brief):
    claude = FakeClaude()
    services = Services(settings, claude=claude, gemini=FakeGemini(), web=FakeWeb())
    run = start_run(example_brief, settings)
    run_pipeline(run, services, stop_after="create")

    # Human edit of post 1, as the API does it: keep the AI plan, save the edited one
    (run.path / "03_plan.ai.json").write_text(run.phase_file("plan").read_text())
    plan = run.read("plan", ContentPlan)
    plan.posts[0].caption = "Blago kiselkasto pivo."
    run.save("plan", plan)

    claude.caption_fix = "Kiselo pivo."
    run_pipeline(run, services)

    posts = run.read("review", ReviewResult).posts
    assert posts[0].caption_edited_by_human and posts[0].final_caption == "Blago kiselkasto pivo."
    assert posts[0].suggested_caption == "Kiselo pivo."
    assert not posts[1].caption_edited_by_human and posts[1].final_caption == "Kiselo pivo."  # AI caption: corrected


def test_runs_started_in_the_same_second_get_unique_ids(settings, example_brief):
    first, second = start_run(example_brief, settings), start_run(example_brief, settings)
    assert first.id != second.id and first.path.exists() and second.path.exists()
