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
