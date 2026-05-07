# How to use it

This doc covers the five moments you'll have with the app. For each
one: what you do, what happens, and what it looks like.

Honest note: the app is alpha. All five moments are polished — what's
still rough is **distribution** (today you install via `pip`, not a
one-click `.dmg`). The roadmap (`./roadmap.md`) tracks distribution.

---

## First — get it running on your computer

Today this is **two steps**, not one click. We're working on a real
installer; for now:

```
pip install neuro-os
neuro-os start
```

The `start` command does four things in the background:
- Creates a folder at `~/.founder_loop/` for your private data.
- Boots a small server on `127.0.0.1:8765` (only your machine can
  reach it; nothing leaves your computer).
- **Auto-detects your workflowx export** if it exists (macOS
  Application Support, Linux `~/.config`, etc.) — see
  [Box 1 in how-it-works](./how-it-works.md) for the full precedence.
  Logs the detected path so you know whether real signal is flowing.
- Opens [`http://127.0.0.1:8765/onboard`](http://127.0.0.1:8765/onboard)
  in your default browser.

From here on, you mostly won't touch the terminal.

> **Want it to start when you log in?** Run
> `neuro-os autostart install` once. That writes a launchd plist
> (macOS), a systemd-user service (Linux), or a Task Scheduler XML
> (Windows). `--dry-run` previews what would be written. Reverse with
> `neuro-os autostart uninstall`.

> **One-click installer (`.dmg` / `.exe` / `.AppImage`)** is on the
> roadmap if even `pip install` feels like too much.

---

## Moment 1 — Start your day

**You do**: Open `http://127.0.0.1:8765/onboard` in your browser. You
see a chat page. Tell it what matters today, in your own words.

**The app does**: Asks you the questions it needs (how will we know
this is done? must-do or nice-to-have?). Writes each priority into a
side panel as it crystallizes. When you're done adding things, asks
how long of an entertainment ration you want for the day. Then shows
you the whole contract and waits for you to click **Sign**.

**Sketch**:

```
 ┌───────────────────────────────────────────────┬──────────────────────────────┐
 │  Morning ritual                               │  Today's priorities          │
 │  ● ready · LLM mode                           │                              │
 │                                               │  ┌─────────────────────────┐ │
 │  AI: Good morning. What's important today?    │  │ P3  ship the report     │ │
 │                                               │  │     pr_merged · #142    │ │
 │  YOU: I want to ship the report and call      │  └─────────────────────────┘ │
 │       my sister                               │  ┌─────────────────────────┐ │
 │                                               │  │ P2  call my sister      │ │
 │  AI: Got it. Two priorities so far. For       │  │     human signoff · sis │ │
 │       the report — is it merging the PR or    │  └─────────────────────────┘ │
 │       opening it?                             │                              │
 │                                               │  Settings                    │
 │  YOU: merging                                 │  Entertainment ration        │
 │                                               │  [60] min after 90%          │
 │  AI: Good. And how important is it today —    │                              │
 │       must-do or nice-to-have?                │                              │
 │                                               │  ┌─────────────────────────┐ │
 │  ┌─────────────────────────────────────┐      │  │      Sign contract      │ │
 │  │ Type a message…                  ↵  │      │  └─────────────────────────┘ │
 │  └─────────────────────────────────────┘      │                              │
 └───────────────────────────────────────────────┴──────────────────────────────┘
```

**Time it takes**: 2–3 minutes once you're warmed up.

---

## Moment 2 — Check in (anytime)

**You do**: Glance at the toolbar. Or click the Founder Loop icon for
the full picture. Or open a new tab.

**The app does**: Three different surfaces all show the same data.

- **Browser toolbar badge** — a small number on the icon, the current
  tank %. Color tells you the situation: amber = below threshold,
  green = within ration, red = ration burnt.
- **Browser popup** — click the icon. Tank bar, today's priorities
  with what's done, ration remaining, current diagnosis (if any).
- **System menu bar** — same gauge, but in your OS-level menu bar,
  always visible. Click it for a menu: tank %, run a check-in, show
  contract, quit.
- **New tab page** — every time you open a new tab, you see the full
  dashboard: tank, priorities, last few hours of activity.

You don't have to choose; install both and they show the same thing
in different places. Pick what's least intrusive for you.

**Sketch (browser popup)**:

```
 ┌────────────────────────────────────┐
 │  Founder Loop                ↻ ⚙   │
 ├────────────────────────────────────┤
 │  ████████████░░░░░░░░░░░  60%      │
 │  ration 0/60 min · below threshold │
 │                                    │
 │  ○ ship the report (pr_merged)     │
 │  ○ call my sister (human signoff)  │
 │  ● wrote outline (commit_pushed)   │
 │                                    │
 ├────────────────────────────────────┤
 │  daemon: 127.0.0.1:8765            │
 │  [ Tick now ]  [ ⚙ ]               │
 └────────────────────────────────────┘
```

---

## Moment 3 — When you're tempted

**You do**: Navigate to YouTube (or Twitter/X, Reddit, HN, Instagram,
TikTok, Facebook).

**The app does**: Pops up a card. Names what's likely going on.
Offers concrete alternatives — including, often, ones tailored to you
(the article you bookmarked Tuesday; the friend you haven't messaged
in 3 days; your lighter priority you can switch to).

**Sketch**:

```
 ╔══════════════════════════════════════════════════════════╗
 ║  YESTERDAY-YOU WANTED ME TO ASK:                         ║
 ║                                                          ║
 ║  You're tired.                                           ║
 ║  YouTube simulates rest but doesn't deliver it.          ║
 ║                                                          ║
 ║   sleep_last_night_hours=5.0 < 6.5; the urge is           ║
 ║   fatigue dressed as boredom.                            ║
 ║                                                          ║
 ║  ┌──────────────────────────────────────────────────┐    ║
 ║  │  20 min nap                                      │    ║
 ║  │  20 min · tank +5.0%                             │    ║
 ║  └──────────────────────────────────────────────────┘    ║
 ║  ┌──────────────────────────────────────────────────┐    ║
 ║  │  Switch to lighter priority                      │    ║
 ║  │  25 min · tank +3.0%                             │    ║
 ║  └──────────────────────────────────────────────────┘    ║
 ║  ┌──────────────────────────────────────────────────┐    ║
 ║  │  10 min walk outside                             │    ║
 ║  │  10 min · tank +2.0%                             │    ║
 ║  └──────────────────────────────────────────────────┘    ║
 ║                                                          ║
 ║                          — or —                          ║
 ║                                                          ║
 ║  ┌──────────────────────────────────────────────────┐    ║
 ║  │       Proceed anyway (logged, drains tank)       │    ║
 ║  └──────────────────────────────────────────────────┘    ║
 ║                                                          ║
 ║  Press ESC, click outside, or pick something — your      ║
 ║  call. Nothing is blocked.                               ║
 ╚══════════════════════════════════════════════════════════╝
```

**The app's principles when this fires**:

- It will *never* block you outright. You can always proceed.
- Clicking **Proceed anyway** is a perfectly valid choice. The card
  just makes the cost visible.
- If you click an option, the app starts a timer for it (a nap timer,
  a walk timer) and credits your tank when done.
- After your earned-ration runs out and you reach for another video,
  you'll get a card again that diagnoses what you *actually* still
  need (often: rest, since reward-watching can be tiring).

**No browser? No extension? Log the urge from the terminal.** If
you're working in a non-browser app and feel an urge — or you're on a
machine where you haven't installed the extension — you can tell the
app directly:

```
neuro-os loop urge entertainment --context "I'm bored fighting this bug"
```

The next tick honors it as ground truth (your reported urge always
beats the predictor's guess), runs the same diagnosis, and proposes
the same constructive expression in the next hourly tick or the next
time you open the dashboard.

---

## Moment 4 — Look back

**You do**: Open
[`http://127.0.0.1:8765/review`](http://127.0.0.1:8765/review) in your
browser. The chat page kicks off with today's summary — four numbers:

- **Prediction MAE** — how wrong the brain was about your distraction
  minutes today. Lower over time = the AI is learning you.
- **Contract-honor rate** — what fraction of decisions today went the
  way yesterday-you wanted. Higher = today-you is increasingly willing
  to keep the deal.
- **Entertainment minutes used** — total YouTube/TikTok/etc. time
  consumed (honored OR overridden).
- **Sublimation success rate** — of times the system proposed a
  constructive alternative, what fraction "stuck" (you didn't override
  the contract afterwards).

The AI then walks you through the day: what worked, what didn't, what
to change for tomorrow. Ends with *"Want me to draft tomorrow's
contract?"* — when you say yes, you're back at the morning ritual.

> **Power-user CLI** equivalent (no chat, just the numbers):
> `neuro-os loop nightly`. Same four metrics printed as JSON.

---

## Moment 5 — Tweak the rules

The app keeps three little lists that make Moment-3 cards feel
personal:

- **Bookmarks queue** — articles to read when novelty-hunger fires.
- **Social queue** — people to reach when loneliness fires.
- **Rubber-duck venues** — where to externalize when you're stuck.

**You do**: Open
[`http://127.0.0.1:8765/queues`](http://127.0.0.1:8765/queues) in your
browser. Tell the AI *"three people I've been meaning to reach out
to"* or *"add the Karpathy attention lecture to my bookmarks"* — it
writes the list for you. The side panel re-renders after each turn so
you can see what changed.

> **Power-user fallback**: edit the JSON files in
> `agent/founder_loop/data/queues/` directly if you'd rather. There's
> a sample of each shipped with the app.

---

## Common questions

**Where is "the app" actually running?**
On your laptop. The "server" is just a small program that listens on
your own machine on port 8765. Nothing connects to the internet
unless you set an Anthropic API key for the natural-language path.
Even then, only your *messages to the AI* go to Anthropic; your
contract, your tank, your priorities — those never leave.

**What if I close the terminal that's running it?**
Run `neuro-os autostart install` once and the daemon will come up
on every login (launchd on macOS, systemd-user on Linux, Task
Scheduler on Windows). Reverse with `neuro-os autostart uninstall`.

**Do I have to use Anthropic?**
No. Without an API key, the morning ritual still works — it just asks
you one field at a time instead of conversationally. Worse but not
broken.

**Is my data shared?**
No. Everything lives in `~/.founder_loop/` on your laptop. The
"server" refuses to bind to anything but your own machine
(127.0.0.1).

**I want a phone app.**
Not yet. Roadmap.

---

If you got this far: the next thing to read is
[how it works](./how-it-works.md) (the five-box architecture, light
on jargon).
