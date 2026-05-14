# world-os (seed)

> v0 user-facing demo for the *Mechanism Survival* position paper.
> Currently lives inside `neuro-os` at `world_os/`; this directory
> becomes the seed for the public `world-os` spin-off repo when
> `/goal-2` (1k stars by 2026-12-31) launches.

## Run locally

From `neuro-os/` root:

```bash
streamlit run world_os/app.py
```

The app opens at `http://localhost:8501` with four tabs.

## What you'll see

### Tab 1 — Proposal Inbox

Browse all **60 real LLM extractions** (10 papers × 6 systems).
Pick a system (default Ours_full_loop) and a paper. The card's
four schema fields render on the left; the source paper renders
on the right. **If the LLM's claimed `source_excerpt` substring-
matches the paper, you'll see the matched span highlighted in
green; if not, you'll see "✗ Excerpt NOT found".**

This is the paper's headline LLM-behavior finding made live:
Sonnet 4.6 paraphrases ~50% of "verbatim" excerpts despite
explicit instructions. You can verify it on any of the 10 papers.

### Tab 2 — Accept / Reject Gate (Law 7)

The human review surface. For each pending extraction, click
Accept / Reject / Edit. Each click emits a real `OverrideEvent`
(session-local in v0). Session stats track your decisions in
real time.

This makes the "closed loop" concrete: the system proposes, the
human gates, the override events flow into the skillify accumulator.

### Tab 3 — Cross-rater Diff (human vs LLM)

For each of the 10 papers, gold card (hand-written by the author)
on the left, Ours_full_loop card (Sonnet 4.6) on the right. Each
of the four fields is color-coded by the independent LLM judge's
agreement classification:

- 🟢 **green** = strong agreement
- 🟡 **yellow** = partial agreement
- 🔴 **red** = weak agreement

The top-of-page metrics show the per-field strong-agreement rates
(**90% mechanism**, 40% invariant, 30% failure_mode, 10% prediction)
— the paper's headline reproducibility finding.

### Tab 4 — About

What's in the demo, what's deliberately out of v0 (Skillify Prior
Evolution, Citation Surface — both deferred to Track B), tech stack,
license.

## What's NOT in v0 (deferred)

Two surfaces from `DESIGN_BRIEF.md` are deferred until Track B brings
real downstream-citation data (Wk 14-20):

- **Skillify Prior Evolution** — needs real user override traces
- **Citation Surface** — needs S2ORC + Scite.ai integration

See `experiments/phase_1/decisions/TODO_REAL_DATA.md` for the
integration plan.

## Anti-goals

The UI deliberately does NOT visualize the synthetic decision
corpus or the stipulated outcome probabilities from
`experiments/phase_1/decisions/{synthetic.py,outcomes.py}`. Every
chart and number traces to real measurements on disk. This is
encoded in `memory/feedback-synthetic-data-is-not-measurement.md`
as a permanent guardrail.

## Files

- `app.py` — main Streamlit app (~400 lines, 3 tabs + about)
- `data_loaders.py` — shared loaders; reads only real artifacts on disk
- `DESIGN_BRIEF.md` — the one-pager spec this v0 implements
- `assets/` — screenshot pack for paper + LinkedIn + HN (TBD)

## v1 migration path

Streamlit is the right v0 tool because it's already in the neuro-os
stack and the data is JSON on disk. For the public spin-off (Q3 2026,
Wk 14-20 = Task #23), v1 rebuilds on:

- Next.js 16 + React 19 + TypeScript
- shadcn/ui + Tailwind
- Zustand for state, FastAPI for the background skillify accumulator
- Postgres / sqlite-cloud for persistence

Same surface, production polish. **No AGPL dependencies** — that's
why we did NOT build on OpenMAIC despite the surface similarity.
