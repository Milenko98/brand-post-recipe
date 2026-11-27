"""Data passed between phases.

The same Pydantic models are used three ways:
  * as the structured-output schema Claude must fill (client.beta.messages.parse),
  * as the JSON files saved after every phase (runs/<id>/NN_phase.json),
  * as FastAPI request/response bodies.
Field descriptions are sent to the model, so they double as instructions.
"""

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- 1. brief

class Product(BaseModel):
    name: str
    image: str = Field(description="Path to a cut-out product photo (transparent background), relative to the brief")
    notes: str = ""


class Brief(BaseModel):
    """Answers to the briefing questions plus paths to reference files."""

    brand: str
    instagram: str
    website: str
    extra_urls: list[str] = Field(default_factory=list, description="Webshop / product pages to read for facts")
    products: list[Product]
    audience: str
    goals: list[str]
    inspiration: str = ""
    constraints: list[str] = Field(default_factory=list)
    language: str = "hr"
    logo: str
    post_screenshots: list[str] = Field(default_factory=list)
    captions_file: str | None = None


class Source(BaseModel):
    url: str
    ok: bool
    title: str = ""
    text: str = ""
    error: str = ""


class BriefResult(BaseModel):
    """Output of the brief phase: the brief with absolute asset paths + fetched web sources."""

    brief: Brief
    captions: str = ""
    sources: list[Source]


# ---------------------------------------------------------------- 2. analysis

class ColorSwatch(BaseModel):
    hex: str = Field(description="#RRGGBB")
    name: str
    usage: str = Field(description="Where the brand uses this color, e.g. 'label accent of Pale Ale', 'event poster backgrounds'")


class Evidence(BaseModel):
    observation: str
    reference: str = Field(description="Screenshot file name, URL, or 'caption N' the observation is based on")


class Fact(BaseModel):
    claim: str
    source: str = Field(description="URL or product label the claim comes from")
    verified: bool = Field(description="True only if read directly on the official website or product label")


class ProductProfile(BaseModel):
    name: str
    style: str
    abv: str = Field(description="e.g. '5,3%' or 'unknown'")
    volume: str = Field(description="e.g. '0,33 L bottle' or 'unknown'")
    label_colors: list[str] = Field(description="Hex colors on the label/can")
    description: str = Field(description="Flavor and character, only from official sources; say so if unknown")
    source: str


class BrandAnalysis(BaseModel):
    summary: str = Field(description="3-5 sentences: who the brand is and how it presents itself")
    audience: str
    tone_of_voice: str
    tone_examples: list[str] = Field(description="Short verbatim quotes from captions that show the tone")
    language_rules: list[str] = Field(description="Concrete do/don't writing rules (emoji use, slang, humor, length, CTAs)")
    content_themes: list[str]
    colors: list[ColorSwatch]
    typography: str
    photography_style: str = Field(description="Lighting, locations, framing, color grading of photos")
    graphic_style: str = Field(description="Illustrations, flat color posters, layouts, recurring motifs (e.g. the dragon)")
    product_presentation: str
    people_presentation: str
    products: list[ProductProfile]
    facts: list[Fact]
    assumptions: list[str] = Field(description="Conclusions NOT backed by a source; clearly labeled as assumptions")
    unavailable_sources: list[str] = Field(description="Sources that could not be read and what that means for the analysis")
    evidence: list[Evidence]


# ---------------------------------------------------------------- 3. plan

class Slide(BaseModel):
    purpose: str = Field(description="What this slide does in the post (hook, product, detail, CTA ...)")
    background: Literal["photo", "graphic"] = Field(
        description="'photo' = photorealistic scene, 'graphic' = flat brand-colored poster background like the brand's event posts"
    )
    scene_prompt: str = Field(
        description=(
            "English prompt for the image model describing ONLY the background scene. "
            "No text, no logos, no beer cans/bottles (the real product is composited later). "
            "Must describe the empty surface/area where the product will be placed."
        )
    )
    product: str | None = Field(description="Exact product name from the analysis to composite on this slide, or null")
    product_position: Literal["left", "center", "right"] = "center"
    product_scale: float = Field(description="Product height as a fraction of image height, 0.35-0.75")
    headline: str = Field(description="Short overlay text in Croatian, max ~6 words; empty string for no text")
    subline: str = Field(description="Optional smaller overlay line in Croatian (e.g. ABV/IBU), or empty string")
    text_position: Literal["top", "bottom"] = "top"
    text_color: str = Field(description="#RRGGBB for the headline, chosen for contrast")
    accent_color: str = Field(description="#RRGGBB from the brand palette, used for the text band")


class PostPlan(BaseModel):
    number: int
    title: str
    goal: str = Field(description="e.g. education, engagement (comments/saves), product launch, purchase intent")
    format: Literal["single_image", "carousel"]
    concept: str
    rationale: str = Field(description="Why this approach fits the brand and its audience, referencing the analysis")
    slides: list[Slide] = Field(description="1 slide for single_image, 3-5 for carousel")
    caption: str = Field(description="Final Instagram caption in Croatian, in the brand's tone; only verified facts")
    hashtags: list[str]


class ContentPlan(BaseModel):
    strategy: str = Field(description="2-3 sentences on how the three posts work together")
    posts: list[PostPlan] = Field(description="Exactly three posts")


# ---------------------------------------------------------------- 4. create

class SlideAttempt(BaseModel):
    attempt: int
    scene_prompt: str
    scene_file: str
    final_file: str
    feedback: str = Field(default="", description="QA feedback that led to this attempt")
    score: int | None = Field(default=None, description="QA score, filled in by the review phase")


class CreatedSlide(BaseModel):
    index: int
    final_file: str
    attempts: list[SlideAttempt]


class CreatedPost(BaseModel):
    number: int
    slides: list[CreatedSlide]


class CreateResult(BaseModel):
    posts: list[CreatedPost]


# ---------------------------------------------------------------- 5. review

class SlideReview(BaseModel):
    slide: int = Field(description="1-based slide index")
    score: int = Field(description="Overall quality 1-10")
    product_accurate: bool = Field(description="Product, label and logo match the reference exactly, nothing distorted")
    brand_consistent: bool
    looks_natural: bool = Field(description="Product sits believably in the scene (perspective, light, shadow, scale)")
    text_legible: bool
    issues: list[str]
    scene_fix: str = Field(description="If the slide should be regenerated: concrete changes to the scene prompt. Else empty.")


class PostReview(BaseModel):
    slides: list[SlideReview]
    caption_issues: list[str] = Field(description="Invented facts, prices, claims about real people, tone mismatches")
    revised_caption: str = Field(description="Corrected caption (or the original if it is fine)")


class ReviewedPost(BaseModel):
    number: int
    rounds: list[PostReview]
    regenerated_slides: list[int]
    passed: bool
    final_caption: str
    # A caption edited by a human is never rewritten by QA; its correction is only suggested
    caption_edited_by_human: bool = False
    suggested_caption: str = ""


class ReviewResult(BaseModel):
    posts: list[ReviewedPost]
