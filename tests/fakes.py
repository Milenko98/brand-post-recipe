"""Fake Claude / Gemini / website so the whole pipeline runs in tests without API keys or cost."""

import io

from PIL import Image

from recipe.schemas import (BrandAnalysis, ColorSwatch, ContentPlan, Evidence, Fact, PostPlan, PostReview,
                            ProductProfile, Slide, SlideReview, Source)


class FakeClaude:
    def __init__(self, reviews: list[PostReview] | None = None):
        self.calls: list[dict] = []
        self.reviews = list(reviews or [])
        self.caption_fix = ""  # revised_caption returned by passing reviews

    def structured(self, *, system, content, schema, effort="high", on_usage=None):
        self.calls.append({"schema": schema.__name__, "content": content, "effort": effort})
        if on_usage:
            on_usage(claude_input_tokens=1000, claude_output_tokens=200, claude_cache_read_tokens=0,
                     claude_cost_usd=0.008, cost_usd=0.008)
        if schema is BrandAnalysis:
            return analysis()
        if schema is ContentPlan:
            return plan()
        if schema is PostReview:
            return self.reviews.pop(0) if self.reviews else passing_review(content, self.caption_fix)
        raise AssertionError(f"Unexpected schema {schema}")


class FakeGemini:
    def __init__(self):
        self.prompts: list[str] = []

    def generate(self, prompt, *, references=(), aspect_ratio="4:5", images_so_far=0, on_usage=None):
        self.prompts.append(prompt)
        if on_usage:
            on_usage(images=1, gemini_cost_usd=0.05, cost_usd=0.05)
        buf = io.BytesIO()
        Image.new("RGB", (928, 1152), (60, 40, 30)).save(buf, "PNG")
        return buf.getvalue()


class FakeWeb:
    def read_site(self, website, extra_urls):
        return [Source(url=website, ok=True, title="Home", text="Prva hrvatska craft pivovara."),
                Source(url="https://example.com/broken", ok=False, error="404")]


def analysis() -> BrandAnalysis:
    return BrandAnalysis(
        summary="Craft brewery.", audience="Adults 25-45", tone_of_voice="Playful",
        tone_examples=["Izlegla se sveta patka!"], language_rules=["Use wordplay"], content_themes=["new beers"],
        colors=[ColorSwatch(hex="#E8641B", name="Pale Ale orange", usage="label")],
        typography="Condensed bold", photography_style="Moody pub photos", graphic_style="Flat posters",
        product_presentation="Hero shots", people_presentation="Brewers",
        products=[ProductProfile(name="Pale Ale", style="APA", abv="5,3%", volume="0,33 L", label_colors=["#E8641B"],
                                 description="Citrus", source="label")],
        facts=[Fact(claim="Pale Ale has 5,3% ABV", source="label", verified=True)],
        assumptions=["Audience is mostly urban"], unavailable_sources=[],
        evidence=[Evidence(observation="Orange posters", reference="post_01.jpg")],
    )


def slide(product: str | None = "Pale Ale", **kw) -> Slide:
    data = dict(purpose="hero", background="photo", scene_prompt="Wooden bar counter, empty in the foreground",
                product=product, product_position="center", product_scale=0.55, headline="Zmaj je budan",
                subline="5,3%", text_position="top", text_color="#FFFFFF", accent_color="#E8641B")
    data.update(kw)
    return Slide(**data)


def plan() -> ContentPlan:
    posts = [
        PostPlan(number=1, title="Launch", goal="purchase intent", format="single_image", concept="Hero shot",
                 rationale="Fits", slides=[slide("pale ale")], caption="Novo!", hashtags=["#craft"]),
        PostPlan(number=2, title="Quiz", goal="engagement", format="carousel", concept="Guess the hops",
                 rationale="Fits", slides=[slide(), slide(None, background="graphic"), slide(product_position="right")],
                 caption="Pogodi!", hashtags=["#pivo"]),
        PostPlan(number=3, title="Education", goal="education", format="single_image", concept="What is APA",
                 rationale="Fits", slides=[slide(text_position="bottom", product_position="left")],
                 caption="Što je APA?", hashtags=["#apa"]),
    ]
    return ContentPlan(strategy="Launch, engage, educate", posts=posts)


def passing_review(content, caption: str = "") -> PostReview:
    count = sum(1 for b in content if b.get("type") == "text" and b["text"].startswith("Finished slide"))
    return PostReview(slides=[review(i) for i in range(1, count + 1)], caption_issues=[], revised_caption=caption)


def review(index: int, ok: bool = True, fix: str = "") -> SlideReview:
    return SlideReview(slide=index, score=9 if ok else 4, product_accurate=True, brand_consistent=True,
                       looks_natural=ok, text_legible=True, issues=[] if ok else ["Product floats"], scene_fix=fix)
