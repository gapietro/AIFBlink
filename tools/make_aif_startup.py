#!/usr/bin/env python3
"""Build the AI Foundry startup screen: the AIF mark over its own navy, with
"AI Foundry" and "BLINK" under it, as a 320x240 PNG for the logo partition.

    tools/make_aif_startup.py [--out dist/aif-startup.png]
    tools/burn.sh --edition claude --logo dist/aif-startup.png

This fork's units belong to the AI Foundry team (2026-10-14), and the logo
partition is how a unit says whose it is (docs/README-full.md, "Company
units"). The picture is BUILT here rather than drawn by hand so the exact
screen can be regenerated from the logo in docs/img/brand/aif/ -- and so a
change of wording is a one-line edit, not a trip to an image editor.

The background is the gauge screen's COL_BG, read out of
firmware/src/usage_view.c rather than typed in again, so the startup screen
hands over to the gauges without the panel changing colour underneath. That
is darker than the logo's own navy -- the cheap panel washed the logo navy
out (2026-10-14) -- so the logo's navy is recoloured to it, including the
anvil, which is the same navy showing through.

Fonts: Avenir Next where macOS has it, the closest thing to the panel's
Montserrat on this Mac, and Pillow's built-in face elsewhere -- legible, if
plainer, on a Linux runner that will never see the panel anyway.
"""
import argparse
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = os.path.join(ROOT, "docs", "img", "brand", "aif", "aif-logo.png")
W, H = 320, 240
GREEN = (0x6A, 0xC2, 0x51)      # the logo's green; usage_view.c's COL_BRAND
WHITE = (0xFF, 0xFF, 0xFF)
MARK = 150                      # px, square, leaving room for two lines
# The mark's own box inside the 1024 px logo, measured off the artwork: the
# rest is navy margin, which the canvas supplies at the panel's size.
MARK_BOX = (150, 140, 880, 880)
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"
USAGE_VIEW = os.path.join(ROOT, "firmware", "src", "usage_view.c")
# How far from the logo's navy a pixel may be and still be moved with it, in
# RGB distance. The anti-aliased rim between navy and green is a blend of the
# two, so it moves part of the way -- in proportion to how navy it is --
# rather than being left as a halo of the old colour round the mark.
NAVY_REACH = 120.0


def panel_bg():
    """COL_BG from usage_view.c, as an (r, g, b) tuple.

    The NORMAL palette's: the first value of THEMED(normal, high), or the
    only value of a plain lv_color_hex(). The high-contrast palette's ground
    is near-black, and a board in that mode shows this screen's navy for its
    three seconds before the gauges -- one picture cannot match both, and the
    logo partition holds one picture.
    """
    with open(USAGE_VIEW, encoding="utf-8") as f:
        m = re.search(r"#define COL_BG\s+(?:THEMED|lv_color_hex)"
                      r"\(0x([0-9A-Fa-f]{6})", f.read())
    v = int(m.group(1), 16)
    return (v >> 16 & 0xFF, v >> 8 & 0xFF, v & 0xFF)


def recolour(img, frm, to):
    """Move every pixel near `frm` towards `to`, by how near it is."""
    shift = [t - f for f, t in zip(frm, to)]
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            d = ((r - frm[0]) ** 2 + (g - frm[1]) ** 2 + (b - frm[2]) ** 2) ** .5
            w = max(0.0, 1.0 - d / NAVY_REACH)
            if w:
                px[x, y] = (round(r + shift[0] * w), round(g + shift[1] * w),
                            round(b + shift[2] * w), a)
    return img


def font(size, demi):
    try:
        return ImageFont.truetype(AVENIR, size, index=2 if demi else 0)
    except OSError:
        return ImageFont.load_default(size=size)


def centred(draw, y, text, face, fill, spacing=0):
    widths = [draw.textlength(c, font=face) for c in text]
    x = (W - sum(widths) - spacing * (len(text) - 1)) / 2
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=face, fill=fill)
        x += w + spacing


def build(logo_path=LOGO):
    logo = Image.open(logo_path).convert("RGBA")
    navy = logo.getpixel((0, 0))[:3]
    bg = panel_bg()
    mark = logo.crop(MARK_BOX).resize((MARK, MARK), Image.LANCZOS)
    mark = recolour(mark, navy, bg)
    canvas = Image.new("RGB", (W, H), bg)
    canvas.paste(mark, ((W - MARK) // 2, 14), mark)
    d = ImageDraw.Draw(canvas)
    centred(d, 170, "AI Foundry", font(22, True), WHITE)
    centred(d, 202, "BLINK", font(15, False), GREEN, spacing=4)
    return canvas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(ROOT, "dist",
                                                  "aif-startup.png"))
    args = ap.parse_args(argv)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    build().save(args.out)
    print(f"wrote {args.out} ({W}x{H})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
