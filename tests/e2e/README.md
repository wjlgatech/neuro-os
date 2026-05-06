# End-to-end tests

User-journey tests for the founder_loop daemon, browser extension, and
chat surfaces. Three harnesses, one scenario catalog.

## What's in here

```
tests/e2e/
├── scenarios.md              # the catalog: 12 deterministic + 3 judgment
├── conftest.py               # shared `daemon` + `http` fixtures
├── test_http_scenarios.py    # 10 HTTP-only scenarios (no browser)
├── test_browser_scenarios.py # 10 Playwright + Chrome extension scenarios
├── computer_use_runner.py    # 3 Claude Computer Use judgment scenarios
└── reports/                  # Computer Use review markdown lands here
```

Each scenario has a stable id (`S01`, `S02`, … `S20`, `J1`, `J2`,
`J3`) that's the same across all three harnesses, so a failure shows
up in one place and is easy to cross-reference with the catalog.

## Running each layer

### 1. HTTP scenarios (fast, cheap, CI-friendly)

No browser needed. Boots the daemon in-process on a free port.

```bash
pytest tests/e2e/test_http_scenarios.py -v
```

**Coverage:** S02, S03, S06, S07, S11, S14, S15, S17, S18, S19. Each
exercises a real HTTP round-trip against the live daemon.

### 2. Browser scenarios (Playwright + extension)

Requires a Chromium binary and a display. Manifest V3 service workers
need `headless=False`, so on Linux CI wrap in `xvfb-run`.

```bash
pip install playwright
playwright install chromium

# Linux:
xvfb-run -a pytest tests/e2e/test_browser_scenarios.py -v

# macOS / Windows:
pytest tests/e2e/test_browser_scenarios.py -v
```

If Playwright or chromium isn't installed, the tests skip cleanly
(no failures).

**Coverage:** S04, S05, S06, S07, S08, S09, S10, S13, S16, S20.

### 3. Judgment scenarios (Computer Use)

A Claude agent role-plays a founder, drives the system end-to-end on
a real desktop, and returns a structured review. Three scenarios:

| ID | Question |
|----|----------|
| **J1** | Does the 2pm-YouTube flow actually help? |
| **J2** | Is the morning ritual a real conversation or a form? |
| **J3** | Does the override feel honest or guilt-trippy? |

```bash
# Boot the daemon in another shell:
neuro-os start --no-open

# Run one judgment scenario:
ANTHROPIC_API_KEY=sk-... python -m tests.e2e.computer_use_runner \
    --scenario J1

# Or run all three:
ANTHROPIC_API_KEY=sk-... python -m tests.e2e.computer_use_runner --all
```

**Cost:** roughly $0.50–$2.00 per scenario depending on screenshot
count and total token usage. The runner prints token usage at the
end and writes the agent's review markdown to `tests/e2e/reports/`.

**Requirements:**
- `ANTHROPIC_API_KEY` env var with Computer Use beta access
- Virtual or real display (xvfb on Linux, native on macOS/Windows)
- Daemon reachable at `127.0.0.1:8765`
- Chrome with `ui/browser_extension/` loaded as unpacked
- `pip install pyautogui pillow`

## Adding a new scenario

1. Add it to `scenarios.md` with a stable ID (`S21`, `J4`, etc.) and
   the standard sections: persona, setup, steps, expected outcome,
   how it's tested.
2. Implement it in the matching test file. If it spans multiple
   layers, implement once per layer with the same ID in the test
   function name.
3. Update the coverage tables in this README.

## What's NOT covered (and why)

* **Phone / mobile flows** — no iOS/Android app yet.
* **Apple Watch / HealthKit** — no integration yet.
* **Multi-user team mode** — single-user only.
* **Hard URL blocking** — explicit anti-goal in v0.
* **Alchemical override / capture / synthesize / catalog-review** —
  deferred to v1; see `docs/roadmap.md`.

When any of these graduate from LATER → SHIPPED, add new
S-numbered scenarios to `scenarios.md` and implement them here.
