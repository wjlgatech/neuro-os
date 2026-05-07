"""
Generate the founder_loop browser extension icons.

The icon: a circular ring (the "tank") with a half-fill, on a dark
square background. Run once to produce the four PNG sizes.

Usage::

    python ui/browser_extension/icons/generate.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
SIZES = [16, 32, 48, 128]
BG = (13, 17, 23, 255)        # neuro-os background
RING = (139, 148, 158, 255)   # neutral ring
FILL = (86, 211, 100, 255)    # green: tank


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img)

    pad = max(1, size // 8)
    box = [pad, pad, size - pad, size - pad]
    stroke = max(1, size // 16)

    # Background ring
    d.ellipse(box, outline=RING, width=stroke)

    # Half-tank fill: bottom hemisphere green.
    mid = size // 2
    half_box = [pad + stroke, mid, size - pad - stroke, size - pad - stroke]
    d.pieslice(half_box, start=0, end=180, fill=FILL)

    return img


def main() -> None:
    for s in SIZES:
        out = HERE / f"{s}.png"
        render(s).save(out, "PNG")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
