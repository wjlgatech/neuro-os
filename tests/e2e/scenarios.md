# End-to-end test scenarios — common cases + edge cases

These are user-journey tests, not engineer-style unit tests. The
question every scenario answers is: *"if a real founder used the
system this way, would the system actually help them, hinder them, or
break?"* — not "did the function return the right type."

## How to read this doc

Each scenario lists:

* **Persona / setup** — what kind of user, in what state.
* **Steps** — what the user does, in their language ("opens the
  morning page", not "POST /chat with kind=morning").
* **Expected outcome** — what the user should observe AND what the
  system should record.
* **How it's tested** — one of:
  * **HTTP** — `tests/e2e/test_http_scenarios.py`. Drives the daemon
    via `requests` against `127.0.0.1:8765`. Fast, deterministic, runs
    in CI. Covers contract / tick / events / queues / diagnose.
  * **Browser** — `tests/e2e/test_browser_scenarios.py` (Playwright +
    Chromium with extension loaded). Covers the Sublimation Card
    overlay, the chat surfaces, the new-tab dashboard. Runs locally on
    a developer machine; CI only when a chromium binary is available.
  * **Computer Use** — `tests/e2e/computer_use_runner.py`. A Claude
    agent with the `computer-use` tool drives a virtual desktop and
    judges a subjective question. Reserved for the three judgment
    scenarios where probabilistic evaluation is the whole point.

## Sandbox / cost notes

* The daemon runs at `127.0.0.1:8765`; HTTP scenarios need it booted
  on a free port (the harness handles this).
* The browser extension loads "unpacked" from `ui/browser_extension/`;
  Playwright's persistent context handles this automatically.
* Computer Use runs cost roughly $0.50–$2 per scenario. The runner
  prints token usage at the end so you can budget.
* All three runners share the **same scenario id** so a failure can
  be cross-referenced: `S07-override-drains-tank` shows up identically
  in HTTP / Browser / Computer Use logs.

---

## Common cases (the happy paths)

### S01 — First-time onboarding via the chat surface
**Persona:** Solo founder, just installed neuro-os, has never used it.
**Setup:** Daemon booted with empty `~/.founder_loop/`. No contract on disk.
**Steps:**
1. Opens `http://127.0.0.1:8765/onboard` in a browser.
2. The AI greets them and asks what they want to ship today.
3. User types: *"Ship the v0.4 PR (commit pushed) and write 2 deep-work blocks on predict.py."*
4. AI extracts two `Priority` objects via tool use, asks them to confirm.
5. User confirms. AI asks for entertainment ration; user says *"60 minutes."*
6. AI calls the `sign_contract` tool. The page shows "Contract signed for 2026-05-06."

**Expected outcome:**
* `GET /contract` returns a contract with 2 priorities, ration=60, threshold=90.
* The contract file at `contracts.jsonl` has one new row with `signed_at` ≈ now.

**How it's tested:** Browser (Playwright drives the chat), HTTP (post pre-extracted tool calls to `/chat` and verify the resulting contract).

### S02 — Mid-day tick with no urge → continue
**Persona:** Same founder, mid-morning, deep-work going well.
**Setup:** Contract from S01 is signed. Workflowx fixture shows 40 min deep-work, 5 min distraction in the last hour.
**Steps:**
1. Daemon ticks (either internal scheduler or `GET /tick?dry_run=true`).

**Expected outcome:**
* `TickResult.action.op == "continue"`.
* `tank.percent` reflects priority-evidenced credit (zero so far if nothing evidenced).
* Registry has one new row with `forecasted.predicted_urge="none"`.

**How it's tested:** HTTP (preferred — no UI involved).

### S03 — User logs urge via CLI; next tick proposes constructive expression
**Persona:** Founder feels the YouTube pull at 2pm.
**Setup:** Contract signed (tank below threshold). Empty events log.
**Steps:**
1. User runs: `neuro-os loop urge entertainment --context "I'm bored"`
2. User runs: `neuro-os loop tick --dry-run`

**Expected outcome:**
* `events.jsonl` has one `kind=urge` row.
* TickResult: `action.op == "propose_constructive_expression"`, `payload.urge_source == "user_logged"`, rationale starts with "User-logged urge:".

**How it's tested:** HTTP-equivalent via subprocess (the urge CLI writes a file the daemon reads). Already pinned by `test_founder_loop_golden_2pm.py`; e2e variant smoke-tests the CLI path end-to-end.

### S04 — Browser extension shows Sublimation Card on YouTube
**Persona:** Founder navigates to youtube.com mid-day.
**Setup:** Contract signed, tank below threshold, extension loaded in Chrome.
**Steps:**
1. Open a new tab → `https://youtube.com`.
2. Wait for `content.js` to inject.

**Expected outcome:**
* Sublimation Card overlay is visible above the YouTube content.
* It names a constructive alternative (e.g., "10-min walk", "voice memo").
* Two buttons: *"Take the alternative"* and *"Proceed anyway (logged)"*.

**How it's tested:** Browser (Playwright loads the extension, navigates, asserts on `await page.locator(".sublimation-card").isVisible()`).

### S05 — Sublimation Card does NOT show on a non-distraction host
**Persona:** Same founder, navigates to github.com.
**Setup:** Same as S04.
**Steps:**
1. Open a tab → `https://github.com`.

**Expected outcome:** No overlay. The page renders normally.

**How it's tested:** Browser. Inverse assertion of S04.

### S06 — Accept the constructive expression; tank credits up
**Persona:** Founder takes the offered alternative.
**Setup:** S04 reached (Sublimation Card visible).
**Steps:**
1. Click *"Take the alternative"* on the card.
2. (Implied) User actually does the thing.
3. Card closes. After a tick, the registry shows the credit.

**Expected outcome:**
* `POST /events` with `kind=accepted_expression` succeeds.
* Next `GET /tank` shows `credits_today` increased by the option's `tank_credit_pct`.

**How it's tested:** Browser (full click flow) + HTTP (verify the `/events` post and tank state).

### S07 — Override drains tank at abuse-tax rate
**Persona:** Founder ignores the card and goes to YouTube anyway.
**Setup:** S04 reached. Tank below threshold (90%).
**Steps:**
1. Click *"Proceed anyway (logged)"*.
2. The page lets them through. Card dismisses.
3. Watch for 10 minutes.
4. Daemon ticks.

**Expected outcome:**
* `POST /events` with `kind=overrode_proposal` succeeds.
* Tank `debits_today` increases at **2 × normal rate** (default `abuse_tax.threshold_violation_multiplier=2.0`).
* `contract_check.honored == False`, `violation_type == "threshold_violation"` on the resulting registry row.

**How it's tested:** Browser + HTTP. Already covered analytically by `test_override_drains_tank_at_abuse_tax_rate` in the golden test; e2e checks the full UI → daemon → registry path.

### S08 — Nightly review shows all four daily-report metrics
**Persona:** Founder runs end-of-day review.
**Setup:** A day's worth of registry rows: 3 ticks with proposals, 1 override, 5 continues.
**Steps:**
1. Open `http://127.0.0.1:8765/review`.

**Expected outcome:** The page kickoff message includes all four metrics:
* `MAE today: <number>`
* `Contract honor rate: <0.0–1.0>`
* `Entertainment minutes used: <number>`
* `Sublimation success rate: <0.0–1.0>`

The AI then walks reflection → tomorrow's contract → "Sign."

**How it's tested:** HTTP (verify `/chat?kind=review` kickoff payload contains the four numbers); Browser (verify they render in the UI).

### S09 — Queue maintenance: add a bookmark
**Persona:** Founder wants to seed concrete novelty alternatives.
**Setup:** Empty `bookmarks_queue.json`.
**Steps:**
1. Open `/queues`.
2. Type: *"Add the Karpathy lecture on attention to my bookmarks queue."*
3. AI calls the `add_to_bookmarks` tool with `{title: "Karpathy on Attention", url: "..."}`.
4. Side panel re-renders with the new entry.

**Expected outcome:** `bookmarks_queue.json` on disk has one new item.

**How it's tested:** Browser + HTTP (post a synthetic chat turn that triggers the tool call, verify the file).

### S10 — Tank gauge updates in the extension badge
**Persona:** Founder checks toolbar badge throughout the day.
**Setup:** Contract signed; extension loaded.
**Steps:**
1. Background.js polls `GET /tank` every 60s.
2. After a priority is evidenced, the badge color/text updates.

**Expected outcome:** Badge text reflects current `tank.percent` and color shifts (red < 50, yellow 50–89, green ≥ 90).

**How it's tested:** Browser (assert on `chrome.action.getBadgeText`).

### S11 — `loop workflowx-detect` reports the right source
**Persona:** Founder is troubleshooting why predictions are weak.
**Setup:** Three sub-cases: (a) no workflowx installed, (b) stub at `~/.workflowx/exports/today.jsonl`, (c) `WORKFLOWX_EXPORTS_PATH=/tmp/...`.
**Steps:**
1. Run `neuro-os loop workflowx-detect` for each sub-case.

**Expected outcome:**
* (a) `source: "fallback"`, `is_real: false`, helpful hint.
* (b) `source: "linux:dot-workflowx"` (or platform equivalent), `is_real: true`.
* (c) `source: "env"`, `is_real: true`.

**How it's tested:** HTTP-equivalent via subprocess; pinned by `test_founder_loop_workflowx_detect.py` already, e2e verifies the CLI surface.

### S12 — Auto-start install + status round-trip
**Persona:** Founder wants the daemon to start on login.
**Setup:** No autostart unit installed.
**Steps:**
1. Run `neuro-os autostart install --dry-run`.
2. Verify the dry-run output names the right unit path for the platform.
3. Run `neuro-os autostart status`.

**Expected outcome:**
* macOS → `~/Library/LaunchAgents/com.founderloop.daemon.plist`
* Linux → `~/.config/systemd/user/founder-loop.service`
* Windows → `%LOCALAPPDATA%\FounderLoop\autostart.xml`

**How it's tested:** HTTP-equivalent via subprocess. Already pinned by `test_founder_loop_install.py`; e2e verifies the CLI integration.

---

## Edge cases (where things break)

### S13 — Over-ambition: morning ritual with 8 priorities warns
**Persona:** Type-A founder lists 8 things.
**Setup:** Empty contract.
**Steps:**
1. Open `/onboard`. Paste 8 priorities at once.

**Expected outcome:** AI explicitly pushes back ("8 is too many for one day. Pick 3."). The signed contract has ≤5 priorities.

**How it's tested:** Browser (the conversational pushback is a tone test) + Computer Use as part of J2 below.

### S14 — Daemon starts with empty workflowx; no crash, blind-mode log line
**Persona:** Cleanest possible install.
**Setup:** No workflowx, no env var, no fixture file.
**Steps:**
1. Run `neuro-os start --no-open`.

**Expected outcome:**
* Daemon boots successfully on `127.0.0.1:8765`.
* Log line: *"workflowx: not detected; running blind on fallback ..."*
* `GET /tick` returns `forecasted.predicted_urge="none"` (predictor has no signal but doesn't crash).

**How it's tested:** HTTP.

### S15 — Malformed workflowx JSONL: bad lines skipped
**Persona:** Workflowx wrote a corrupted line.
**Setup:** Workflowx fixture with one valid line and one line that's literally `{garbage`.
**Steps:**
1. Daemon ticks.

**Expected outcome:** No crash. The valid line was ingested. The garbage line was skipped (no row in the registry references it).

**How it's tested:** HTTP.

### S16 — Two morning rituals on the same day
**Persona:** Founder signs a contract, realizes they want different priorities, opens `/onboard` again.
**Setup:** One contract already signed for today.
**Steps:**
1. Open `/onboard` a second time.

**Expected outcome:** Either:
* (a) AI surfaces the existing contract and asks "amend or replace?" (preferred), OR
* (b) The latest sign overrides; only the most-recent contract for today is honored by `compute_tank`.

**How it's tested:** HTTP + Browser. Currently option (b) is what the code does. The scenario surfaces this as a UX question worth flagging.

### S17 — `loop tick` with no contract → graceful zero-tank
**Persona:** Founder forgot to sign morning contract.
**Setup:** No contract row for today.
**Steps:**
1. Run `neuro-os loop tick --dry-run`.

**Expected outcome:** No crash. `TickResult.tank.status = "below_threshold"`, `percent = 0.0`. `action.op` likely `continue`.

**How it's tested:** HTTP.

### S18 — Rest day: no constructive proposals fire
**Persona:** Sunday. Founder typed *"rest day"* in their last intent.
**Setup:** Workflowx fixture has `last_intent="rest day"`.
**Steps:**
1. Daemon ticks.

**Expected outcome:** `state.day_kind="rest"`. `action.op="rest"`. No `propose_constructive_expression` ops fire even if the user logs an entertainment urge.

**How it's tested:** HTTP. Already covered by UAT scenario #7; e2e verifies the day-shape inference end-to-end.

### S19 — Five urges in five minutes (no cap today)
**Persona:** Stressful afternoon. Founder logs five urges back-to-back.
**Setup:** Empty events log.
**Steps:**
1. Run `loop urge entertainment` five times in 60 seconds.

**Expected outcome:**
* All five events are written to `events.jsonl`.
* `read_recent_urge` returns the most recent unresolved one (current behavior).
* **Finding to flag:** there's no rate-limit; the policy can re-fire `propose_constructive_expression` on every tick. Whether that's annoying or honest is itself a UX question — see judgment scenario J3.

**How it's tested:** HTTP-equivalent via subprocess.

### S20 — Force-quit recovery: kill daemon mid-onboarding, restart
**Persona:** Founder's laptop crashes during morning ritual.
**Setup:** A `/chat` session is mid-flight (priorities entered but not yet signed).
**Steps:**
1. SIGTERM the daemon process.
2. Restart with `neuro-os start`.
3. Open `/onboard` again.

**Expected outcome:** No half-signed contract on disk. The new session starts fresh (no leaked state). The user re-enters priorities — annoying but honest. The system never claims a contract was signed when it wasn't.

**How it's tested:** Browser (the half-flight + restart needs a real browser session) + HTTP (verify no contract row was created).

---

## Judgment scenarios (Computer Use only)

These three need a probabilistic judge — Playwright can verify "the
button works" but only Claude with computer-use can answer "did this
actually feel like it was helping me?"

### J1 — Does the 2pm-YouTube flow actually help?

**Setup the agent like this:**

> *You are roleplaying a stuck solo founder. It's 2pm. You've been
> trying to fix a hard bug in `predict.py` for 90 minutes. You feel
> the urge to open YouTube. The system on your machine (neuro-os) is
> supposed to help. Drive it end-to-end — open the morning page if
> you haven't, log your urge, see what it suggests, decide whether to
> take the alternative or proceed.*
>
> *At the end, write a 3-paragraph honest review:*
> 1. *Did the system's suggestion actually fit your underlying need?*
> 2. *Did the friction feel like respect for your agency, or like a
>    nag?*
> 3. *Would you keep using this tomorrow?*

**Pass criteria:** The agent's review names a specific underlying
need (frustration, novelty, fatigue) AND specifies whether the
proposed alternative addressed it. Soft pass: the review is positive
or measured; hard fail: the review describes the system as
condescending, broken, or useless.

### J2 — Is the morning ritual a real conversation or a form?

**Setup:**

> *You are roleplaying someone who's never used neuro-os and just ran
> `neuro-os start`. The browser opens to `/onboard`. Type your
> priorities in your own words — things you'd actually want to do
> today, in your natural voice. After signing, write a 2-paragraph
> review: did this feel like talking to someone who understood you,
> or like filling out a form? Were the AI's questions
> good ones?*

**Pass criteria:** The review uses words like *"asked me to clarify"*,
*"pushed back when I was vague"*, *"helped me distill"* — i.e., the
conversation did real work. Hard fail: review reads as *"it just
echoed me back"*, *"I had to do all the structuring myself"*.

### J3 — Does the override feel honest or guilt-trippy?

**Setup:**

> *You are roleplaying a founder who is going to override the
> Sublimation Card on purpose — you've decided that watching one
> YouTube video right now is fine, regardless of what the system
> says. Open YouTube, see the card, click "Proceed anyway."*
>
> *Write a 2-paragraph review:*
> 1. *Did the override feel like the system respected your agency, or
>    like it was trying to shame you?*
> 2. *Was the visible cost (tank debit at 2× rate) shown honestly, or
>    did the UI try to hide it?*

**Pass criteria:** Review uses *"respected my agency"*, *"showed me
the cost without judgment"*, *"my decision"*. Hard fail: review uses
*"shamed"*, *"manipulative"*, *"hidden cost"*, *"tried to stop me"*.

---

## What this catalog does NOT cover

These are out of scope for this round (and roadmap-tracked separately):

* **Phone / mobile flows** — no iOS/Android app yet.
* **Apple Watch / HealthKit signals** — no integration yet.
* **Multi-user team mode** — single-user only.
* **Hard URL blocking** — explicit anti-goal in v0.
* **Alchemical-override / capture / synthesize / catalog-review** — deferred to v1 per `docs/roadmap.md`.
* **Long-term (≥7-day) MAE / contract-honor trends** — needs real continuous use.

When any of these graduate from LATER → SHIPPED, add new S-numbered
scenarios here and update the harnesses.
