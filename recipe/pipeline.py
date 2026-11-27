"""The recipe: six phases, each reading the previous phase's JSON and writing its own.

    brief -> analysis -> plan -> create -> review -> deliver

| phase    | input                              | does                                         | output              |
|----------|------------------------------------|----------------------------------------------|---------------------|
| brief    | inputs/brief.yaml + files          | validates inputs, reads captions, website    | 01_brief.json       |
| analysis | brief, screenshots, captions, web  | Claude: tone, visuals, products, facts       | 02_analysis.json    |
| plan     | brief + analysis                   | Claude: 3 posts, slides, scene prompts, copy | 03_plan.json        |
| create   | plan + product photos + logo       | Gemini scenes + Pillow compositing           | 04_create.json, images/ |
| review   | slides + references + captions     | Claude QA, regenerates failed slides         | 05_review.json      |
| deliver  | everything                         | final folder, captions, summary, ZIP         | 06_deliver.json, final/ |
"""

import io
import re
import shutil
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from PIL import Image
from pydantic import BaseModel

from .budget import MIN_CLAUDE_CALL, check_phase, ensure
from .compose import compose_slide
from .config import PRICES, Settings
from .images import Gemini, ImageBudgetExceeded
from .llm import Claude, image_block, text_block
from .schemas import (BrandAnalysis, Brief, BriefResult, ContentPlan, CreatedPost, CreatedSlide, CreateResult,
                      PostPlan, PostReview, ReviewedPost, ReviewResult, Slide, SlideAttempt)
from .store import PHASES, Run
from .web import WebReader

PROMPTS = Path(__file__).parent / "prompts"
PASS_SCORE = 7


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text()


class Services:
    """External dependencies, created lazily (the brief phase needs no API keys). Tests inject fakes."""

    def __init__(self, settings: Settings, claude=None, gemini=None, web=None):
        self.settings = settings
        self._claude, self._gemini, self._web = claude, gemini, web

    @property
    def claude(self) -> Claude:
        self._claude = self._claude or Claude(self.settings)
        return self._claude

    @property
    def gemini(self) -> Gemini:
        self._gemini = self._gemini or Gemini(self.settings)
        return self._gemini

    @property
    def web(self) -> WebReader:
        self._web = self._web or WebReader()
        return self._web


class DeliverResult(BaseModel):
    folder: str
    zip_file: str
    posts: list[dict]


# ================================================================ starting a run

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "run"


def start_run(brief_file: Path, settings: Settings) -> Run:
    """Create a run folder and copy the brief and every file it references into run/inputs/."""
    brief_file = brief_file.resolve()
    data = yaml.safe_load(brief_file.read_text())
    brief = Brief.model_validate(data)
    run = Run.create(settings.runs_dir, slugify(brief.brand))
    base = brief_file.parent

    def copy(rel: str) -> str:
        src = (base / rel).resolve()
        if not src.exists():
            raise FileNotFoundError(f"File referenced in the brief does not exist: {rel}")
        dst = run.path / "inputs" / Path(rel).name
        shutil.copy2(src, dst)
        return dst.name

    brief.logo = copy(brief.logo)
    for product in brief.products:
        product.image = copy(product.image)
    # Screenshots and captions are optional context (they are not in the public repo),
    # so missing ones are skipped instead of failing the run.
    skipped = [s for s in [*brief.post_screenshots, brief.captions_file] if s and not (base / s).exists()]
    brief.post_screenshots = [copy(s) for s in brief.post_screenshots if s not in skipped]
    brief.captions_file = copy(brief.captions_file) if brief.captions_file and brief.captions_file not in skipped else None

    (run.path / "inputs" / "brief.yaml").write_text(
        yaml.safe_dump(brief.model_dump(), allow_unicode=True, sort_keys=False)
    )
    run.log(f"Run created from {brief_file}")
    if skipped:
        run.log(f"Optional inputs not found, skipped: {skipped}")
    return run


# ================================================================ phases

def phase_brief(run: Run, services: Services, note: str | None) -> BriefResult:
    brief = Brief.model_validate(yaml.safe_load((run.path / "inputs" / "brief.yaml").read_text()))
    inputs = run.path / "inputs"
    missing = [f for f in [brief.logo, *(p.image for p in brief.products), *brief.post_screenshots]
               if not (inputs / f).exists()]
    if missing:
        raise FileNotFoundError(f"Missing input files: {missing}")
    if not brief.products:
        raise ValueError("The brief needs at least one product")

    captions = (inputs / brief.captions_file).read_text() if brief.captions_file else ""
    run.log(f"Reading website {brief.website}")
    sources = services.web.read_site(brief.website, brief.extra_urls)
    run.log(f"Read {sum(s.ok for s in sources)}/{len(sources)} web pages")
    return BriefResult(brief=brief, captions=captions, sources=sources)


def phase_analysis(run: Run, services: Services, note: str | None) -> BrandAnalysis:
    b = run.read("brief", BriefResult)
    inputs = run.path / "inputs"

    content = [text_block("## Brief\n" + b.brief.model_dump_json(indent=2, exclude={"post_screenshots"}))]
    if b.captions:
        content.append(text_block("## Captions of recent posts (verbatim)\n" + b.captions))
    for s in b.sources:
        content.append(text_block(
            f"## Website page: {s.url}\n" + (f"Title: {s.title}\n{s.text}" if s.ok else f"FAILED TO LOAD: {s.error}")
        ))
    content.append(text_block(f"## Instagram post screenshots ({len(b.brief.post_screenshots)})"))
    for name in b.brief.post_screenshots:
        content += [text_block(f"Screenshot: {name}"), image_block(inputs / name)]
    for product in b.brief.products:
        content += [text_block(f"Product photo: {product.name} ({product.notes})"), image_block(inputs / product.image)]
    content += [text_block("Brand logo:"), image_block(inputs / b.brief.logo)]
    if note:
        content.append(text_block(f"## Reviewer note for this attempt\n{note}"))

    run.log("Claude is analysing the brand")
    ensure(services.settings, "claude", MIN_CLAUDE_CALL, "the brand analysis")
    return services.claude.structured(system=prompt("analysis"), content=content, schema=BrandAnalysis,
                                      effort="high", on_usage=run.add_usage)


def phase_plan(run: Run, services: Services, note: str | None) -> ContentPlan:
    (run.path / "03_plan.ai.json").unlink(missing_ok=True)  # a new AI plan replaces any edited one
    b = run.read("brief", BriefResult)
    analysis = run.read("analysis", BrandAnalysis)
    inputs = run.path / "inputs"

    content = [
        text_block("## Brief\n" + b.brief.model_dump_json(indent=2, exclude={"post_screenshots"})),
        text_block("## Brand analysis\n" + analysis.model_dump_json(indent=2)),
        text_block("## Products available for compositing (use these exact names in `product`)\n"
                   + "\n".join(f"- {p.name}" for p in b.brief.products)),
    ]
    for product in b.brief.products:
        content += [text_block(f"Product photo: {product.name}"), image_block(inputs / product.image)]
    if note:
        content.append(text_block(f"## Reviewer note for this attempt\n{note}"))

    run.log("Claude is planning three posts")
    ensure(services.settings, "claude", MIN_CLAUDE_CALL, "the content plan")
    plan = services.claude.structured(system=prompt("plan"), content=content, schema=ContentPlan,
                                      effort="high", on_usage=run.add_usage)
    if len(plan.posts) != 3:
        raise ValueError(f"The plan must contain exactly 3 posts, got {len(plan.posts)}")
    for i, post in enumerate(plan.posts, start=1):
        post.number = i
        for slide in post.slides:
            if slide.product:
                slide.product = find_product(b.brief, slide.product).name
    return plan


def phase_create(run: Run, services: Services, note: str | None) -> CreateResult:
    b = run.read("brief", BriefResult)
    analysis = run.read("analysis", BrandAnalysis)
    plan = run.read("plan", ContentPlan)
    (run.path / "images").mkdir(exist_ok=True)

    jobs = [(post, i, slide) for post in plan.posts for i, slide in enumerate(post.slides, start=1)]
    run.log(f"Generating {len(jobs)} slides")

    with ThreadPoolExecutor(max_workers=services.settings.image_workers) as pool:
        results = list(pool.map(
            lambda job: render_slide(run, services, b.brief, analysis, job[0], job[1], job[2], attempt=1, feedback=note or ""),
            jobs,
        ))

    posts = []
    for post in plan.posts:
        slides = [CreatedSlide(index=i, final_file=a.final_file, attempts=[a])
                  for (p, i, _), a in zip(jobs, results) if p.number == post.number]
        posts.append(CreatedPost(number=post.number, slides=slides))
    return CreateResult(posts=posts)


def phase_review(run: Run, services: Services, note: str | None) -> ReviewResult:
    b = run.read("brief", BriefResult)
    analysis = run.read("analysis", BrandAnalysis)
    plan = run.read("plan", ContentPlan)
    created = run.read("create", CreateResult)
    max_retries = services.settings.max_review_retries
    ai_plan = run.path / "03_plan.ai.json"
    ai_captions = ({p.number: p.caption for p in ContentPlan.model_validate_json(ai_plan.read_text()).posts}
                   if ai_plan.exists() else {})

    reviewed = []
    for post, made in zip(plan.posts, created.posts):
        rounds: list[PostReview] = []
        regenerated: set[int] = set()
        # The human decides: an edited caption is checked, but QA may only suggest changes to it
        human_caption = post.number in ai_captions and ai_captions[post.number].strip() != post.caption.strip()
        suggested = ""
        for round_no in range(max_retries + 1):
            run.log(f"QA post {post.number}, round {round_no + 1}")
            review = review_post(run, services, b.brief, analysis, post, made, human_caption)
            rounds.append(review)
            _record_scores(made, review)
            revised = review.revised_caption.strip()
            if human_caption:
                if revised and revised != post.caption.strip():
                    suggested = revised
            elif revised:
                post.caption = revised  # the next round checks the corrected caption

            to_fix = [r for r in review.slides if _failed(r) and r.scene_fix and 1 <= r.slide <= len(made.slides)]
            if not to_fix or round_no == max_retries:
                break
            for r in to_fix:
                slide_plan = post.slides[r.slide - 1]
                created_slide = made.slides[r.slide - 1]
                run.log(f"Regenerating post {post.number} slide {r.slide}: {r.scene_fix[:80]}")
                try:
                    attempt = render_slide(run, services, b.brief, analysis, post, r.slide, slide_plan,
                                           attempt=len(created_slide.attempts) + 1, feedback=r.scene_fix)
                except ImageBudgetExceeded as e:
                    run.log(str(e))
                    break
                created_slide.attempts.append(attempt)
                created_slide.final_file = attempt.final_file
                regenerated.add(r.slide)

        # Keep the best-scoring attempt of every slide, not just the latest one
        for slide in made.slides:
            scored = [a for a in slide.attempts if a.score is not None]
            if scored:
                slide.final_file = max(scored, key=lambda a: (a.score, a.attempt)).final_file

        last = rounds[-1]
        passed = all(not _failed(r) for r in last.slides)
        reviewed.append(ReviewedPost(number=post.number, rounds=rounds, regenerated_slides=sorted(regenerated),
                                     passed=passed, final_caption=post.caption,
                                     caption_edited_by_human=human_caption, suggested_caption=suggested))

    run.save("create", created)  # attempts + scores are part of the create history
    return ReviewResult(posts=reviewed)


def phase_deliver(run: Run, services: Services, note: str | None) -> DeliverResult:
    b = run.read("brief", BriefResult)
    plan = run.read("plan", ContentPlan)
    created = run.read("create", CreateResult)
    review = run.read("review", ReviewResult) if run.has("review") else None

    final = run.path / "final"
    shutil.rmtree(final, ignore_errors=True)
    final.mkdir()

    # Client-facing summary, in the language of the posts
    summary = [f"# {b.brief.brand} – tri Instagram objave\n", f"Instagram: {b.brief.instagram}\n",
               f"**Strategija:** {plan.strategy}\n"]
    posts_out = []
    for post, made in zip(plan.posts, created.posts):
        folder = final / f"post_{post.number}"
        folder.mkdir()
        files = []
        for slide in made.slides:
            dst = folder / f"slide_{slide.index}.png"
            shutil.copy2(run.path / slide.final_file, dst)
            files.append(run.rel(dst))

        reviewed = next((r for r in review.posts if r.number == post.number), None) if review else None
        caption = reviewed.final_caption if reviewed else post.caption
        full_caption = caption.strip() + "\n\n" + " ".join(post.hashtags)
        (folder / "caption.txt").write_text(full_caption + "\n")

        n = len(made.slides)
        fmt = f"karusel ({n} {'slajda' if 2 <= n <= 4 else 'slajdova'})" if post.format == "carousel" else "jedna slika"
        qa = "nije provedena"
        if reviewed:
            qa = "prošla" if reviewed.passed else "treba ljudski pregled (detalji u phases/05_review.json)"
            if reviewed.regenerated_slides:
                qa += f"; ponovno generirani slajdovi: {', '.join(map(str, reviewed.regenerated_slides))}"
            if reviewed.caption_edited_by_human:
                qa += "; opis je ručno uređen, provjera ga nije mijenjala"
        summary += [
            f"\n## Objava {post.number}: {post.title}\n",
            f"- **Format:** {fmt}, 1080×1350 px",
            f"- **Cilj:** {post.goal}",
            f"- **Koncept:** {post.concept}",
            f"- **Zašto odgovara brendu:** {post.rationale}",
            f"- **Provjera kvalitete:** {qa}",
            f"\n**Opis objave:**\n\n{full_caption}\n",
        ]
        posts_out.append({"number": post.number, "title": post.title, "format": post.format,
                          "files": files, "caption": full_caption})

    usage = run.state["usage"]
    summary.append(f"\n---\nTrošak ovog pokretanja: ${usage['cost_usd']:.2f} "
                   f"(Claude ${usage.get('claude_cost_usd', 0):.2f}: {usage['claude_input_tokens']:,} ulaznih i "
                   f"{usage['claude_output_tokens']:,} izlaznih tokena; Gemini ${usage.get('gemini_cost_usd', 0):.2f}: "
                   f"{usage['images']} generiranih slika)\n")
    (final / "README.md").write_text("\n".join(summary))

    zip_path = final / f"{run.id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in final.rglob("*"):
            if f.is_file() and f != zip_path:
                z.write(f, f"posts/{f.relative_to(final)}")
        for phase in PHASES[:-1]:
            if run.has(phase):
                z.write(run.phase_file(phase), f"phases/{run.phase_file(phase).name}")
        original_plan = run.path / "03_plan.ai.json"
        if original_plan.exists():  # the AI's plan before the human edit
            z.write(original_plan, f"phases/{original_plan.name}")

    run.log(f"Delivered to {final}")
    return DeliverResult(folder=run.rel(final), zip_file=run.rel(zip_path), posts=posts_out)


PHASE_FUNCTIONS = {
    "brief": phase_brief,
    "analysis": phase_analysis,
    "plan": phase_plan,
    "create": phase_create,
    "review": phase_review,
    "deliver": phase_deliver,
}


# ================================================================ helpers

_budget_lock = threading.Lock()
_in_flight: dict[str, int] = {}


def render_slide(run: Run, services: Services, brief: Brief, analysis: BrandAnalysis, post: PostPlan,
                 index: int, slide: Slide, attempt: int, feedback: str) -> SlideAttempt:
    inputs = run.path / "inputs"
    scene_prompt = scene_text(slide, analysis, feedback)

    # Reserve an image slot atomically: parallel workers must not overshoot MAX_IMAGES_PER_RUN
    with _budget_lock:
        images_so_far = run.state["usage"]["images"] + _in_flight.get(run.id, 0)
        if images_so_far >= services.settings.max_images_per_run:
            raise ImageBudgetExceeded(
                f"Image limit reached ({services.settings.max_images_per_run} per run) - stopping to protect your credit")
        # ...and never start an image the remaining Gemini credit cannot pay for
        price = PRICES["image"].get(services.settings.image_size, 0.05)
        ensure(services.settings, "gemini", price * (_in_flight.get(run.id, 0) + 1), "the next image")
        _in_flight[run.id] = _in_flight.get(run.id, 0) + 1
    try:
        png = services.gemini.generate(scene_prompt, images_so_far=images_so_far, on_usage=run.add_usage)
    finally:
        with _budget_lock:
            _in_flight[run.id] -= 1

    stem = f"post{post.number}_slide{index}_a{attempt}"
    scene_path = run.path / "images" / f"{stem}_scene.png"
    scene_path.write_bytes(png)

    product = find_product(brief, slide.product) if slide.product else None
    final = compose_slide(Image.open(io.BytesIO(png)), slide,
                          inputs / product.image if product else None, inputs / brief.logo)
    final_path = run.path / "images" / f"{stem}.png"
    final.save(final_path, optimize=True)
    run.log(f"Slide ready: {final_path.name}")

    return SlideAttempt(attempt=attempt, scene_prompt=scene_prompt, scene_file=run.rel(scene_path),
                        final_file=run.rel(final_path), feedback=feedback)


# Fields that change what the image model has to draw; everything else is composited by Pillow
SCENE_FIELDS = ("scene_prompt", "background")


def scenes_still_valid(old: ContentPlan, new: ContentPlan) -> bool:
    """True when an edited plan can reuse the generated scenes (only texts, layout, products or captions changed)."""
    if len(old.posts) != len(new.posts):
        return False
    for a, b in zip(old.posts, new.posts):
        if len(a.slides) != len(b.slides):
            return False
        for sa, sb in zip(a.slides, b.slides):
            if any(getattr(sa, f) != getattr(sb, f) for f in SCENE_FIELDS):
                return False
    return True


def recompose(run: Run) -> CreateResult:
    """Re-composite every slide from its saved AI scene with the current plan. No API calls, no cost.

    Used after a human edits headlines, product placement or captions, and after compositing fixes.
    Review and delivery have to run again, because the slides changed.
    """
    if run.state["phases"]["create"]["status"] != "done":
        raise RuntimeError("Slides can be re-composited only after the create phase")
    brief = run.read("brief", BriefResult).brief
    plan = run.read("plan", ContentPlan)
    created = run.read("create", CreateResult)
    inputs = run.path / "inputs"
    for post, made in zip(plan.posts, created.posts):
        for slide, made_slide in zip(post.slides, made.slides):
            product = find_product(brief, slide.product) if slide.product else None
            for attempt in made_slide.attempts:
                image = compose_slide(Image.open(run.path / attempt.scene_file), slide,
                                      inputs / product.image if product else None, inputs / brief.logo)
                image.save(run.path / attempt.final_file, optimize=True)
                attempt.score = None
    run.save("create", created)
    run.invalidate_from("review")
    run.log("Slides re-composited from saved scenes (no new images)")
    return created


def scene_text(slide: Slide, analysis: BrandAnalysis, feedback: str) -> str:
    style = analysis.photography_style if slide.background == "photo" else analysis.graphic_style
    colors = ", ".join(f"{c.name} {c.hex}" for c in analysis.colors[:6])
    fix = f"\nCorrections from the previous attempt (apply them): {feedback}" if feedback else ""
    return prompt("scene").format(scene_prompt=slide.scene_prompt, style=style, colors=colors,
                                  text_zone=slide.text_position, feedback=fix).strip()


def review_post(run: Run, services: Services, brief: Brief, analysis: BrandAnalysis,
                post: PostPlan, made: CreatedPost, human_caption: bool = False) -> PostReview:
    inputs = run.path / "inputs"
    facts = [f.claim for f in analysis.facts if f.verified] + [
        f"{p.name}: {p.style}, {p.abv}, {p.volume}" for p in analysis.products]
    content = [
        text_block(f"## Brand\n{analysis.summary}\nTone: {analysis.tone_of_voice}\n"
                   f"Colors: {', '.join(c.hex + ' ' + c.name for c in analysis.colors)}"),
        text_block("## Verified facts\n" + "\n".join(f"- {f}" for f in facts)),
        # The website text itself, so claims taken from it are not flagged as invented
        text_block("## Official website text (also a verified source)\n" + "\n\n".join(
            f"### {s.url}\n{s.text[:2500]}" for s in run.read("brief", BriefResult).sources if s.ok)),
        text_block(f"## Planned post {post.number}\n" + post.model_dump_json(indent=2, exclude={"slides"})),
    ]
    if human_caption:
        content.append(text_block(
            "Note: the caption was edited by a human editor on purpose. Check it as usual and explain every "
            "concern in `caption_issues`, but keep the editor's wording; `revised_caption` is only a suggestion."))
    used = {s.product for s in post.slides if s.product}
    for name in used:
        content += [text_block(f"Reference product photo: {name}"), image_block(inputs / find_product(brief, name).image)]
    content += [text_block("Reference logo:"), image_block(inputs / brief.logo)]
    for slide in made.slides:
        content += [text_block(f"Finished slide {slide.index} of {len(made.slides)}:"),
                    image_block(run.path / slide.final_file, max_side=1350)]

    ensure(services.settings, "claude", MIN_CLAUDE_CALL, f"the QA of post {post.number}")
    return services.claude.structured(system=prompt("review"), content=content, schema=PostReview,
                                      effort="medium", on_usage=run.add_usage)


def _failed(r) -> bool:
    return r.score < PASS_SCORE or not r.product_accurate or not r.looks_natural


def _record_scores(made: CreatedPost, review: PostReview) -> None:
    for r in review.slides:
        if 1 <= r.slide <= len(made.slides):
            slide = made.slides[r.slide - 1]
            current = next(a for a in slide.attempts if a.final_file == slide.final_file)
            current.score = r.score


def find_product(brief: Brief, name: str):
    wanted = name.lower().strip()
    for p in brief.products:
        if p.name.lower() == wanted:
            return p
    for p in brief.products:
        if wanted in p.name.lower() or p.name.lower() in wanted:
            return p
    raise ValueError(f"Unknown product '{name}'. Known: {[p.name for p in brief.products]}")


# ================================================================ runner

def run_phase(run: Run, phase: str, services: Services, note: str | None = None) -> None:
    if phase not in PHASE_FUNCTIONS:
        raise ValueError(f"Unknown phase '{phase}'. Phases: {PHASES}")
    previous = PHASES[:PHASES.index(phase)]
    not_done = [p for p in previous if run.state["phases"][p]["status"] != "done"]
    if not_done:
        raise RuntimeError(f"Run these phases first: {not_done}")

    # Do not start a phase the remaining credit cannot pay for
    images = sum(len(p.slides) for p in run.read("plan", ContentPlan).posts) if phase == "create" else 0
    check_phase(services.settings, phase, images)

    if note:
        run.update(lambda s: s["notes"].__setitem__(phase, note))
    run.invalidate_from(phase)
    run.set_phase(phase, "running")
    try:
        result = PHASE_FUNCTIONS[phase](run, services, note)
        run.save(phase, result)
        run.set_phase(phase, "done")
    except Exception as e:
        run.set_phase(phase, "failed", error=f"{type(e).__name__}: {e}")
        run.log(f"Phase '{phase}' failed: {e}")
        raise


def run_pipeline(run: Run, services: Services, from_phase: str | None = None,
                 stop_after: str | None = None, note: str | None = None) -> None:
    start = from_phase or run.next_phase()
    if start is None:
        run.log("All phases are already done")
        return
    for phase in PHASES[PHASES.index(start):]:
        run_phase(run, phase, services, note if phase == start else None)
        if phase == stop_after:
            run.log(f"Stopped after '{phase}' - review the output, then resume")
            break
