# Roadmap

Three columns. Honest.

- **SHIPPED** is verifiable in the current commit. Run the tests; if
  they pass, it works.
- **NEXT** is what we're focused on this week or next.
- **LATER** is real work that's worth doing but isn't started.

If you're reading this and something in **SHIPPED** doesn't actually
work for you, that's a bug — please file it. If something in
**NEXT** is taking too long, that's a different kind of bug.

---

## SHIPPED (v0.4)

The reward-economy + sublimation engine, plus three UI surfaces. All
verifiable: 80 tests pass.

| Area | Status | What's there |
|---|---|---|
| **Engine** | Complete | Five boxes (sensors → brain → contract → carrot/stick → memory) wired end-to-end. 14 user-acceptance scenarios pass. |
| **Local daemon** | Complete | `127.0.0.1:8765`, eight endpoints, refuses non-loopback bind, no auth (boundary is the loopback). |
| **Conversational morning ritual** | Complete | `/onboard` chat page. Users tell the AI what matters; AI extracts structured priorities via tool use. Falls back to a state-machine without an API key. |
| **Browser extension (Manifest V3)** | Complete | Toolbar badge, popup, new-tab dashboard, sublimation overlay on 8 distraction hosts. Honors agency: nothing blocks. |
| **System tray app** | Complete | Cross-platform (Linux / macOS / Windows). Tank gauge in the menu bar; menu actions for tick / show contract / quit. |
| **Sublimation catalog** | 6 needs | fatigue, novelty_hunger, social, frustration, decision_fatigue, embodied (hunger / eye-strain). |
| **Per-user queues** | 3 queues | bookmarks, social, rubber_duck. JSON files; populated manually. |
| **First-run defaults** | Complete | `neuro-os loop serve` with no args creates `~/.founder_loop/` and an empty workflowx fixture. |

---

## NEXT (this week)

These are the ordered next steps. Each is small enough to land in
1–3 days.

| # | Item | Why now | Days | Where |
|---|---|---|---|---|
| 1 | **`neuro-os start` alias** + auto-launch in browser | Today's `neuro-os loop serve` followed by manual URL-paste is two steps; should be one. | 0.5 | `agent/cli.py` |
| 2 | **Auto-start on login** (launchd unit on macOS, systemd-user unit on Linux, Task Scheduler on Windows) | Users close the terminal and the app dies. Real apps don't do this. | 1.5 | New `agent/founder_loop/install.py` |
| 3 | **Conversational nightly review** (`/review` page) | Currently CLI-only. Should match the morning ritual's polish. | 1 | New route + reuse `conversation.py` |
| 4 | **Conversational queue maintenance** (`/queues` page) | Editing JSON by hand is the kind of thing this whole project rejects. | 1 | New route + chat tool to write JSON |
| 5 | **Daemon-internal tick scheduler** | Hourly ticks via `cron` is engineer-only. Daemon should own its own clock. | 0.5 | `agent/founder_loop/server.py` background thread |
| 6 | **One-pager `/about`** at the daemon | Today the docs are on GitHub; the user has to know to look. The daemon should serve `what-is-this.md` rendered. | 0.5 | New route |

Total estimate: ~5 days of focused work to close the "engineer-friendly leakage" gap.

---

## LATER (next quarter or v1)

Real work, not started.

| Area | Why it matters | Cost (rough) |
|---|---|---|
| **One-click installer** (`.dmg` / `.exe` / `.AppImage`) | Today's `pip install` is a barrier for non-coders. Real installers solve it. | 1 week + ongoing code-signing certs (~$300/yr Apple, free on others). |
| **Chrome Web Store + Firefox AMO listings** | "Load unpacked" is dev-only. Store listings need review. | 1 week + ongoing reviewer back-and-forth. |
| **iOS / Android companion app** | Phone is where many urges fire (Instagram, TikTok). Desktop-only is a real gap. | 4–6 weeks + Apple Developer account. |
| **Apple Watch complication** | The watch is the embodied-need sensor (HRV → fatigue, stand time → eye-strain). Massive accuracy upgrade. | 2 weeks + iOS app prerequisite. |
| **Workflowx auto-detect** | Today the user must pass `--workflowx-fixture`. Should auto-find `~/Library/.../workflowx/exports/` if present. | 1 day. |
| **Native Screen Time integration** (`pre_authorized_blocks` actually fires) | Currently `block_url` is a logged event, not a real block. Real blocks need OS-level permission. | 1 week (macOS first via Family Controls API). |
| **Apple Health / HealthKit pull** for sleep | Removes the workflowx-fixture dependency for the most-load-bearing signal. | 3 days inside the iOS app. |
| **L2 self-modification of the sublimation catalog** | Currently the catalog is hand-edited; v1 promotes it under `mutable_paths` so failed-golden runs can rewrite catalog entries automatically. | 1 week + careful safety testing. |
| **Multi-user / team mode** | Today single-user only. A founders' chat where teams hold each other accountable would be powerful — but is its own product. | 4+ weeks. Defer. |
| **Voice morning ritual** | Speaking your priorities is faster than typing for the daily ceremony. Whisper API + iOS Shortcut. | 3 days. |
| **iMessage / SMS bot** | Universal-fallback intercept on any device. | 1 week + Twilio costs. |
| **Hosted (cloud) version** | Some users would happily trade privacy for "works on every device." We'd need to build it carefully — encrypted-at-rest, e2e if possible. | 4–6 weeks + ongoing infra. |
| **MAE-trend dashboard** in `/today` | Currently a CLI nightly print. Worth a small chart in the dashboard once we have ≥7 days of real data. | 0.5 day. |

---

## Anti-goals

Things we are *not* going to build, and why.

- **A blocking mode.** Hard URL/app blocks defeat the philosophy. The
  "stick" in carrot/stick is making cost visible, not removing
  agency. If a user wants a hard block, they have plenty of other
  apps.
- **Gamification (streaks, leaderboards, achievements).** Distorts
  the contract from "promise to yourself" to "score in someone
  else's game." If it makes the user perform for the app instead of
  for themselves, it's wrong.
- **A social feed.** The data is yours; we don't share it. If
  community accountability becomes a feature, it'll be opt-in,
  per-message, and never automatic.
- **Telemetry / "anonymous usage data".** Even anonymized telemetry
  is a leak of attention patterns. If we ever add it, it'll be
  per-feature opt-in with a visible kill-switch.

---

## How to read this

If you're a user: focus on **SHIPPED**. That's what works today.
**NEXT** is what removes the rough edges in the next week or two.
**LATER** is "we'd love to" — don't count on any specific timeline.

If you're a contributor: pick from **NEXT** — those are scoped and
ready to start. Don't pick from **LATER** without first writing a
short design note here in `docs/` so we can align.

If you're trying to decide whether to use this: today the rough edges
are real (terminal install, manual workflowx, no phone). The
philosophy and core engine are solid. If those rough edges are too
much, watch the **NEXT** column ship.
