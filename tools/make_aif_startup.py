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

The background is the logo's own navy, sampled from its corner rather than
typed in, which is also the gauge screen's COL_BG: the startup screen hands
over to the gauges without the panel changing colour underneath.

Fonts: Avenir Next where macOS has it, the closest thing to the panel's
Montserrat on this Mac, and Pillow's built-in face elsewhere -- legible, if
plainer, on a Linux runner that will never see the panel anyway.
"""
import argparse
import os
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
    mark = logo.crop(MARK_BOX).resize((MARK, MARK), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), navy)
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
