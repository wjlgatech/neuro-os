# What is this?

**Neuro-OS** is one platform with **four daily-ritual products** for four different audiences. Each product is the same shape — a typed daily contract, a tank that scores progress, a "drift card" that names what's really going on when you're about to abandon the contract — but with different vocabulary for different lives.

| The product | For | What kind of contract | What "drift" looks like |
|---|---|---|---|
| **Founder Loop** | A solo founder fighting distraction | "Ship the PR; call my sister; 2 deep-work blocks" | YouTube urge at 3pm |
| **Research** | A researcher building a world-model from papers | "Extract one mechanism card today; tied to my active thesis" | Bookmarking 10 papers, reading 0 |
| **Investment** *(advisory-only)* | An investor making epistemically calibrated decisions | "Document the AAPL thesis with falsification condition; check for survivorship bias" | Trading on a story instead of a mechanism |
| **Startup** | A founder building a startup | "Capture 3 audience signals; identify this week's bottleneck; stay on the active hypothesis" | Pivoting to a shiny new idea every Thursday |

The same machine, four lives. You pick the one(s) you want; they share the system but stay in their own boundaries. (Investment positions don't leak to Startup. Research notes can be explicitly shared with Investment for cross-domain mechanism transfer, but only when you say so.)

The rest of this doc walks through the metaphor stack with **Founder Loop** as the worked example, then closes with what the other three look like.

---

# Founder Loop — the canonical example

**Founder Loop** is an app that helps you keep promises to yourself.

You know how you wake up planning to ship something today, and at 3pm
you find yourself watching YouTube, and you don't even remember
deciding to? This app is built around a simple idea: that's not a
willpower problem. It's a *plumbing* problem. The version of you
who's tired and tempted at 3pm is a different person than the
deliberate, rested version of you who set the goals at 9am. So the app
helps morning-you write a contract that afternoon-you is bound by — but
in a way that's kind, not punishing.

Here's the metaphor stack the whole thing runs on. **The other three
products use the same metaphor stack with their own vocabulary** — see
the per-product sections below.

## The deal with tomorrow-you

Every morning you spend two minutes telling the app what matters today,
in plain English. Things like:

> *I want to ship the report. I want to call my sister. I want to do
> two solid blocks of work on the database thing.*

The app, talking back like a friendly assistant, asks the questions
that turn each of these into something concrete: *how will we know it's
done? Is it must-do or nice-to-have?* When you've finished, it shows
you the contract and you click **Sign**. You've now made a deal with
the version of you who'll exist later today.

## The score

The app keeps a score for you, called the **tank**. It's a number
between 0% and 100%. As you finish things on your contract, the tank
fills up. As you waste time on things you didn't sign up for, the tank
drains a little. You don't have to look at the score; the app shows it
to you in three places — a tiny number on your browser toolbar, a
gauge in your menu bar, and a bar on every new tab you open.

## The reward

Here's the part that makes this different from every other
productivity app: **entertainment is good, when it's earned.** When
your tank hits 90%, the app unlocks however much YouTube / Twitter /
gaming time you set aside for yourself that morning. Default is 60
minutes. The timer runs; when it runs out, the app gently checks in.

Below 90%, the app doesn't *block* anything. You can still go to
YouTube. But:

## When you're tempted, the app shows you what you actually want

This is the heart of the whole thing.

When you go to YouTube at 3pm and your tank is at 60%, the app pops up
a small window. Not a nag. A window that names what's actually
happening:

> *You're tired. YouTube simulates rest but doesn't deliver it. Real
> rest options: 20-minute nap (tank +5%), or switch to your lighter
> task for 25 minutes, or 10-minute walk outside.*

You can pick one of those, or you can click **Proceed anyway**. The
"proceed anyway" button is always there, and clicking it is fine — it
just gets logged, and the tank drains a bit faster than usual.

The app distinguishes six "underlying needs" that distraction is
usually a stand-in for:

| When the urge fires, the real thing you want is often… | …and the app suggests… |
|---|---|
| Rest (you're tired) | A 20-minute nap, or switch to the lighter task |
| Novelty (the work is grindy) | A 10-minute deep-read of something you bookmarked |
| Connection (you've been alone) | A 5-minute voice message to one of three people |
| Escape from a stuck problem | A 10-minute walk + voice memo to externalize it |
| Decision-fatigue | Pick one small thing for 25 min, defer the rest |
| Hunger / eye-strain (your body) | Eat first, then re-decide |

The app isn't always right. When it's wrong, you click "Proceed
anyway" and that gets recorded too. Over time, the app learns your
patterns and gets less wrong.

## The memory

At the end of each day, the app shows you a one-page summary: what
got done, what didn't, where the tank ended up, what diagnoses fired,
what you accepted, what you proceeded-anyway through. Then it asks if
you want to plan tomorrow.

That's it. That's the whole product.

---

# The other three products

**Same machine.** The morning ritual, the tank, the drift-card-at-the-moment-of-temptation, the nightly summary — all four products work this way. What changes is the **vocabulary** (what counts as a priority, what "the tank" measures, what counts as "drift") and the **6 named drift modes** the app diagnoses when you're about to abandon the contract.

Each product also lives in its own **private store** by default. Your investment positions don't show up in the research view. Your startup confidentials don't show up in the investment view. You explicitly opt into sharing per-note (e.g. researcher: "send this mechanism card to investment so I can stress-test the thesis").

## Research — for a researcher building a world model

**The deal:** every morning you commit to reading **at most one paper today**, tied to a single load-bearing thesis you've signed up to refine for 40 days. (No more bookmarking 30 papers and reading 2.)

**The score:** the **mechanism cards/day** count and the **continuity score** (how many of the last 40 days have you stayed on the same thesis).

**The drift card:** when you find yourself bookmarking instead of extracting, or jumping to a new topic, or memorizing terms without predicting consequences, the system names which of the **6 research drift modes** you're in:

| Drift mode | What it looks like | What the app suggests |
|---|---|---|
| Paper-collector | Bookmarking without extracting | Extract one MechanismCard now (20 min) |
| Topic-hopper | Jumping off your active thesis | Bind today's reading back to the thesis (5 min) |
| Memorizer | Reciting terms without prediction | File a PredictionLog (10 min) |
| Authority-acceptor | Taking the paper at face value | Build an AssumptionMap (15 min) |
| Overloaded | Feed is firehose, signal is dead | Triage; cap at 1 paper today |
| Forgetting | Concepts evaporate | Re-paraphrase 3 random cards from memory |

**The reward:** there isn't a "ration unlock" for research the way YouTube minutes is for founder loop — the reward is the visible compounding of MechanismCards in your private store and the rising continuity score.

**Try it now:** `neuro-os research onboard --priorities-file priorities.json --active-thesis-id thesis-001` (see [how to use it](./how-to-use-it.md)).

## Investment — for the epistemically calibrated investor

⚠️ **v0 is advisory-only.** No broker integration. No trade execution. The app logs theses, scores them, surfaces bias warnings via Belief OS. *You read; you decide.*

**The deal:** every position you hold (or are about to hold) gets a **PositionThesis** with: the thesis text, supporting evidence, an explicit invalidation condition, an expected timeline, a confidence level (low/medium/high). 100% thesis coverage is the bar.

**The score:** the **calibration error** — over time, how well does your stated confidence match the rate at which your theses survive vs invalidate. Plus thesis-survival rate, bias-detection rate, decision consistency.

**The drift card:** when you're about to act on a position, the system runs a **Belief OS bias check** on the thesis text and surfaces warnings:

| Drift mode | What it looks like | What the app suggests |
|---|---|---|
| Emotional | Fear / FOMO / volatility-induced action | File the thesis BEFORE acting (15 min); defer 24h |
| Narrative-following | "AI is huge, X is the AI play" | Map the causal mechanism (20 min) |
| Price-obsessed | Refreshing the chart hourly | Pause; recheck thesis (10 min); close the chart for 24h |
| Overconfident | Confidence > evidence | Log a CalibrationRecord; enumerate 3 failure paths |
| Social-proof-following | "X said it's good" | Run Belief OS bias check on the thesis |
| Ego-attached | Position became identity | Write the kill-condition; role-play a short-seller |

**Privacy:** position theses default to **private to investment**. They never reach research or startup unless you explicitly share. Founder Loop never sees them.

## Startup — for a founder building a startup

**The deal:** commit to one **load-bearing hypothesis** for 40 days. Changing the active hypothesis is allowed but expensive — `thesis_pivots/day` is hard-capped at 1, and the abuse-tax bites at 3+ kills in 40 days. Anti-novelty-addiction.

**The score:** the **strategic continuity score** (1 - kill_count/40), **trust density** (fraction of audience members who engaged with you twice or more), audience-signals captured, conversion quality.

**The drift card:** the founder-OEC review when you're about to abandon the active hypothesis or re-feature-creep:

| Drift mode | What it looks like | What the app suggests |
|---|---|---|
| Idea-chaos | A new "what if we…" every day | Park the idea; reaffirm the active hypothesis aloud |
| Broadcasting | Pushing without listening | Capture an AudienceSignal from a recent reply |
| Feature-creep | Building without identifying the constraint | Identify this week's Bottleneck (15 min) |
| Vision-intoxicated | Excitement over evidence | Stress-test against the falsification signal |
| Vanity-metrics | Counting impressions, not retention | Switch the dashboard to repeat-engagement |
| Random-execution | Mood-driven days | Run the nightly OEC review |

**Try it now:** `neuro-os startup onboard --priorities-file priorities.json --active-hypothesis-id hyp-001`.

---

# Why this shape, four times

Three things that aren't in habit-trackers / research apps / portfolio trackers / startup-OS-apps:

1. **The deal is signed by yesterday-you**, not enforced by some external thing. It's not Instagram telling you you've used it too long. It's *you*, this morning, asking *you, this afternoon* to honor a thing you both agreed to. Same shape across all four products.
2. **Drift is treated as a misaimed real desire**, not a moral failure. The app's job is to help you find the real thing you want, not to suppress the surface-level want. Same machine across all four — what differs is the catalog of "real things you want."
3. **You always retain agency.** Nothing is ever blocked outright. The app makes the cost visible, but the choice is always yours.

It's a system to help you become more honest with yourself, in whichever life-domain you've chosen to focus on. Not a cage.

---

# Five things that make the system compound

Same metaphor stack — but layered on top are five mechanisms that turn a daily ritual into something that **gets sharper as you use it**. Each is a small, opt-in lever; you don't need to use all five to get value from the daily ritual.

| Mechanism | What it does for you |
|---|---|
| **Corpus ingestion** | Drop the papers / books / transcripts you're reading into a folder; the system extracts candidate "mechanism cards" for you to review. No more typing each card by hand. Two paths: `gbrain` ([garrytan/gbrain](https://github.com/garrytan/gbrain)) if you have it installed, OR a native Python extractor for `.txt` / `.md` / `.pdf` files (zero extra deps). The system auto-detects which is available. |
| **Dashboard** | One-screen rollup of your last 7 / 40 days. Shows the **compound curve** (mechanism-cards/day trending), the drift histogram, the stick-rate of your accepted constructive expressions, and — critically — **drift modes that NEVER fired** so you can revise the catalog from data, not opinion. |
| **Cross-vertical entity graph** | When you accept a mechanism card and tell it "this mentions NVIDIA," an `Entity` page is created in the cross-vertical store. Default-PRIVATE to research; explicit `share-note` opens it to investment. Over time, a typed knowledge graph forms across your verticals — without ever leaking what you didn't share. |
| **Cross-modal Belief OS** | When a position thesis goes through bias-checking, it's run through K models in parallel (default 3 — Haiku + Sonnet + Opus). If they DISAGREE, the system surfaces a `low_confidence` warning that's a stronger signal than any single model's flag. Disagreement is the diagnostic — that's where human judgment matters most. |
| **Skillify (catalog evolution)** | Every time you choose something OTHER than the constructive expression the system proposed and you log it (`loop urge ... --override-of <mode>`), it's evidence the catalog is wrong. After ≥5 same-mode overrides, the system proposes a new constructive expression for you to review. **Law 7 honored**: the catalog itself only changes via an explicit human commit. |

These mechanisms are all in [`docs/how-it-works.md`](./how-it-works.md#the-five-compounding-mechanisms) if you want the deeper picture.

## Faith and relational anchors

Two non-business pillars that don't fit the four verticals' "drift mode" frame, and intentionally don't get one:

- `loop anchor --kind faith --context "..."` — a typed daily marker for the faith pillar (5:50am prayer, walk, weekly worship, etc.).
- `loop anchor --kind relational --context "..."` — same for the relational pillar (a meaningful Taylor / family / team interaction).

Both ride the existing `UrgeEvent` mechanism — no new vertical, no drift modes, no contracts. The dashboard renders them as "faith: 5/7 days hit; relational: 4/7 days hit" so you see the streak without the system instrumenting your relationships.

---

## What it doesn't do (yet)

- **Phone**: it doesn't watch your phone — for now it's a desktop app.
- **Anyone else**: your data lives only on your own machine. Nothing leaves it. Cross-vertical reads are default-private and require explicit opt-in.
- **Sleep / HRV** (founder loop): those signals come from a separate tool called **workflowx**. If you have workflowx installed, the app finds it automatically and uses it; if you don't, the app still works (it just relies on you logging urges manually via the browser extension or `neuro-os loop urge`). See [how it works](./how-it-works.md#box-1--sensors-what-the-app-knows-about-your-day) for what gets read where.
- **Browser extension** (founder loop only today): the YouTube/Twitter/etc. overlay is built for founder loop. The other three products are CLI-only in v0; their browser surfaces are roadmapped.
- **Mobile / voice / multi-user**: roadmapped. See [the roadmap](./roadmap.md).

If any of this sounds interesting, see [how to use it](./how-to-use-it.md).
