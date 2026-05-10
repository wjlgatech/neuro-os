# Paul's week of May 11–17, 2026 — runbook

> Experiment runbook, not a permanent doc. Goal: Paul runs his week's plan from the CLI without distraction or regression. After May 17, the post-mortem either promotes patterns to permanent docs or this file goes away.

## Pre-week setup (Sunday May 10 evening, ~30 min)

```bash
# 1. Make sure the latest code is installed.
cd ~/code/neuro-os && git pull && pip install -e .

# 2. Drop this week's reading into a single directory.
#    .pdf works directly (pypdf); also .txt/.md.
mkdir -p ~/reading/may-11-17
cp ~/Downloads/constitutional-ai.pdf            ~/reading/may-11-17/
cp ~/Downloads/agentic-software-engineering.pdf ~/reading/may-11-17/
cp ~/Downloads/info-theoretic-agentic-design.pdf ~/reading/may-11-17/
cp ~/Downloads/bitcoin-whitepaper.pdf           ~/reading/may-11-17/
cp ~/Downloads/intelligent-investor.pdf         ~/reading/may-11-17/

# 3. Ingest into the research vertical proposal queue.
neuro-os research ingest \
    --prefer local \
    --source-dir ~/reading/may-11-17/ \
    --home ~/.neuro_os_research

# 4. Review proposals. Accept ~10, reject ~5; type entity slugs at the prompt.
#    Suggested slugs to use this week: bitcoin, satoshi, graham, buffett,
#    moats, network-effects, agentic-design.
neuro-os research review --cli --home ~/.neuro_os_research

# 5. Sign Monday's contract (pre-write the priorities JSON tonight).
#    Each priority can carry --time-window 'HH:MM-HH:MM' so the daily
#    rollup can group evidenced priorities by block.
```

## Daily blocks — what to run when

### 5:50 — 7:00 AM • Prayer / worship / walk / plan day

```bash
neuro-os loop anchor --kind faith \
    --context "5:50am prayer + worship + walk + plan done" \
    --home ~/.founder_loop

neuro-os loop morning-ritual \
    --priorities ~/.founder_loop/priorities-monday.json \
    --registry ~/.founder_loop/registry.jsonl \
    --contracts ~/.founder_loop/contracts.jsonl
```

### 7:00 — 9:00 AM • Eat the frog: read seminal papers

If a drift fires (you wanted to switch papers / check Twitter / etc.) and you DID something else, log it in ONE command:

```bash
# Logged the urge AND emits a skillify OverrideEvent for catalog evolution.
neuro-os loop urge novelty \
    --registry ~/.founder_loop/registry.jsonl \
    --contracts ~/.founder_loop/contracts.jsonl \
    --context "switched to YouTube ai-explained instead of CAI section 3" \
    --override-of authority_acceptor \
    --override-vertical research
```

### 9:00 — 10:00 AM • Breakfast / reset

(no system action — the tank refresh signal is built into the morning ritual already)

### 10:00 AM — 12:30 PM • Neuro-OS company building

Drift modes most likely to fire here: `feature_creep`, `idea_chaos`, `vision_intoxicated` (startup vertical). Same `loop urge ... --override-of <mode> --override-vertical startup` pattern.

### 12:30 — 1:00 PM • Lunch break

(no system action)

### 1:00 — 3:00 PM • Neuro-OS work / meetings / outreach

After meetings:

```bash
# Log a relational anchor for any meaningful Taylor-or-team interaction.
neuro-os loop anchor --kind relational \
    --context "talked with Taylor about week, listened" \
    --home ~/.founder_loop
```

### 3:30 — 5:30 PM • YouTube / LinkedIn / community building

Drift modes: `broadcasting`, `social_proof_following`. The browser extension's sublimation card already fires on YouTube and LinkedIn.

### 5:30 — 8:00 PM • Exercise (swim / weights / climb)

(embodied need fulfilled — no system action; tank state is auto-credited via the workflowx adapter if connected)

### 8:00 — 9:00 PM • Cook / eat / clean

(no system action)

### 9:00 — 11:00 PM • Read books / walk / pray / journal / publish

Bitcoin whitepaper or Intelligent Investor reading. After accepting a high-conviction MechanismCard, share with the investment vertical:

```bash
# 1. The card was already accepted earlier in the week via `research review --cli`.
#    Find its id:
neuro-os research entity-list --reader research --home ~/.neuro_os_research

# 2. Look up the corresponding cross_vertical note id:
neuro-os cross-vertical query --reader research --kind mechanism_card

# 3. Share the highest-conviction one with investment:
neuro-os cross-vertical share-note --note-id <id> --with investment

# 4. Publish journal-of-the-day BEFORE sleep (this part is hand-written;
#    not yet system-tracked).
```

### 11:00 PM • Nightly summary

```bash
neuro-os loop nightly \
    --registry ~/.founder_loop/registry.jsonl \
    --contracts ~/.founder_loop/contracts.jsonl

# Compound-curve check (research vertical):
neuro-os research dashboard --home ~/.neuro_os_research --window 7
```

## End-of-week (Sunday May 17)

```bash
# 1. The compound curve over the full week:
neuro-os research dashboard --home ~/.neuro_os_research --window 7 --json \
    > ~/.neuro_os_research/week-1-snapshot.json

# 2. Check anchor streak:
python -c "
from agent.founder_loop import count_anchors_per_day
from pathlib import Path
faith, _ = count_anchors_per_day(home=Path.home() / '.founder_loop',
                                  kind='faith', days=7)
relational, _ = count_anchors_per_day(home=Path.home() / '.founder_loop',
                                       kind='relational', days=7)
print(f'faith: {faith}/7 days; relational: {relational}/7 days')
"

# 3. Did skillify accumulate enough overrides for a SkillProposal?
neuro-os skillify extract --vertical research --threshold 5 --window-days 7

# 4. If yes, review:
neuro-os skillify review --cli
```

## Pass criteria for the week

The week is a SUCCESS if:

- ✅ ≥10 MechanismCards accepted into `mechanism_cards/`
- ✅ Compound-curve trend shows `up` or `flat` (not `down`) on the dashboard
- ✅ Faith anchors hit ≥5/7 days
- ✅ Relational anchors hit ≥4/7 days
- ✅ At least 1 cross-vertical share (research → investment)
- ✅ Zero system regressions (existing 523 tests still pass on Sunday)
- ⚠️ Optional bonus: skillify proposes ≥1 catalog candidate (requires ≥5 same-mode overrides in a week — may not happen this early)

## What to NOT do

- Don't skip the morning anchor + ritual when tired. The 5:50am block is the load-bearing one for everything downstream.
- Don't run `loop urge` without `--override-of` if the drift mode is identifiable. The two-second hint to the system is the difference between skillify having data and skillify being empty 40 days from now.
- Don't share notes cross-vertical reflexively. Cross-vertical privacy is default-PRIVATE for a reason; only share what you'd consciously want a different vertical to know.

## After the week

- If pass criteria met: this runbook becomes a one-paragraph entry in `docs/how-to-use-it.md` ("daily rhythm with neuro-os") and this file gets deleted.
- If pass criteria missed: the post-mortem identifies which feature failed AND which is most worth adding next (probably picks one item from the LATER section in `docs/roadmap.md`).

The system is the regulator; the regulator only works if you run it.
