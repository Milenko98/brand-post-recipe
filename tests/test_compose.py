from PIL import Image

from recipe.compose import compose_slide
from tests.conftest import ROOT
from tests.fakes import slide

INPUTS = ROOT / "inputs" / "zmajska"
PRODUCT = INPUTS / "products" / "pale_ale.png"
LOGO = INPUTS / "logo.png"


def scene(color=(30, 30, 30)):
    return Image.new("RGB", (928, 1152), color)


def test_output_is_instagram_portrait_size():
    assert compose_slide(scene(), slide(), PRODUCT, LOGO).size == (1080, 1350)


def test_product_is_composited_at_the_bottom():
    out = compose_slide(scene((0, 0, 255)), slide(headline="", subline=""), PRODUCT, LOGO)
    assert out.getpixel((540, 1100)) != (0, 0, 255)   # product covers the bottom center
    assert out.getpixel((540, 200)) == (0, 0, 255)    # nothing in the empty top area


def test_logo_turns_white_on_dark_background():
    out = compose_slide(scene((10, 10, 10)), slide(headline="", subline="", text_position="top"), PRODUCT, LOGO)
    logo_area = out.crop((60, 1150, 280, 1290))
    assert max(p[0] for p in logo_area.get_flattened_data()) > 200


def test_long_headline_with_croatian_letters_fits():
    long = "Čašica šljivovice? Ne, đir po žutom zmajskom pivu za sve"
    out = compose_slide(scene(), slide(headline=long), PRODUCT, LOGO)
    assert out.size == (1080, 1350)


def test_slide_without_product():
    out = compose_slide(scene((200, 100, 30)), slide(product=None), None, LOGO)
    assert out.getpixel((540, 1100)) == (200, 100, 30)


def test_packshot_floor_shadow_becomes_transparent():
    from recipe.compose import _clean_product

    product = Image.new("RGBA", (100, 300), (0, 0, 0, 0))
    product.paste((30, 20, 10, 255), (20, 0, 80, 285))  # dark bottle body
    product.paste((240, 240, 240, 255), (5, 285, 95, 300))  # white floor with light shadow under it
    cleaned = _clean_product(product)

    r, g, b, a = cleaned.getpixel((50, 295))
    assert a < 30 and (r, g, b) == (0, 0, 0)  # floor became a faint transparent shadow
    assert cleaned.getpixel((50, 100)) == (30, 20, 10, 255)  # the product itself is untouched


def test_headline_never_covers_the_product():
    from PIL import ImageDraw
    from recipe.compose import _text_layout

    color = (42, 166, 207)
    s = slide(product="Pils", product_position="center", text_position="top", product_scale=0.8,
              headline="Neiskusni - pozor! Ovo je jako dugacak naslov", subline="IBU 70")
    img = compose_slide(Image.new("RGB", (1080, 1350), color), s, INPUTS / "products" / "pils.png", INPUTS / "logo.png")
    text_bottom = _text_layout(Image.new("RGBA", (1080, 1350)), s, True)[1]
    # The bottle is shrunk, so the strip right under the text is still the plain scene
    assert all(img.getpixel((540, y)) == color for y in range(text_bottom + 2, text_bottom + 20))
