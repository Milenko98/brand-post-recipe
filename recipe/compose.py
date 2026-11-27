"""Pillow compositing: AI background + real product photo + real logo + headline.

Generated images can distort labels and logos, so those are never generated:
the original files from the brief are placed on top of the AI scene here.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, ImageStat

from .config import POST_SIZE
from .schemas import Slide

FONTS = Path(__file__).parent / "fonts"
HEADLINE_FONT = FONTS / "Anton-Regular.ttf"
BODY_FONT = FONTS / "Inter.ttf"

MARGIN = 0.06  # of image width


def compose_slide(scene: Image.Image, slide: Slide, product_image: Path | None, logo: Path) -> Image.Image:
    canvas = ImageOps.fit(scene.convert("RGB"), POST_SIZE, Image.Resampling.LANCZOS).convert("RGBA")

    has_product = product_image is not None
    if has_product and slide.product_position == "center" and slide.text_position == "bottom":
        # The product stands at the bottom; centered text there would cover it
        slide = slide.model_copy(update={"text_position": "top"})

    text_box = _text_layout(canvas, slide, has_product)

    if has_product:
        text_bottom = text_box[1] if slide.text_position == "top" and (slide.headline or slide.subline) else 0
        _place_product(canvas, Image.open(product_image), slide, text_bottom)

    _place_logo(canvas, Image.open(logo), slide)

    if slide.headline or slide.subline:
        _draw_text(canvas, slide, text_box)

    return canvas.convert("RGB")


# ---------------------------------------------------------------- product

def _place_product(canvas: Image.Image, product: Image.Image, slide: Slide, text_bottom: int = 0) -> None:
    W, H = canvas.size
    product = _clean_product(product)

    bottom = H * 0.93  # always stands on the surface at the bottom of the scene
    scale = min(max(slide.product_scale, 0.3), 0.8)
    height = int(H * scale)
    if text_bottom:
        # Never let the headline cover the product: shrink it to fit under the text
        height = max(min(height, int(bottom - text_bottom - H * 0.03)), int(H * 0.25))
    width = int(product.width * height / product.height)
    product = product.resize((width, height), Image.Resampling.LANCZOS)

    # Match the product's brightness a little to the scene, so it doesn't look pasted on
    scene_luma = ImageStat.Stat(canvas.convert("L")).mean[0] / 255
    product = _adjust_brightness(product, 0.9 + 0.2 * scene_luma)

    center_x = {"left": 0.3, "center": 0.5, "right": 0.7}[slide.product_position] * W
    x = int(center_x - width / 2)
    y = int(bottom - height)

    # Contact shadow (ellipse under the base) + soft drop shadow from the product's silhouette
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    ew, eh = width * 1.1, max(height * 0.05, 12)
    draw.ellipse([center_x - ew / 2, bottom - eh / 2, center_x + ew / 2, bottom + eh / 2], fill=(0, 0, 0, 150))
    silhouette = Image.new("RGBA", product.size, (0, 0, 0, 90))
    silhouette.putalpha(product.getchannel("A").point(lambda a: a * 90 // 255))
    shadow.alpha_composite(silhouette, (x + int(width * 0.06), y + int(height * 0.02)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(W * 0.012, 6)))

    canvas.alpha_composite(shadow)
    canvas.alpha_composite(product, (x, y))


def _clean_product(product: Image.Image) -> Image.Image:
    """Trim transparent padding and turn the packshot's baked-in floor shadow into a transparent one.

    Shop packshots are photographed on white with a soft grey shadow under the base. Pasted on a
    scene, that shows as a white oval. Light pixels around the base become black with alpha
    proportional to their darkness, so the scene shows through.
    """
    product = product.convert("RGBA")
    product = product.crop(product.getbbox())
    pixels = product.load()
    w, h = product.size
    top = int(h * 0.9)

    def to_shadow(x: int, y: int) -> None:
        r, g, b, a = pixels[x, y]
        pixels[x, y] = (0, 0, 0, min(a, (255 - (r + g + b) // 3) * 2 // 3))

    def row_mean(y: int) -> float:
        values = [sum(pixels[x, y][:3]) / 3 for x in range(w) if pixels[x, y][3] > 128]
        return sum(values) / len(values) if values else 255

    # The darkest row near the bottom is where the product meets the floor
    contact = min(range(top, h), key=row_mean)

    # Below it there is only floor and shadow
    for y in range(contact + 1, h):
        for x in range(w):
            if pixels[x, y][3] and min(pixels[x, y][:3]) > 120:
                to_shadow(x, y)

    # Beside the base, clear light floor pixels reachable from the transparent background
    stack = [(x, y) for y in range(top, contact + 1) for x in (0, w - 1)]
    seen = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < w and top <= y <= contact):
            continue
        seen.add((x, y))
        r, g, b, a = pixels[x, y]
        if a < 20 or min(r, g, b) > 200:
            if a >= 20:
                to_shadow(x, y)
            stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return product


def _adjust_brightness(img: Image.Image, factor: float) -> Image.Image:
    alpha = img.getchannel("A")
    rgb = ImageEnhance.Brightness(img.convert("RGB")).enhance(factor)
    rgb.putalpha(alpha)
    return rgb


# ---------------------------------------------------------------- logo

def _place_logo(canvas: Image.Image, logo: Image.Image, slide: Slide) -> None:
    W, H = canvas.size
    logo = logo.convert("RGBA")
    logo = logo.crop(logo.getbbox())
    width = int(W * 0.2)
    logo = logo.resize((width, int(logo.height * width / logo.width)), Image.Resampling.LANCZOS)

    margin = int(W * MARGIN)
    x = margin if slide.product_position != "left" else W - margin - logo.width
    y = margin if slide.text_position == "bottom" else H - margin - logo.height

    # The logo is black; switch to a white version on dark backgrounds
    area = canvas.crop((x, y, x + logo.width, y + logo.height)).convert("L")
    if ImageStat.Stat(area).mean[0] < 110:
        white = Image.new("RGBA", logo.size, (255, 255, 255, 255))
        white.putalpha(logo.getchannel("A"))
        logo = white

    canvas.alpha_composite(logo, (x, y))


# ---------------------------------------------------------------- text

def _font(path: Path, size: int, variation: str | None = None) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(path), size)
    if variation:
        try:
            font.set_variation_by_name(variation)
        except (OSError, ValueError):
            pass
    return font


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    # Move a dangling short word ("I", "U", "DA") to the start of the next line when it still fits
    for i in range(len(lines) - 1):
        head, _, last = lines[i].rpartition(" ")
        if head and len(last) <= 2 and last.isalpha():
            candidate = f"{last} {lines[i + 1]}"
            if draw.textlength(candidate, font=font) <= max_width:
                lines[i], lines[i + 1] = head, candidate
    return lines


def _clean_text(text: str) -> str:
    """Typography for the poster fonts: no emoji (the fonts have no glyphs for them), proper dashes."""
    kept = "".join(c for c in text if ord(c) < 0x2190 or c in "–—„“”‘’…·→")
    return " ".join(kept.replace(" - ", " – ").split())


def _text_layout(canvas: Image.Image, slide: Slide, has_product: bool):
    """Fit the headline (max 3 lines, largest size) and the subline (shrinks, then wraps to 2 lines).

    Returns (top, bottom, lines, font, sub_lines, sub_font, x).
    """
    W, H = canvas.size
    draw = ImageDraw.Draw(canvas)
    x = int(W * MARGIN)
    max_width = int(W * (1 - 2 * MARGIN) - W * 0.04)

    # Next to a product standing on one side, text uses only the other side of the frame
    beside_product = has_product and slide.text_position == "bottom" and slide.product_position != "center"
    if beside_product:
        max_width = int(W * 0.5)
        if slide.product_position == "left":
            x = int(W * (1 - MARGIN)) - max_width - int(W * 0.04)

    headline = _clean_text(slide.headline).upper()
    lines, font = [], None
    for size in range(130, 54, -6):
        font = _font(HEADLINE_FONT, size)
        lines = _wrap(draw, headline, font, max_width) if headline else []
        if len(lines) <= (4 if beside_product else 3) and all(draw.textlength(l, font=font) <= max_width for l in lines):
            break

    # The subline band has padding on both sides
    subline = _clean_text(slide.subline)
    pad = int(font.size * 0.18)
    sub_lines, sub_font = [], None
    for size in range(38, 27, -2):
        sub_font = _font(BODY_FONT, size, "Bold")
        sub_lines = [subline] if subline else []
        if draw.textlength(subline, font=sub_font) <= max_width - 2 * pad:
            break
    else:
        sub_lines = _wrap(draw, subline, sub_font, max_width - 2 * pad)

    line_h = int(font.size * 1.18)
    block_h = len(lines) * (line_h + pad) + len(sub_lines) * int(sub_font.size * 1.5) + (pad if sub_lines else 0)

    top = int(H * MARGIN) if slide.text_position == "top" else int(H * (1 - MARGIN)) - block_h
    return top, top + block_h, lines, font, sub_lines, sub_font, x


def _draw_text(canvas: Image.Image, slide: Slide, layout) -> None:
    top, _, lines, font, sub_lines, sub_font, x = layout
    draw = ImageDraw.Draw(canvas)
    line_h = int(font.size * 1.18)
    pad = int(font.size * 0.18)

    # Brand-poster style: each line on its own solid accent-colored band
    y = top
    for line in lines:
        width = draw.textlength(line, font=font)
        draw.rectangle([x, y, x + width + 2 * pad, y + line_h], fill=slide.accent_color)
        draw.text((x + pad, y + line_h / 2), line, font=font, fill=slide.text_color, anchor="lm")
        y += line_h + pad

    box_h = int(sub_font.size * 1.5)
    for line in sub_lines:
        sub_w = draw.textlength(line, font=sub_font)
        draw.rectangle([x, y, x + sub_w + 2 * pad, y + box_h], fill=(20, 20, 20, 230))
        draw.text((x + pad, y + box_h / 2), line, font=sub_font, fill="#FFFFFF", anchor="lm")
        y += box_h
