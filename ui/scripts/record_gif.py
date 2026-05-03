"""
Record a self-repair animation GIF.

Drives the Self-Repair tab through 5 state transitions:
  1. canonical (initial)
  2. after Break it
  3. after Run flywheel
  4. result panel showing patch + validators
  5. after Restore canonical

Captures a clipped screenshot focused on the routing graph + key
buttons at each step, then stitches them into a GIF with imageio.

The clipped region is chosen so each frame is the same width/height,
so the resulting GIF is dimensionally consistent.
"""
import asyncio
import json
from pathlib import Path
from typing import List

import imageio.v2 as imageio
from playwright.async_api import async_playwright


OUT = Path("/Users/jialiang.wu/Documents/Projects/neuro-os/ui/assets")
FRAMES_DIR = Path("/tmp/gif_frames")
FRAMES_DIR.mkdir(parents=True, exist_ok=True)


# Each frame is a 1200x800 region anchored at (40, 360) which captures
# the page from the start of the Self-Repair section (heading + buttons
# + graph). Tuned visually.
CLIP = {"x": 40, "y": 320, "width": 1200, "height": 1000}


async def shoot(page, path: Path) -> None:
    await page.screenshot(path=str(path), clip=CLIP)


async def click_text(page, text: str) -> None:
    """Click a button by visible text — Streamlit-friendly."""
    btn = page.get_by_role("button", name=text).first
    # Wait for button to be ready, then click. Streamlit removes/re-adds
    # buttons on rerun, so a stale reference is real.
    await btn.wait_for(state="visible", timeout=5000)
    await btn.click()
    print(f"  clicked: {text!r}")


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1400})
        page = await ctx.new_page()
        await page.goto("http://localhost:8765", wait_until="networkidle")
        await page.wait_for_timeout(5000)

        # Switch to Self-Repair
        await page.get_by_role("tab", name="🔧 Self-Repair").click()
        await page.wait_for_timeout(2500)

        frames: List[Path] = []

        # Frame 1: canonical
        f1 = FRAMES_DIR / "f1_canonical.png"
        await shoot(page, f1)
        frames.append(f1)

        # Frame 2: after Break it
        await click_text(page, "⚠️  Break it (drop RL cues)")
        await page.wait_for_timeout(2500)
        # Streamlit may have re-rendered the tab — make sure we're still on Self-Repair
        await page.wait_for_timeout(1000)
        f2 = FRAMES_DIR / "f2_broken.png"
        await shoot(page, f2)
        frames.append(f2)
        # Hold a moment showing broken state
        frames.append(f2)

        # Frame 3: after Run flywheel.
        # Wait longer — the meta-loop runs a subprocess validator that
        # spawns a fresh python interpreter to re-run goldens against
        # the sandbox copy. That can take 5-8 seconds on cold cache.
        await click_text(page, "▶️  Run flywheel")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(8000)
        # Re-confirm the file has the new rule
        rules_path = Path("/Users/jialiang.wu/Documents/Projects/neuro-os/agent/data/priority_rules.json")
        print(f"  rules after flywheel: {len(json.loads(rules_path.read_text()))}")
        f3 = FRAMES_DIR / "f3_running.png"
        await shoot(page, f3)
        frames.append(f3)
        # Hold the result frame
        frames.append(f3)
        frames.append(f3)

        # Frame 4: scroll down a bit to see the validator results panel
        await page.evaluate("window.scrollBy(0, 300)")
        await page.wait_for_timeout(800)
        f4 = FRAMES_DIR / "f4_validators.png"
        await shoot(page, f4)
        frames.append(f4)
        frames.append(f4)

        # Scroll back up
        await page.evaluate("window.scrollBy(0, -300)")
        await page.wait_for_timeout(500)

        # Frame 5: Restore canonical
        await click_text(page, "↩️  Restore canonical")
        await page.wait_for_timeout(2000)
        f5 = FRAMES_DIR / "f5_restored.png"
        await shoot(page, f5)
        frames.append(f5)

        await browser.close()

        # Stitch into GIF
        images = [imageio.imread(f) for f in frames]
        out_gif = OUT / "self_repair.gif"
        imageio.mimsave(out_gif, images, duration=900, loop=0)  # ms per frame
        print(f"saved {out_gif} ({out_gif.stat().st_size // 1024} KB, {len(frames)} frames)")


asyncio.run(main())
