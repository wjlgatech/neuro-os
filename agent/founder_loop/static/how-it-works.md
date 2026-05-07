# How it works

You don't need to read this to use the app. This is for people
who want to know what's inside, or who might contribute. Some of it
will sound technical near the end, but the first half should be fine
for anyone curious.

The whole thing is five boxes wired in a loop:

```
                              YESTERDAY-YOU
                                  │
                                  ▼
                          ┌───────────────┐
                          │   CONTRACT    │
                          │  (the deal)   │
                          └───────┬───────┘
                                  │
                                  ▼
   ┌───────────┐    ┌────────┐    ┌──────────────┐    ┌────────┐
   │  SENSORS  │ ─► │ BRAIN  │ ─► │ CARROT/STICK │ ─► │ MEMORY │
   │ (observe) │    │(predict│    │  (policy +   │    │(record │
   │           │    │  + dx) │    │   action)    │    │ + learn)│
   └───────────┘    └────────┘    └──────────────┘    └────┬───┘
                                                           │
                                                           ▼
                                                       TODAY-YOU
                                                     (sees the result)
                                                           │
                                                           ▼
                                                       TOMORROW
                                                  (signs a new contract)
```

Each box, in plain language, then the names of the actual code files.

---

## Box 1 — **Sensors** *(what the app knows about your day)*

Every hour, the app wakes up and reads what you did. Right now it
reads from a workflowx export file — a log of "you spent 35 min on
this, 5 min on that, you switched contexts 4 times." If you don't
have workflowx, the file is empty and the app has no signal; it
guesses based on your past trajectory and asks you for intent.

**Where the app finds workflowx (auto-detect precedence):**

1. An explicit `--workflowx-fixture` flag wins everything.
2. The `WORKFLOWX_EXPORTS_PATH` environment variable (file or
   directory).
3. Platform-specific known directories — first match returns the
   most-recently-modified `.jsonl` inside:
   * macOS: `~/Library/Application Support/workflowx/exports/`,
     `~/.workflowx/exports/`
   * Linux: `~/.config/workflowx/exports/`,
     `~/.local/share/workflowx/exports/`, `~/.workflowx/exports/`
   * Windows: `%APPDATA%\workflowx\exports\`,
     `%LOCALAPPDATA%\workflowx\exports\`
4. Repo-local `./workflowx.jsonl` (dev convenience).
5. Fallback: `~/.founder_loop/workflowx.jsonl` (auto-created empty;
   the loop runs blind unless you log urges manually).

The daemon logs which branch fired at boot, so you always know
whether real signal is flowing. Run `neuro-os loop workflowx-detect`
without starting the daemon to print the result as JSON.

**The other channel is you.** When workflowx is silent (or wrong)
and you feel an urge anyway, you can tell the app directly:

```
neuro-os loop urge entertainment --context "want YouTube"
```

This writes to `~/.founder_loop/founder_events.jsonl` as a
`UrgeEvent`. The next tick reads recent events (15-minute window by
default) and treats your reported urge as **ground truth** — the
predictor's guess is overridden, the diagnosis runs against the
state, and the Sublimation Card surfaces in the dashboard. The
browser extension's "I'm tempted right now" button uses the same
mechanism via `POST /events`.

In the future, sensors include: sleep from your watch, last-meal time,
hours-of-screen-time, time-since-last-message-sent. The more sensors,
the better the diagnoses.

*Code: `agent/founder_loop/observe.py`,
`agent/founder_loop/workflowx_detect.py`,
`agent/founder_loop/urge_log.py`*

---

## Box 2 — **Brain** *(predict + diagnose)*

Two things happen here:

1. **Predict the next hour.** Based on what you just did, what you've
   done over the last 7 days, and what you said you wanted to do —
   how much distraction is incoming? What kind of urge is firing?
   This part runs Claude (an AI) when you have an API key, otherwise
   it falls back to a simple trajectory average.

2. **Diagnose the underlying need.** If an urge is firing, *which* of
   the six is it? Fatigue? Novelty-hunger? Social? Frustration?
   Decision-fatigue? Hunger? The diagnosis isn't from the AI alone;
   there's a small rule-book ("if sleep < 6.5 hours, fatigue") that
   triages, and the AI confirms or overrides.

The brain doesn't *do* anything yet — it just produces a forecast and
a diagnosis.

*Code: `agent/founder_loop/predict.py`, `agent/founder_loop/sublimate.py`*

---

## Box 3 — **Contract** *(yesterday-you's signature)*

The contract is what you signed this morning. It contains:

- Your **priorities** (1–5) — each with a tangible "done" signal.
- Your **entertainment ration** — how much YouTube/etc. you unlock at
  90% completion.
- The **threshold** — usually 90%.
- A few internal knobs that almost no one needs to touch.

The contract is just a JSON file at `~/.founder_loop/contracts.jsonl`
with one line per day. You don't write this by hand; the morning chat
on `/onboard` does.

The app keeps a running **tank score** by reading your activity log
and the contract together: how much progress have you made on the
priorities (credits)? How much have you done that drains the tank
(debits, like overriding a sublimation card)? The tank is a function
of these two, capped at 100%.

*Code: `agent/founder_loop/contract.py`,
`agent/founder_loop/priorities.py`,
`agent/founder_loop/reward_ledger.py`*

---

## Box 4 — **Carrot / Stick** *(what to do about the urge)*

This is where the brain meets the contract. The decision tree, in
plain language:

```
Is an urge firing? ──► No  ──► continue (do nothing)
                  └─► Yes ─┐
                           ▼
        Is the tank ≥ 90% ?
        ├─ Yes, within ration ──► UNLOCK ENTERTAINMENT (with timer)
        ├─ Yes, ration done   ──► gentle nudge, re-diagnose what's left
        └─ No                  ──► PROPOSE CONSTRUCTIVE EXPRESSION
                                   (the Sublimation Card)
```

Crucially, the carrot/stick layer **never blocks**. The "stick" is
that override-anyway costs tank-credits. You always retain agency.

*Code: `agent/founder_loop/policy.py`, `agent/founder_loop/act.py`*

---

## Box 5 — **Memory** *(records and learns)*

Every tick (every hour, or when you visit a distraction site) writes a
line to `~/.founder_loop/registry.jsonl`. Each line has the state, the
prediction, the action, whether the contract was honored, and the
delta to the tank.

At the end of the day, the **nightly summary** reads the whole day and
computes four numbers:

- **MAE** — Mean Absolute Error between what the brain predicted and
  what you actually did. Lower over time = the AI is learning you.
- **Contract-honor rate** — what fraction of decisions today went the
  way yesterday-you wanted. Higher over time = today-you is
  increasingly willing to keep the deal.
- **Entertainment minutes used** — total entertainment time consumed
  today (honored unlocks AND overrides combined).
- **Sublimation success rate** — of times the system proposed a
  constructive alternative, what fraction "stuck" — i.e. you didn't
  override the contract afterwards. The signal that says whether the
  philosophy is actually working.

The summary also surfaces **goldens failed** — pre-defined "the system
is broken if X" rules. Triggers a rebuild of either the predictor
prompt or the sublimation catalog when ≥2 fire in a 7-day window.

You see all four numbers in the `/review` chat page kickoff, and the
same numbers via `neuro-os loop nightly` in the terminal.

*Code: `agent/founder_loop/memory.py`,
`agent/founder_loop/golden_cases.py`*

---

## How it learns over time

The system has three feedback loops:

1. **Daily** — the predictor's prompt-cache hits accumulate; cheap
   improvements just by you being a recurring user.
2. **Weekly** — when goldens fail, the nightly summary suggests
   rewriting the predictor prompt or the sublimation catalog. v0
   surfaces this as a recommendation; v1 will apply it automatically
   under flywheel's L2 self-modification machinery.
3. **Per-session** — the chat onboarding adapts to your phrasing
   inside a single conversation (e.g. you say "PR" the first time
   and "pull request" the third; Claude handles both).

The L2 self-modification is the deepest part of the loop and the part
most under construction. See `docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md`
for the laws governing it.

---

## How the UIs fit in

Three UI surfaces, all talking to the same local server:

```
       Browser extension                  System tray app                  Chat surfaces
  ┌──────────────────────┐         ┌──────────────────────┐         ┌──────────────────────┐
  │  Toolbar badge       │         │  Menu bar gauge      │         │  /onboard (morning)  │
  │  Popup dashboard     │         │  Always-visible      │         │  /review  (nightly)  │
  │  New tab dashboard   │         │  Quick actions       │         │  /queues  (curate)   │
  │  Sublimation overlay │         │                      │         │                      │
  └──────────┬───────────┘         └──────────┬───────────┘         └──────────┬───────────┘
             │                                │                                │
             │  HTTP                          │  HTTP                          │  HTTP
             │                                │                                │
             ▼                                ▼                                ▼
                          ┌───────────────────────────────────────┐
                          │   Local daemon  127.0.0.1:8765        │
                          │   (refuses non-loopback bind)         │
                          │                                       │
                          │   GET /tank, /contract, /today        │
                          │   GET /tick                           │
                          │   POST /chat, /sign, /diagnose        │
                          │   POST /events                        │
                          └─────────────────┬─────────────────────┘
                                            │
                                            ▼
                                ┌─────────────────────────┐
                                │     The five boxes      │
                                │  (Python; one process)  │
                                └─────────────────────────┘
```

The daemon is one Python process. The UIs are dumb clients; everything
load-bearing is in the engine. This means:

- You can build a phone app, a Discord bot, an Apple Watch
  complication — they all just talk HTTP to the same daemon.
- If you replace the daemon with a hosted service (you wouldn't —
  privacy), the UIs don't change.
- If you replace the UIs with a single CLI, the engine doesn't change.

---

## What's special about this design

Three things, none of which are revolutionary alone, but the
combination is the actual product:

1. **The control loop is closed against a contract you signed.** Most
   productivity tools have a "rule"; this one has a "contract." The
   former is external; the latter is your own promise to yourself.
2. **The action layer prefers proposing alternatives over blocking.**
   Most habit apps treat distraction as the problem to suppress; this
   one treats distraction as a misaimed legitimate desire and tries to
   route the desire to a constructive expression.
3. **The whole thing runs on your laptop and is auditable.** Every
   decision, every override, every diagnosis is one line in a JSONL
   file you own. You can read it. You can delete it. No vendor sees
   it.

---

## What's still being built

See [the roadmap](./roadmap.md) for the honest list of what works
today vs. what's coming.

Anything missing here? Open an issue. The five-box diagram is the
mental model we want to keep clean even as features grow underneath
it; if a future feature doesn't fit one of the five boxes, we should
question whether it belongs.
