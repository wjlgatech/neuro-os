# STATUS — neuro-os

**Last updated:** 2026-05-18 (auto-generated)

**Last commit at update:** `c174891` (2026-05-18 — Stamp 3 PRD drafts; regenerate STATUS.md to include them)


> Single-page "where am I" snapshot. **Auto-generated** by `scripts/sync_status.py` from frontmatter stamps on each plan file + recent git log + a small north-star config. Do NOT hand-edit this file — edit the stamps on individual plan files; the pre-commit hook re-renders this on every commit.

> If `Last updated` above is more than 14 days ago, **stop and fix the staleness before touching code**. The pre-commit hook ensures this can only happen if no commits have landed in 14+ days, which itself is the bug.


## One sentence (north-star)

Neuro-os is a four-vertical AI substrate (`founder_loop` / `research` / `investment` / `startup`) Paul uses to compound personal practice into research output. Two-phase arc: **Phase 1** = mechanism-survival paper (arXiv-first July 2026, ICLR 2027 primary) — the wedge that earns trust + schema + co-authors. **Phase 3** = continual world models for Physical AI on construction sites (NeurIPS 2027 moonshot, ProCore application). Phase 1 unlocks Phase 3.


## Where we are

**3 most recent ships** (from `git log -3`):

| Date | SHA | Subject |
|---|---|---|
| 2026-05-18 | `c174891` | Stamp 3 PRD drafts; regenerate STATUS.md to include them |
| 2026-05-18 | `84c08b1` | Auto-sync pipeline: STATUS.md generated from plan stamps + git log |
| 2026-05-14 | `edaf224` | Phase 1 paper: harness, position paper, world-os v0 demo, research-os fold-in |


## Active this week

| Parent | Plan | Acceptance | Last touched |
|---|---|---|---|
| Phase 1 — mechanism-survival paper | [Phase 1 — Co-Author Outreach Plan](plans/phase-1-coauthor-outreach.md) | 3 shortlisted emails sent (Wk 1: May 12–18, 2026); first 1–2 positive responses accepted by EOD Wk 2 (May 25). Fall back to solo + paid annotator if zero responses. | 2026-05-18 |
| Phase 1 — mechanism-survival paper | [Phase 1 — Mechanism Survival: A Closed-Loop System for Research as Predictive Compression](plans/phase-1-mechanism-survival-paper.md) | arXiv submission July 2026 with: (1) reproducible harness + position paper draft v2 (shipped 5/14 in commit edaf224), (2) real-data corpus swap completed (Wk 14–20, Q3 2026), (3) inter-rater study results, (4) ≥1 co-author secured. | 2026-05-18 |
| Phase 1 — mechanism-survival paper | [Phase 1 — OSF Pre-Registration Draft](plans/phase-1-osf-prereg.md) | Pre-registration submitted to osf.io/prereg/ with DOI before Wk 4 experiment runs begin. Must happen before any survival/calibration numbers are computed on real corpus. | 2026-05-18 |
| Substrate / infra | [Roadmap](roadmap.md) | Feature-tier SHIPPED / NEXT / LATER table per lane, refreshed when a PR lands. Different scope from docs/STATUS.md (north-star + active focus); both files coexist by design. | 2026-05-18 |


## Parked but real (not abandoned)

**Phase 1 — mechanism-survival paper**
- [Phase 1 — NeurIPS 2026 Workshop Targets](plans/phase-1-workshop-targets.md) — NeurIPS 2026 workshop list not yet published. Re-check official accepted-workshops page in Wk 12 (early August 2026); applications close 2026-06-06.
- [Neuro-OS Research Branch PRD (Enhanced)](prd/enhanced_research_prd.md) — Foundational PRD for the research vertical (epistemic primitives that the Phase-1 mechanism-survival paper writes about). Commit message says 'will not merge to main' — kept as reference draft. Un-parks if a future paper needs cited spec.

**Phase 3 — NeurIPS 2027 moonshot**
- [NeurIPS 2027 Moonshot Outline — Continual World Models for Embodied Agents on Construction Sites](plans/neurips-2027-moonshot-outline.md) — Phase 3 depends on Phase 1 paper acceptance signal. Un-parks when phase-1-mechanism-survival-paper goes to arXiv (target July 2026).

**Investment vertical**
- [Neuro-OS Investment Branch PRD (Enhanced)](prd/enhanced_investment_prd.md) — Foundational PRD for the invest vertical. Commit message says 'will not merge to main' — kept as reference draft. Partially shipped via agent/investment/ (catalog, ontology, cost_of_living, trade, dashboard); remainder un-parks when invest vertical gets its next slice.

**Substrate / infra**
- [Plan — 40-day trial dashboard (Lane 5)](plans/40-day-trial-dashboard.md) — Design doc only, no code shipped. Un-parks when Lane 5 dashboard becomes the active focus again — currently blocked by Phase-1 paper push.
- [Plan — gbrain as upstream sensor (Plan B for NEXT #2)](plans/gbrain-as-upstream-sensor.md) — Plan B alternative to research-graphrag-sensor (Plan A). Both parked while Phase-1 paper is the active focus. Un-parks when Paul picks one of the two.
- [Plan — Research-vertical GraphRAG-style ingestion sensor + Yang walkthrough](plans/research-graphrag-sensor.md) — Plan A alternative to gbrain-as-upstream-sensor (Plan B). Both parked while Phase-1 paper push is active. Un-parks when Paul chooses one or the other after Phase-1 ships.
- [Plan — `founder_loop`: a daily reward-economy + sublimation loop, built on what's shipped](plans/understand-the-code-base-fancy-phoenix.md) — Long-form design doc for the founder_loop vertical. Un-parks when Paul returns to substrate work after Phase-1 paper push.
- [Neuro-OS Startup Branch PRD (Enhanced)](prd/enhanced_startup_prd.md) — Foundational PRD for the startup vertical. Commit message says 'will not merge to main' — kept as reference draft. Un-parks when Paul returns to substrate work on the startup vertical (currently lowest-priority of the 4 verticals).


## Done this cycle

**Investment vertical**
- [Phase-1 invest workflow — design + implementation plan](plans/phase-1-invest-workflow.md) — last touched 2026-05-18


## What's actively NOT happening (don't reopen by accident)

- No Phase 3 (NeurIPS 2027) code yet — depends on Phase 1 paper signal.
- No broker integration in invest vertical — advisory-only is a hard invariant.
- No catalog mutation across the 4 verticals — `mutable_paths=[]` locked per Law 7.
- No multi-currency support for invest workflow — USD only, v0 scope.


## Where to look for detail (the spine)

Every stamped plan, grouped by parent. `status` tells you what's active/parked/done/abandoned at a glance.

| Parent | Plan | Status | Last touched |
|---|---|---|---|
| Phase 1 — mechanism-survival paper | [Phase 1 — Co-Author Outreach Plan](plans/phase-1-coauthor-outreach.md) | `active` | 2026-05-18 |
| Phase 1 — mechanism-survival paper | [Phase 1 — Mechanism Survival: A Closed-Loop System for Research as Predictive Compression](plans/phase-1-mechanism-survival-paper.md) | `active` | 2026-05-18 |
| Phase 1 — mechanism-survival paper | [Phase 1 — OSF Pre-Registration Draft](plans/phase-1-osf-prereg.md) | `active` | 2026-05-18 |
| Phase 1 — mechanism-survival paper | [Phase 1 — NeurIPS 2026 Workshop Targets](plans/phase-1-workshop-targets.md) | `parked` | 2026-05-18 |
| Phase 1 — mechanism-survival paper | [Neuro-OS Research Branch PRD (Enhanced)](prd/enhanced_research_prd.md) | `parked` | 2026-05-18 |
| Phase 3 — NeurIPS 2027 moonshot | [NeurIPS 2027 Moonshot Outline — Continual World Models for Embodied Agents on Construction Sites](plans/neurips-2027-moonshot-outline.md) | `parked` | 2026-05-18 |
| Investment vertical | [Phase-1 invest workflow — design + implementation plan](plans/phase-1-invest-workflow.md) | `done` | 2026-05-18 |
| Investment vertical | [Neuro-OS Investment Branch PRD (Enhanced)](prd/enhanced_investment_prd.md) | `parked` | 2026-05-18 |
| Substrate / infra | [Plan — 40-day trial dashboard (Lane 5)](plans/40-day-trial-dashboard.md) | `parked` | 2026-05-18 |
| Substrate / infra | [Plan — gbrain as upstream sensor (Plan B for NEXT #2)](plans/gbrain-as-upstream-sensor.md) | `parked` | 2026-05-18 |
| Substrate / infra | [Plan — Research-vertical GraphRAG-style ingestion sensor + Yang walkthrough](plans/research-graphrag-sensor.md) | `parked` | 2026-05-18 |
| Substrate / infra | [Plan — `founder_loop`: a daily reward-economy + sublimation loop, built on what's shipped](plans/understand-the-code-base-fancy-phoenix.md) | `parked` | 2026-05-18 |
| Substrate / infra | [Neuro-OS Startup Branch PRD (Enhanced)](prd/enhanced_startup_prd.md) | `parked` | 2026-05-18 |
| Substrate / infra | [Roadmap](roadmap.md) | `active` | 2026-05-18 |

**Reference docs** (not stamped — load-bearing background):

- [AI_NATIVE_ENGINEERING_PRINCIPLES.md](AI_NATIVE_ENGINEERING_PRINCIPLES.md) — 10 laws + enforcement tags
- [how-it-works.md](how-it-works.md), [how-to-use-it.md](how-to-use-it.md), [what-is-this.md](what-is-this.md) — user-facing intros
- [prd/](prd/) — product requirement drafts


## Weekly ritual (5 min, Sundays)

1. Skim **Active this week** — does it match what you actually want to be doing? If not, move stamps.
2. Look at **Last touched** dates — any active row >7 days cold? Either revive or mark parked.
3. Re-read **Parked but real** — any row parked >30 days? Decide: revive or abandon (delete the file).
4. If you skipped a week, add a one-line note in the parent plan you most recently touched. Don't lie.
5. Confirm at least one active row's `Last touched` is <7 days. If not, the project is sleeping — that's data.

---
_This file is generated by `scripts/sync_status.py`. Edit the frontmatter stamps on individual plan files (or the north-star config in `agent/status/render.py`) — never STATUS.md directly._
