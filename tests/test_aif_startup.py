"""tools/make_aif_startup.py: the AI Foundry startup screen builds, at the
panel's size, on the gauge screen's own background."""
import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        "make_aif_startup", ROOT / "tools" / "make_aif_startup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_it_builds_a_panel_sized_picture(tmp_path):
    out = tmp_path / "s.png"
    assert _tool().main(["--out", str(out)]) == 0
    from PIL import Image
    assert Image.open(out).size == (320, 240)


def test_its_background_is_the_gauge_screens():
    """The startup screen hands over to the gauges; the panel must not
    change colour underneath it."""
    img = _tool().build()
    corner = "%02X%02X%02X" % img.getpixel((0, 0))
    src = (ROOT / "firmware" / "src" / "usage_view.c").read_text()
    bg = re.search(r"#define COL_BG\s+lv_color_hex\(0x([0-9A-Fa-f]{6})\)",
                   src).group(1).upper()
    assert corner == bg
