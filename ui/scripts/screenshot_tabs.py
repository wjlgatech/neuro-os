"""Take per-tab screenshots of the running Streamlit app."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("/Users/jialiang.wu/Documents/Projects/neuro-os/ui/assets")
OUT.mkdir(parents=True, exist_ok=True)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        await page.goto("http://localhost:8765", wait_until="networkidle")
        await page.wait_for_timeout(5000)

        # Tab 1: Try It (initial)
        await page.screenshot(path=str(OUT / "01_try_it.png"))

        # Try It with a preset selected + Run clicked
        await page.locator("textarea").first.fill(
            "Predictive coding minimizes sensory prediction error across cortical hierarchy. Friston (2010) frames this as free-energy minimization."
        )
        await page.wait_for_timeout(500)
        # Find Run button on Try It tab
        await page.get_by_role("button", name="Run", exact=True).first.click()
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(OUT / "02_try_it_result.png"), full_page=True)

        # Tab 2: Watch It Learn
        await page.get_by_role("tab", name="🌱 Watch It Learn").click()
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(OUT / "03_watch_learn.png"))

        # Tab 3: Self-Repair
        await page.get_by_role("tab", name="🔧 Self-Repair").click()
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(OUT / "04_self_repair.png"))

        # Tab 4: Readiness — toggle a few questions for visual interest
        await page.get_by_role("tab", name="📊 Readiness").click()
        await page.wait_for_timeout(2500)
        toggles = page.locator('[data-testid="stCheckbox"], [role="switch"], input[type="checkbox"]')
        count = await toggles.count()
        for i in range(min(3, count)):
            try:
                await toggles.nth(i).click(force=True)
            except Exception:
                pass
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(OUT / "05_readiness.png"), full_page=True)

        await browser.close()


asyncio.run(main())
print("done")
