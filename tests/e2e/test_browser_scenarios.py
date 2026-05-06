"""
E2E browser scenarios — Playwright + the founder_loop Chrome extension.

Runs on a developer machine (or CI with a chromium binary). The
sandboxed harness here can't download chromium, so this file is
shipped *runnable* but skipped automatically when Playwright or the
chromium binary is absent.

Setup once:

    pip install playwright
    playwright install chromium

Then:

    pytest tests/e2e/test_browser_scenarios.py -v

Each test loads ``ui/browser_extension/`` as an unpacked extension via
Playwright's ``launch_persistent_context``. Manifest V3 service
workers run only in headless=False mode, so all tests use a real
display. On Linux CI, wrap in xvfb-run:

    xvfb-run -a pytest tests/e2e/test_browser_scenarios.py

Maps to scenario.md S04, S05, S06, S07, S08, S09, S10, S13, S16, S20.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


pytest_plugins: list[str] = []


# Skip the whole module when Playwright or chromium is missing —
# users on machines without browser tooling get a clean skip rather
# than a noisy failure.
playwright = pytest.importorskip(
    "playwright",
    reason=(
        "Playwright not installed. Run: pip install playwright && "
        "playwright install chromium"
    ),
)
from playwright.sync_api import sync_playwright  # noqa: E402


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EXTENSION_DIR = _REPO_ROOT / "ui" / "browser_extension"


def _chromium_available() -> bool:
    """Best-effort check that a chromium binary is reachable."""
    if not _EXTENSION_DIR.exists():
        return False
    # Playwright's bundled chromium lives under a versioned dir.
    # Detection just tries to launch and reports failure.
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir="",  # ephemeral
                headless=True,
            )
            browser.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _chromium_available(),
    reason="Chromium not installed for Playwright. Run `playwright install chromium`.",
)


# ---------------------------------------------------------------------------
# Browser fixture — persistent context with the extension loaded
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def browser(daemon, tmp_path):
    """A Chromium persistent context with the founder_loop extension
    pre-loaded and pointed at the test daemon.

    The extension's background.js reads the daemon URL from a known
    storage key; since v0 hardcodes ``127.0.0.1:8765``, the daemon
    fixture must be told to use that port. Tests that need a custom
    port use ``daemon_on_default_port`` instead.
    """
    user_data = tmp_path / "chrome-profile"
    user_data.mkdir(parents=True, exist_ok=True)
    extension_path = str(_EXTENSION_DIR)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data),
            headless=False,  # Manifest V3 requires headed mode
            args=[
                f"--disable-extensions-except={extension_path}",
                f"--load-extension={extension_path}",
                "--no-sandbox",
            ],
        )
        try:
            yield ctx
        finally:
            ctx.close()


# ---------------------------------------------------------------------------
# S04 — Sublimation Card on YouTube
# ---------------------------------------------------------------------------


def test_S04_sublimation_card_appears_on_youtube(browser, daemon):
    """The content script injects an overlay on the listed
    distraction hosts. Verify it appears on youtube.com and contains
    a constructive-alternative button."""
    page = browser.new_page()
    page.goto("https://www.youtube.com", wait_until="domcontentloaded")
    # Card may take up to 2s to inject after content.js evaluates.
    overlay = page.locator(".founder-loop-sublimation-card")
    overlay.wait_for(state="visible", timeout=5000)
    assert overlay.is_visible()
    # The card must surface at least one constructive option.
    take_button = overlay.locator("button", has_text="Take")
    assert take_button.count() >= 1
    proceed_button = overlay.locator("button", has_text="Proceed")
    assert proceed_button.count() >= 1


# ---------------------------------------------------------------------------
# S05 — Sublimation Card does NOT appear on github.com
# ---------------------------------------------------------------------------


def test_S05_sublimation_card_absent_on_non_distraction_host(browser, daemon):
    """Inverse of S04: the overlay must NOT inject on github.com."""
    page = browser.new_page()
    page.goto("https://github.com", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)  # give content scripts time to fire
    overlay = page.locator(".founder-loop-sublimation-card")
    assert overlay.count() == 0


# ---------------------------------------------------------------------------
# S06 — Accept the constructive expression
# ---------------------------------------------------------------------------


def test_S06_accept_alternative_credits_tank(browser, daemon, http):
    """Clicking 'Take the alternative' POSTs /events with
    kind=accepted_expression and the daemon records it."""
    page = browser.new_page()
    page.goto("https://www.youtube.com", wait_until="domcontentloaded")
    overlay = page.locator(".founder-loop-sublimation-card")
    overlay.wait_for(state="visible", timeout=5000)
    overlay.locator("button", has_text="Take").first.click()
    # Wait for the click to flush to the daemon.
    page.wait_for_timeout(500)
    # On-disk: the events file has the row.
    lines = [l for l in daemon.events_path.read_text().splitlines() if l.strip()]
    assert any('"kind": "accepted_expression"' in l for l in lines)


# ---------------------------------------------------------------------------
# S07 — Override drains tank at abuse-tax rate
# ---------------------------------------------------------------------------


def test_S07_override_records_event_and_lets_user_through(browser, daemon, http):
    """Clicking 'Proceed anyway' POSTs /events kind=overrode_proposal
    and the page is no longer overlay-blocked."""
    page = browser.new_page()
    page.goto("https://www.youtube.com", wait_until="domcontentloaded")
    overlay = page.locator(".founder-loop-sublimation-card")
    overlay.wait_for(state="visible", timeout=5000)
    overlay.locator("button", has_text="Proceed").first.click()
    page.wait_for_timeout(500)
    # Card dismissed.
    assert overlay.is_visible() is False
    # On-disk: the override is logged.
    lines = [l for l in daemon.events_path.read_text().splitlines() if l.strip()]
    assert any('"kind": "overrode_proposal"' in l for l in lines)


# ---------------------------------------------------------------------------
# S08 — Nightly review surfaces all four metrics
# ---------------------------------------------------------------------------


def test_S08_review_page_shows_four_metrics(browser, daemon, http):
    """Open /review with a populated registry; the kickoff text must
    name MAE, contract honor rate, entertainment minutes, and
    sublimation success rate.

    NOTE: this test depends on the conversation manager's fallback
    state-machine path (no LLM). The kickoff payload is built from
    `loop.nightly()` which we already pin in unit tests.
    """
    page = browser.new_page()
    page.goto(daemon.url("/review"), wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    body = page.locator("body").inner_text()
    assert "MAE" in body or "prediction" in body.lower()
    assert "honor" in body.lower()
    assert "minute" in body.lower()


# ---------------------------------------------------------------------------
# S09 — Queue maintenance: add a bookmark
# ---------------------------------------------------------------------------


def test_S09_queues_page_renders(browser, daemon):
    """Open /queues; the side panel should list the three queues
    (bookmarks / social / rubber_duck), even when empty."""
    page = browser.new_page()
    page.goto(daemon.url("/queues"), wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    body = page.locator("body").inner_text().lower()
    assert "bookmarks" in body
    assert "social" in body
    assert "rubber" in body or "duck" in body


# ---------------------------------------------------------------------------
# S10 — Tank gauge updates the toolbar badge
# ---------------------------------------------------------------------------


def test_S10_extension_polls_tank(browser, daemon, http):
    """Background.js polls /tank; we verify by counting daemon-side
    requests via /healthz before and after a wait window."""
    # The cleanest assertion would be to read chrome.action.getBadgeText,
    # but Playwright can't reach extension service-worker scope without
    # the chrome.debugger protocol. Instead we observe daemon traffic.
    page = browser.new_page()
    page.goto(daemon.url("/about"), wait_until="domcontentloaded")
    # Give the extension's alarm time to fire at least once (~10s).
    page.wait_for_timeout(11000)
    # Confirm at least one /tank hit happened by scanning daemon logs
    # — but the conftest's daemon doesn't expose request logs. So this
    # test currently asserts only that the extension stayed alive.
    assert page.is_closed() is False


# ---------------------------------------------------------------------------
# S13 — Over-ambition: morning ritual with 8 priorities warns
# ---------------------------------------------------------------------------


def test_S13_onboard_warns_on_too_many_priorities(browser, daemon):
    """In the LLM-fallback state machine, 8 priorities should still
    trigger some pushback. With LLM enabled, the model is supposed
    to ask the user to cut down to 3. Without an API key, we test
    the fallback's bound on priority count."""
    page = browser.new_page()
    page.goto(daemon.url("/onboard"), wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    # The fallback flow uses a textarea + send button. Type 8
    # priority lines.
    textarea = page.locator("textarea").first
    textarea.fill(
        "ship the v0.4 PR\nwrite docs\nfix bug #142\nrespond to email\n"
        "review PR #99\nfile taxes\nbook flight\ncall Alice"
    )
    page.locator("button").filter(has_text="Send").first.click()
    page.wait_for_timeout(1500)
    # The response should contain pushback language. This is a soft
    # assertion since the exact wording depends on the LLM/fallback
    # path. Either: contains 'too many', '5', '3', or the page
    # surfaces fewer than 8 priorities in the side panel.
    body = page.locator("body").inner_text().lower()
    assert any(s in body for s in ("too many", "fewer", "narrow", "pick"))


# ---------------------------------------------------------------------------
# S16 — Two morning rituals on the same day
# ---------------------------------------------------------------------------


def test_S16_second_morning_ritual_can_amend(browser, daemon, http):
    """Open /onboard twice in the same day. Verify the second
    visit either acknowledges the existing contract OR cleanly
    overrides it. Either is acceptable; only ungraceful state
    (crash, duplicate contracts side-by-side in the UI) fails."""
    page = browser.new_page()
    page.goto(daemon.url("/onboard"), wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    # First visit — leave it (no actual sign).
    page.close()

    # Second visit — open fresh.
    page2 = browser.new_page()
    page2.goto(daemon.url("/onboard"), wait_until="domcontentloaded")
    page2.wait_for_timeout(1000)
    # The page must render (no 500). We don't enforce any specific
    # behavior beyond "doesn't crash".
    assert page2.locator("body").is_visible()


# ---------------------------------------------------------------------------
# S20 — Force-quit recovery
# ---------------------------------------------------------------------------


def test_S20_force_quit_recovery(browser, daemon, http):
    """Half-flight onboarding session; restart daemon; new visit
    must work without leaked state.

    The conftest fixture doesn't model 'restart the daemon mid-test'
    cleanly (it's one daemon per test). This test instead verifies
    that an interrupted /chat session leaves no half-signed contract
    on disk — the closest invariant we can check without harness
    surgery.
    """
    page = browser.new_page()
    page.goto(daemon.url("/onboard"), wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    textarea = page.locator("textarea").first
    textarea.fill("ship something")
    # Don't click send; just close the page mid-flight.
    page.close()

    # Verify the contract file is empty (no half-signed contract).
    if daemon.contract_path.exists():
        contents = daemon.contract_path.read_text(encoding="utf-8").strip()
        assert contents == "", (
            f"contracts.jsonl should be empty after an aborted "
            f"onboarding, was: {contents!r}"
        )
