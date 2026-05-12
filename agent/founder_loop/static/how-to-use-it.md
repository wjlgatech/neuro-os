# How to use it

Neuro-OS ships **four verticals** — Founder Loop, Research, Investment
(advisory-only), Startup. They share one substrate (typed daily
contract, tank that scores progress, drift card at the moment of
temptation, nightly summary) but use different vocabulary for
different lives. See [what is this](./what-is-this.md) if you haven't
yet.

You don't have to pick one — they coexist on your machine in their own
private stores. But it helps to start with one and add others later.

| If your day looks like… | Start with | Surface |
|---|---|---|
| Coding/shipping; your problem is YouTube/Twitter/distraction | **Founder Loop** | Browser + chat + system menu bar |
| Reading papers; your problem is bookmarking 30, reading 2 | **Research** | CLI today; chat surface roadmapped |
| Holding positions; your problem is FOMO/narrative-following | **Investment** *(advisory-only)* | CLI today |
| Building a company; your problem is pivoting every Thursday | **Startup** | CLI today |

The rest of this doc walks **Founder Loop's 5 moments** (browser-first,
the most polished surface) then **the CLI tour for the other three**.

Honest note: the system is alpha. Founder Loop is the most polished
surface; the other three ship today as CLI flows that exercise the
same substrate. Browser/chat surfaces for them are roadmapped — see
[`./roadmap.md`](./roadmap.md).

---

## First — get it running on your computer

Today this is **two steps**, not one click. We're working on a real
installer; for now:

```
pip install neuro-os
neuro-os start
```

The `start` command does four things in the background:
- Creates the per-vertical home dirs as you opt in
  (`~/.founder_loop/`, `~/.neuro_os_research/`, etc.). Founder Loop
  is created on first start; the other verticals create theirs on
  their first `onboard` run.
- Boots a small server on `127.0.0.1:8765` for Founder Loop (only
  your machine can reach it; nothing leaves your computer).
- **Auto-detects your workflowx export** if it exists (macOS
  Application Support, Linux `~/.config`, etc.) — see
  [Box 1 in how-it-works](./how-it-works.md) for the full precedence.
  Logs the detected path so you know whether real signal is flowing.
- Opens [`http://127.0.0.1:8765/onboard`](http://127.0.0.1:8765/onboard)
  in your default browser.

From here on, for Founder Loop you mostly won't touch the terminal.
The other three verticals are CLI-only in v0.

> **Want it to start when you log in?** Run
> `neuro-os autostart install` once. That writes a launchd plist
> (macOS), a systemd-user service (Linux), or a Task Scheduler XML
> (Windows). `--dry-run` previews what would be written. Reverse with
> `neuro-os autostart uninstall`.

> **One-click installer (`.dmg` / `.exe` / `.AppImage`)** is on the
> roadmap if even `pip install` feels like too much.

---

# Founder Loop — the 5 moments

The browser-first product. Five moments cover everything the user
does day-to-day.

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

**Sketch (browser toolbar badge)**:

```
   ┌─────────────────────────────────────────────────┐
   │  ✻  ★  ⚐  [ FL 60 ]  ☰  • Tab 1 │ Tab 2 │ ...  │
   └─────────────────────────────────────────────────┘
                       ▲
                       │
            tank% on the action icon's badge
            color: amber (<90) / green (≥90, unspent ration) / red (ration burnt)
```

**Sketch (system tray gauge — macOS menu bar shown; same shape on Linux / Windows)**:

```
   ─────────────────────────────────────────────────────
                                          🔋  📶  ☀️  ●60%  🔍  ⏰  Mon 3:42
                                                  ▲
                                                  │
                                          tank gauge in the menu bar
                                          (click for: tick now / show contract / quit)
```

**Sketch (browser new-tab dashboard — replaces Chrome's default new-tab)**:

```
 ╔══════════════════════════════════════════════════════════════════════╗
 ║                                                                      ║
 ║   morning, paul · monday may 11 · 9:14am                              ║
 ║                                                                      ║
 ║   ████████████░░░░░░░░░░░░░░░░  60%   below threshold                ║
 ║   ration: 0 / 60 min · entertainment locked                          ║
 ║                                                                      ║
 ║   today's contract                                                   ║
 ║   ● ship the report                          (pr_merged)             ║
 ║   ○ call my sister                           (human_signoff)         ║
 ║   ● wrote outline                            (commit_pushed) ✓       ║
 ║                                                                      ║
 ║   last 4 hours                                                       ║
 ║   08:13 · tick · continue · honored=true                             ║
 ║   09:14 · urge.entertainment · "checking twitter" · diagnosing…      ║
 ║                                                                      ║
 ╚══════════════════════════════════════════════════════════════════════╝
```

For the full Manifest V3 wiring (host permissions, badge polling cadence, content-script injection rules, sublimation-card mount) see [`ui/browser_extension/README.md`](../ui/browser_extension/README.md). For the cross-platform tray gauge, see [`ui/tray_app/README.md`](../ui/tray_app/README.md).

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

**If your urge is an *override* of the system's last suggestion, say so**: add `--override-of <drift_mode>` and the urge log AND a skillify `OverrideEvent` get written in one command. Without this flag the catalog-evolution loop (Lane 2) never sees evidence of which constructive expressions don't work for you. With it, after ≥5 same-mode overrides, `skillify extract` proposes a new candidate `ConstructiveExpression` for `/catalog-review`.

```bash
# you wrote a 1-page brief instead of the proposed mechanism-card extraction:
neuro-os loop urge novelty \
    --context "wrote a 1-page brief instead" \
    --override-of paper_collector \
    --override-vertical research
```

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

## Daily anchors — faith and relational pillars

Two pillars in many people's days don't fit "drift modes": faith / spiritual practice, and the close relational ties (spouse, family, close friends). Neuro-OS doesn't try to instrument them — but it provides a tiny typed log so you can SEE the streak:

```bash
# Morning prayer / walk / weekly worship — whenever it happens:
neuro-os loop anchor --kind faith \
    --context "5:50am prayer + walk + plan done"

# Meaningful relational moment:
neuro-os loop anchor --kind relational \
    --context "Taylor: cooked dinner together, talked about week"
```

Each call writes one row to `~/.founder_loop/anchors.jsonl` (append-only, frozen Pydantic). The dashboard renders these as `faith: 5/7 days hit; relational: 4/7 days hit` over the window — same-day multiple entries count as ONE day-hit. You don't have to use this; the rest of the system works without it. But if these pillars matter to you and you'd otherwise journal them by hand, this gives you a streak number and nothing more.

---

## Skillify — make the system learn what works for you

When the system proposes a constructive expression for a drift mode and you do something else, `loop urge --override-of <mode>` (above) records that override. After enough overrides on the same drift mode, `skillify` proposes a new constructive expression candidate for catalog review:

```bash
# Aggregate overrides into SkillProposals (default ≥5 on the same drift mode within 30d):
neuro-os skillify extract --vertical research --threshold 5 --window-days 30

# Review pending proposals:
neuro-os skillify review --cli
```

Accepting a `SkillProposal` moves the file from `pending/` to `accepted/` — **it does NOT auto-mutate the catalog** (Law 7 honored). The catalog change is a separate human-authored commit; the proposal file is just evidence saying "this pattern fired N times; you may want to fold it in."

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

# The other three — CLI tour

Research, Investment, and Startup ship today as CLI flows. They use
the same three-step daily shape — **onboard** (sign the day's
contract), **tick** (run a single observation/diagnosis cycle, often
triggered by a drift), **nightly** (4-metric rollup). The data lives
under `~/.neuro_os_<vertical>/` and never leaves your machine.

By default each vertical's data is **private to that vertical** — your
investment positions don't show up in research; your research
mechanism cards don't reach investment unless you explicitly opt in
per note. See [how it works](./how-it-works.md) for the privacy model.

## Research — for a researcher building a world model

**Ingest** (Sunday night setup, ~5 min). Drop the week's reading into one folder, then:

```bash
# Native Python extractor — works without gbrain. Supports .txt/.md/.pdf.
neuro-os research ingest --prefer local --source-dir ~/reading/

# OR if you have garrytan/gbrain installed:
gbrain export > ~/reading/export.json
neuro-os research ingest --prefer gbrain --export-file ~/reading/export.json

# Auto-detect (default): prefers gbrain when present, falls back to local.
neuro-os research ingest --source-dir ~/reading/
```

Each source produces 0-5 `MechanismCardProposal`s. Then review them:

```bash
neuro-os research review --cli
```

A REPL: shows each pending proposal with its `mechanism / invariant / prediction / failure_mode` fields and the source excerpt. You type `a`/`r`/`s`/`q` to accept / reject / skip / quit. On accept it asks for **entity slugs** — comma-separated kebab tags like `nvda, moats, network-effects` — that get propagated into the cross-vertical entity graph.

If you have no API key (`ANTHROPIC_API_KEY` unset) or want zero LLM cost, add `--no-llm`. The extractor falls back to a regex heuristic and emits low-confidence proposals.

**Onboard** (every morning, ~2 min). Write today's priorities into a
JSON file:

```json
[
  {
    "title": "extract one mechanism card from Karpathy attention lecture",
    "evidence_type": "mechanism_card_filed",
    "evidence_target": "thesis-001",
    "weight": 3
  }
]
```

Then sign:

```bash
neuro-os research onboard \
    --priorities-file priorities.json \
    --active-thesis-id thesis-001 \
    --budget 1 \
    --threshold 90
```

`--budget 1` is the day's primary resource: at most ONE paper today.
This is the heart of research's anti-firehose policy.

**Tick** (when drift fires — you catch yourself bookmarking instead
of extracting):

```bash
neuro-os research tick --drift paper_collector
```

Substrate names the drift (one of: `paper_collector`, `topic_hopper`,
`memorizer`, `authority_acceptor`, `overloaded`, `forgetting`),
proposes a constructive expression (e.g. *"extract one MechanismCard
now (20 min)"*), and credits the tank when you do it.

**Dashboard** (every morning + every evening, ~10 sec):

```bash
neuro-os research dashboard --window 7      # default text rendering
neuro-os research dashboard --window 7 --json   # machine-readable
```

Prints a one-screen rollup. Real output against the 40-day fixture:

```
research vertical — 40-day dashboard (generated 2026-05-09 18:59:54 UTC)
======================================================================

Compound curve
  mechanism cards/day       today=0.0   7d-avg=0.00   40d-avg=0.00   trend=flat

Drift-mode usage (top 3)
  paper_collector        ████████████████████████  18
  topic_hopper           ██████████  8
  authority_acceptor     █████  4
  (overloaded / forgetting fired 0 times — catalog candidates?)

Constructive expressions
  offered:  31   accepted:  31   stuck:  7   stick-rate=23%

Lane 1 ingestion
  sources scanned:    80     proposals emitted:  14
  accepted:           0     rejected:           0     pending:  0

Action queue
  (no pending proposals)
```

The lines that matter most:
- **Compound curve trend** — `up` / `flat` / `down` with 5% hysteresis. The headline question of the 40-day trial: are mechanism-cards-per-day trending up?
- **`overloaded / forgetting fired 0 times — catalog candidates?`** — drift modes the catalog claims exist but never fired. The single most diagnostic line for whether the catalog is calibrated to your real day.
- **`stick-rate=23%`** — of the constructive expressions the system proposed, what fraction "stuck" (no later same-mode-different-CE override). Low stick-rate means the catalog is wrong; the next move is `skillify extract`.
- **Action queue** — pending proposals + oldest age in hours. If there's an unreviewed backlog, the dashboard nudges you to run `research review --cli`.

**Cross-vertical share** (when a mechanism card is relevant to your investment vertical):

```bash
# Find the cross-vertical note id for the accepted card:
neuro-os cross-vertical query --reader research --kind mechanism_card

# Share it with investment:
neuro-os cross-vertical share-note --note-id <id> --with investment
```

The investment vertical can now read that mechanism card. Default is private to research; the share is explicit and audit-trailed.

**Three-Layer Research OS** (weekly, ~5 min):

Layer 1 (extraction) is the per-paper ingest above. Two more layers
turn accumulated cards into decision-grade output.

*Optional one-time setup — your framework.* Tell the system what
axes you read papers against. The substrate doesn't interpret these;
it just preserves them across the pipeline. Hand-edit
`~/.neuro_os_research/framework.json`:

```json
{
  "name": "OEC",
  "description": "Observation -> Evaluation -> Control -> Continual",
  "axes": [
    {"name": "Observation", "description": "What sensors / signals?"},
    {"name": "Evaluation",  "description": "What delta is detected?"},
    {"name": "Control",     "description": "What action is taken?"},
    {"name": "Continual",   "description": "What is learned over time?"}
  ]
}
```

The framework is **fully generic** — a value investor uses
{Moat, Distribution, Unit economics}; a founder uses
{deep-work block, recovery ritual}; the substrate doesn't care. If
the file is missing, framework-aware features are simply skipped.

*Layer 2 — synthesize* (cluster cards by mechanism, not topic):

```bash
neuro-os research synthesize --window 30 --min-cluster-size 2
```

Reads accepted MechanismCards in the window, clusters them by their
underlying causal mechanism (so the regularization paper in CL and
the regularization paper in econ end up in the same cluster), and
writes a `SynthesisRun` to `~/.neuro_os_research/synthesis/runs/`.
With `ANTHROPIC_API_KEY` it uses an LLM clusterer; without, falls
back to a heuristic Jaccard clusterer (less rich but works offline).

> Implementation note: this v0 module mirrors the Plan A pattern in
> `agent/research/ingest_router.py`. Future PR replaces it with a
> graphify adapter — graphify (your separate project) is the right
> long-term backend for graph-shaped synthesis.

*Layer 3 — generate a decision-ready brief.* Author a `ProjectContext`
JSON file naming the project + 1-5 current questions + optional
collaborators + optional pending decisions, then:

```bash
neuro-os research brief --cluster-id <cluster_id> --context-file ./context.json
```

Output: a markdown brief printed to stdout + saved to
`~/.neuro_os_research/briefs/<brief_id>.md`. Contains:
- **What this means for the project** (2-5 implications)
- **Next decisions** unlocked by the cluster
- **Next experiments** that would falsify the cluster's applicability
- **Questions for collaborators** — phrased to surface their
  load-bearing assumption

Sample `context.json`:

```json
{
  "project_name": "myProject",
  "current_questions": [
    "How do we add capability without regressing prior behavior?"
  ],
  "collaborators": ["Alex", "Sam"],
  "pending_decisions": ["ship feature X this week?"],
  "framework_name": "OEC"
}
```

**Stop-condition checkpoint** (after each Layer 3 brief, ~30 sec):

```bash
neuro-os research checkpoint --brief-produced yes --clearer yes --note "..."
```

Two binary signals: did the cycle produce a brief? did your mental
model on the active thesis get clearer? Both YES → the system is
working, keep adding inputs. Either NO twice in a row → dashboard
prints `system_not_converting`. *Redesign before adding more inputs,
not after.* This is the falsifiability gate the Research OS uses on
itself.

**Dashboard health flags** (read after the rollup):

The dashboard's new "Three-Layer Research OS" section surfaces
`system_health_flags`:

- `chaser_mode` — ≥5 accepted, >70% frontier-tier, <10% seed-tier.
  Reading only the recent edge; missing the foundational anchors.
- `hoarder_mode` — oldest pending proposal > 14 days. The 2-week
  inbox rule from the source pipeline; if a paper isn't worth
  processing in 2 weeks, it wasn't worth saving.
- `rubber_stamping` — ≥5 rated cards, zero `skip` + zero `misleading`.
  Every paper rated foundational/useful is suspicious; the verdict
  vocabulary exists so honest "skip" rates matter.
- `no_synthesis` — ≥5 accepted, zero briefs in window. Have data,
  not synthesizing.
- `system_not_converging` — ≥2 consecutive non-converging checkpoints.

Flags fire ONLY when evidence is unambiguous (sample-size guards
make small-corpus days flag-free).

**Nightly** (~30 sec rollup):

```bash
neuro-os research nightly
```

Prints the 4-metric summary as JSON:
- mechanism cards filed today
- continuity score (how many of the last 40 days have stayed on
  the active thesis)
- prediction-log entries
- assumption-map updates

## Investment — for the epistemically calibrated investor

⚠️ **Advisory-only.** No broker integration. No trade execution. The
app logs theses, scores them, surfaces bias warnings. *You read; you
decide.*

**Onboard** — a position is a Pydantic `InvestmentPriority` with
ticker, thesis text, supporting evidence, an explicit invalidation
condition, an expected timeline, and a confidence level:

```json
[
  {
    "title": "AAPL: services revenue compounds at 15%+ through 2027",
    "ticker": "AAPL",
    "thesis_text": "Services attach rate keeps rising as devices age in field; revenue pure software-margin.",
    "invalidation_condition": "services growth drops below 8% for 2 consecutive quarters",
    "expected_timeline": "12-24 months",
    "confidence": "medium",
    "evidence_type": "thesis_documented",
    "evidence_target": "AAPL",
    "weight": 2
  }
]
```

```bash
neuro-os invest onboard \
    --priorities-file positions.json \
    --budget 2 \
    --threshold 90
```

`--budget 2` caps today at 2 position-edits. Keeps the day from
becoming a portfolio churn session.

**Tick** (when you catch yourself FOMO-ing or refreshing the chart):

```bash
neuro-os invest tick --drift emotional
```

Substrate names the drift (one of: `emotional`, `narrative_following`,
`price_obsessed`, `overconfident`, `social_proof_following`,
`ego_attached`), runs a Belief OS bias check on the position thesis,
and proposes a calibrating action (e.g. *"file the thesis BEFORE
acting; defer 24h"*).

**Nightly**:

```bash
neuro-os invest nightly
```

Prints: calibration error (over time, how well stated confidence
matches survival rate), thesis-survival rate, bias-detection rate,
decision consistency.

## Startup — for a founder building a startup

**Onboard** — you commit to ONE load-bearing hypothesis for 40 days.
Changing the active hypothesis is allowed but **expensive** —
`thesis_pivots/day` is hard-capped at 1, and the abuse-tax bites at
3+ kills in 40 days.

```json
[
  {
    "title": "capture 3 audience signals from this week's launch replies",
    "evidence_type": "audience_signal_logged",
    "evidence_target": "hyp-001",
    "weight": 3
  }
]
```

```bash
neuro-os startup onboard \
    --priorities-file priorities.json \
    --active-hypothesis-id hyp-001 \
    --budget 1 \
    --threshold 90
```

**Tick** (when drift fires — a new "what if we…" idea pulls at you):

```bash
neuro-os startup tick --drift idea_chaos
```

Substrate names the drift (one of: `idea_chaos`, `broadcasting`,
`feature_creep`, `vision_intoxicated`, `vanity_metrics`,
`random_execution`), proposes a constructive expression (e.g.
*"park the new idea; reaffirm the active hypothesis aloud"*).

**Nightly**:

```bash
neuro-os startup nightly
```

Prints: strategic continuity score (`1 - kill_count/40`), trust
density (fraction of audience members who engaged twice or more),
audience-signals captured, conversion quality.

---

## Easily confused steps

The places real users get stuck. If you hit one of these, this is the disambiguation.

### 1. `--prefer auto` vs `--prefer local` vs `--prefer gbrain` vs `--from-gbrain` (research ingest)

| You want… | Use | Notes |
|---|---|---|
| Just ingest, you don't care how | (omit `--prefer`) — defaults to `auto` | Probes `gbrain --version` (1-sec timeout). Falls back to `local` if absent. |
| Force the native Python extractor (`.txt`/`.md`/`.pdf`) | `--prefer local --source-dir <dir>` | Always works. No external runtime. Anthropic API key is optional (heuristic fallback). |
| Force gbrain (you have it installed) | `--prefer gbrain --export-file <path>` OR `--from-gbrain --export-file <path>` (alias) | Requires `gbrain` on PATH AND a JSON export. Live MCP wiring is roadmapped. |
| You're on Paul's no-gbrain machine | `--prefer local` | The whole point of PR-1. |

The flag pair you almost always want: `--prefer local --source-dir ~/reading/`. Everything else is opt-in.

### 2. `--override-of` ALWAYS pairs with `--override-vertical`

```bash
# WRONG — defaults to founder_loop, but the drift mode is from research:
neuro-os loop urge novelty --override-of paper_collector
#  → emits OverrideEvent(vertical="founder_loop", drift_mode="paper_collector")
#  → wrong vertical; skillify clusters it under founder_loop

# RIGHT:
neuro-os loop urge novelty --override-of paper_collector --override-vertical research
#  → emits OverrideEvent(vertical="research", drift_mode="paper_collector")
```

If you're overriding a research/invest/startup drift mode, ALWAYS pass `--override-vertical`. The flag defaults to `founder_loop` for founder-loop overrides only.

### 3. Where each vertical's home dir lives

| Vertical | Home dir | What's in it |
|---|---|---|
| Founder Loop | `~/.founder_loop/` | `registry.jsonl`, `contracts.jsonl`, `founder_events.jsonl`, `anchors.jsonl` (faith/relational), `data/queues/*` |
| Research | `~/.neuro_os_research/` | `registry.jsonl`, `mechanism_cards/*.json`, `proposals/{pending,accepted,rejected}/*.json`, `ingestion_runs.jsonl` |
| Investment | `~/.neuro_os_invest/` | `registry.jsonl`, `position_theses/*.json`, `bias_checks/*.json`, `cross_modal_evals/*.json` |
| Startup | `~/.neuro_os_startup/` | `registry.jsonl`, `hypotheses/*.json`, `audience_signals/*.json`, etc. |
| Cross-vertical store | `~/.neuro_os/cross_vertical.jsonl` | The shared append-only JSONL for `VerticalNote` + `Entity` rows |
| Skillify | `~/.neuro_os_skillified/` | `events.jsonl` (override events), `proposals/{pending,accepted,rejected}/*.json` |

**`loop anchor --home <path>`** defaults to `~/.founder_loop/`, NOT `~/.neuro_os_research/`. Anchors are a founder-loop concept (the daily ritual happens there).

### 4. Cross-vertical share is a TWO-step flow

```bash
# Step 1 — find the cross-vertical note id (NOT the MechanismCard id):
neuro-os cross-vertical query --reader research --kind mechanism_card

# Step 2 — share that note id with another vertical:
neuro-os cross-vertical share-note --note-id <id-from-step-1> --with investment
```

The MechanismCard's local `id` (in `~/.neuro_os_research/mechanism_cards/<id>.json`) is NOT the same as the cross-vertical note `id` (in `~/.neuro_os/cross_vertical.jsonl`). Always go through `cross-vertical query` to look up the right one.

### 5. Skillify won't propose anything until you have ≥5 same-mode overrides

Default threshold is 5. With fewer overrides on the same `(vertical, drift_mode)` bucket, `skillify extract` returns `[]` — that's correct, not a bug. Lower the threshold for testing:

```bash
neuro-os skillify extract --vertical research --threshold 2
```

But `--threshold 2` is too noisy for production catalog evolution. Stick with the default 5 once you're past the demo phase.

### 6. Already-proposed buckets are silently skipped on the second `extract`

If you ran `skillify extract` on Monday and got 1 SkillProposal (still pending or accepted), running it again on Tuesday with the same evidence returns `[]`. That's correct — the bucket already has a proposal in flight; running extract again would create a duplicate. To force re-proposal:

```bash
neuro-os skillify extract --no-skip-existing
```

Rejected proposals do NOT block re-proposal — the assumption is that if you rejected the first candidate, the next batch of override evidence might surface a better one.

### 7. The dashboard's `--window N` defaults to 40, not 7

```bash
# Today's view across the 40-day trial (default):
neuro-os research dashboard

# This week only:
neuro-os research dashboard --window 7

# Last day:
neuro-os research dashboard --window 1
```

If counts look smaller than you expected, check the window flag.

---

## Common questions

**Where is "the app" actually running?**
On your laptop. The "server" is just a small program that listens on
your own machine on port 8765 (Founder Loop browser surface). The
other three verticals are CLI-only — no server. Nothing connects to
the internet unless you set an Anthropic API key for the
natural-language path. Even then, only your *messages to the AI* go
to Anthropic; your contracts, your tank, your priorities — those
never leave.

**What if I close the terminal that's running it?**
Run `neuro-os autostart install` once and the daemon will come up
on every login (launchd on macOS, systemd-user on Linux, Task
Scheduler on Windows). Reverse with `neuro-os autostart uninstall`.

**Do I have to use Anthropic?**
No. Without an API key, the morning ritual still works — it just asks
you one field at a time instead of conversationally. Worse but not
broken. The CLI verticals (research/invest/startup) read priorities
from JSON files and don't require the API at all.

**Is my data shared between verticals?**
No, by default. Each vertical has its own private store
(`~/.founder_loop/`, `~/.neuro_os_research/`,
`~/.neuro_os_invest/`, `~/.neuro_os_startup/`). Cross-vertical reads
require explicit per-note opt-in. The privacy boundary is enforced in
`agent/cross_vertical.py` and tested in CI — see
[how it works](./how-it-works.md).

**Is my data shared with anyone else?**
No. Everything lives on your laptop. The "server" refuses to bind to
anything but your own machine (127.0.0.1).

**I want a phone app.**
Not yet. Roadmap.

**I want chat surfaces for research / invest / startup, not CLI.**
Roadmapped. The CLI is the v0 surface; the substrate is shared, so
the chat surface lifts to all four verticals once Founder Loop's
chat experience is judged finished.

---

If you got this far: the next thing to read is
[how it works](./how-it-works.md) (the substrate + four-vertical
architecture, light on jargon).
