"""
Record an annotated self-repair GIF.

Drives the Self-Repair tab through 5 state transitions, captures a
clipped screenshot at each, overlays a brief caption via PIL, and
stitches the result into ``ui/assets/self_repair.gif`` with imageio.

Captions follow the user's mental model:
  Frame 1: "Canonical state"           (7 priority rules · all blue)
  Frame 2: "Click 'Break it'"          (4 RL rules dashed)
  Frame 3: "flywheel observed regression"
  Frame 4: "Patch promoted"            (visual hold)
  Frame 5: "Provenance recorded"       (validator panel)
  Frame 6: "Restored canonical"

Usage:
    streamlit run ui/app.py --server.port 8765 --server.headless true &
    python3 ui/scripts/record_gif.py
"""
import asyncio
import json
from pathlib import Path
from typing import List, Tuple

import imageio.v2 as imageio
from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import async_playwright


REPO = Path(__file__).resolve().parent.parent.parent
OUT = REPO / "ui" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
FRAMES_DIR = Path("/tmp/gif_frames")
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

CLIP = {"x": 40, "y": 320, "width": 1200, "height": 1000}
CAPTION_HEIGHT = 90
CAPTION_BG = (17, 24, 39)        # slate 900
CAPTION_FG = (255, 255, 255)
ACCENT_GREEN = (16, 163, 74)     # emerald 600


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def annotate(src: Path, dst: Path, title: str, sub: str = "") -> None:
    """Add a caption bar above a screenshot, write to ``dst``."""
    img = Image.open(src).convert("RGB")
    w = img.width
    canvas = Image.new("RGB", (w, img.height + CAPTION_HEIGHT), CAPTION_BG)
    canvas.paste(img, (0, CAPTION_HEIGHT))
    draw = ImageDraw.Draw(canvas)
    title_font = _load_font(26)
    sub_font = _load_font(16)
    tb = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((w - (tb[2] - tb[0])) / 2, 14), title, font=title_font, fill=CAPTION_FG)
    if sub:
        sb = draw.textbbox((0, 0), sub, font=sub_font)
        draw.text(((w - (sb[2] - sb[0])) / 2, 52), sub, font=sub_font, fill=ACCENT_GREEN)
    canvas.save(dst)


async def click_text(page, text: str) -> None:
    btn = page.get_by_role("button", name=text).first
    await btn.wait_for(state="visible", timeout=5000)
    await btn.click()
    print(f"  clicked: {text!r}")


async def shoot_clip(page, path: Path) -> None:
    await page.screenshot(path=str(path), clip=CLIP)


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1400})
        page = await ctx.new_page()
        await page.goto("http://localhost:8765", wait_until="networkidle")
        await page.wait_for_timeout(5000)

        await page.get_by_role("tab", name="🔧 Self-Repair").click()
        await page.wait_for_timeout(2500)

        steps: List[Tuple[Path, str, str]] = []

        # Frame 1: canonical
        raw1 = FRAMES_DIR / "f1_raw.png"
        await shoot_clip(page, raw1)
        steps.append((raw1, "Canonical state", "7 priority rules · all blue"))

        # Frame 2: Break it
        await click_text(page, "⚠️  Break it (drop RL cues)")
        await page.wait_for_timeout(2500)
        raw2 = FRAMES_DIR / "f2_raw.png"
        await shoot_clip(page, raw2)
        steps.append((raw2, "Click 'Break it'",
                      "4 reinforcement-learning rules now dashed gray"))
        steps.append((raw2, "Pipeline misclassifies the dopamine golden",
                      "expected: reinforcement_learning · got: predictive_processing"))

        # Frame 3: Run flywheel
        await click_text(page, "▶️  Run flywheel")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(8000)
        rules_path = REPO / "agent" / "data" / "priority_rules.json"
        rule_count = len(json.loads(rules_path.read_text()))
        print(f"  rules after flywheel: {rule_count}")
        raw3 = FRAMES_DIR / "f3_raw.png"
        await shoot_clip(page, raw3)
        steps.append((raw3, "flywheel observed the regression",
                      "Patch proposed · sandbox validated · promoted to disk"))
        steps.append((raw3, "✨  Patch promoted",
                      "reward prediction error → reinforcement_learning"))

        # Frame 4: scroll to validators
        await page.evaluate("window.scrollBy(0, 300)")
        await page.wait_for_timeout(800)
        raw4 = FRAMES_DIR / "f4_raw.png"
        await shoot_clip(page, raw4)
        steps.append((raw4, "Provenance recorded",
                      "patch + rollback patch + validators in version_registry"))
        await page.evaluate("window.scrollBy(0, -300)")
        await page.wait_for_timeout(500)

        # Frame 5: Restore
        await click_text(page, "↩️  Restore canonical")
        await page.wait_for_timeout(2000)
        raw5 = FRAMES_DIR / "f5_raw.png"
        await shoot_clip(page, raw5)
        steps.append((raw5, "Restored canonical", "7 rules · all blue again"))

        await browser.close()

    annotated: List[Path] = []
    for i, (raw, title, sub) in enumerate(steps, start=1):
        out = FRAMES_DIR / f"annotated_{i:02d}.png"
        annotate(raw, out, title, sub)
        annotated.append(out)

    out_gif = OUT / "self_repair.gif"
    images = [imageio.imread(p) for p in annotated]
    imageio.mimsave(out_gif, images, duration=1300, loop=0)
    print(f"saved {out_gif} ({out_gif.stat().st_size // 1024} KB, {len(annotated)} frames)")


if __name__ == "__main__":
    asyncio.run(main())
