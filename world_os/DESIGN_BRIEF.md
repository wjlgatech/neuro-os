# world-os UI Design Brief

> One-page spec for the v0 user-facing demo that ships alongside the
> Phase 1 mechanism-survival paper. The brief specifies the surfaces,
> the tech stack, the data sources, the v0-vs-v1 scoping, and the
> explicit anti-goals.

---

## Goal

The Phase 1 paper argues that AI-assisted research should be evaluated
by **mechanism survival in downstream decisions** — but in its written
form the argument is abstract. A working UI that lets a reader extract
a card, audit its provenance, see two annotators agree (or not), and
watch the closed loop in action **makes the argument tangible in 60
seconds**. Without it, the paper is talk; with it, the repo is the
demo.

This brief specifies that UI. It also locks the scope to surfaces
backed by **real measurements** — same lesson as
`feedback-synthetic-data-is-not-measurement`.

---

## Strategic context

| Goal it serves | How |
|---|---|
| **/goal-2** (world-os to 1k stars by 2026-12-31) | The v0 is the spin-off seed. It demos the paper's argument; HN won't star a Pydantic class but they will star a working live-audit UI. |
| **/goal-3** (love12xfuture brand) | A screenshot-able UI generates content (LinkedIn long-form, YouTube intro video, X threads). The brief and the v0 ship the same week as the arXiv preprint. |
| **Phase 1 paper** | Reviewer reading the arXiv: "OK but does this thing actually exist?" → clone → `streamlit run`. Pulls reviewer trust from "interesting framing" to "this is a working system." |
| **Phase 3 moonshot** | The closed-loop UI demonstrated here is the same surface a construction-site agent eventually uses. Building it now means Phase 3 inherits the surface, not the other way around. |

---

## Surfaces (five total; v0 ships three)

### v0 — backed by real measurements (ship this week)

**Surface 1 — Proposal Inbox.** Browse the 60 real LLM extractions on
disk (`experiments/phase_1/results/extractions/<system>/`). Each card
displays:
- The four fields (mechanism, invariant, prediction, failure_mode)
- The claimed source_excerpt
- The source paper rendered alongside, with the excerpt **highlighted
  in-place IF** `verify_excerpt_in_text` returns True; **flagged as
  paraphrased** if it returns False.

This surface is the live provenance audit. Readers see the 50% gap
the paper claims with their own eyes.

**Surface 2 — Accept / Reject Gate (Law 7).** For any pending proposal,
the user picks Accept / Reject / Edit. Acceptance emits an
`OverrideEvent` via `agent/skillify/events.py::write_override_event`
(it's already implemented). The accepted card becomes part of the
skillify prior visible in Surface 3 (when v1 ships) or pending data
for it (in v0). The N=10 hand-extracted gold cards are pre-loaded as
the initial "accepted" set so the gate has content out of the box.

**Surface 5 — Cross-rater Diff.** Side-by-side: gold card (human) on
the left, LLM card (Sonnet 4.6 Ours_full_loop) on the right. Each of
the four fields is color-coded by the judge's agreement classification
from `inter_rater_agreement.json` (strong / partial / weak). The
mechanism field shows the 90% strong-agreement headline at a glance
across the 10 papers.

### v1 — requires Track B real data (deferred to Wk 14-20)

**Surface 3 — Skillify Prior Evolution.** A timeline showing how the
in-context prior changed as cards were accepted. Each accepted card
appears as a node, with the override-rate trajectory over time as the
axis. **Requires real override data from real users** — not the
modeled trajectory in v0's `metrics/override_rate.py`. Until Track B
brings real users, this surface stays a stub or is omitted.

**Surface 4 — Citation Surface.** For each extracted card, the list of
**real downstream citations from S2ORC** with their citation contexts
classified (supporting / contrasting / mentioning) via Scite.ai. The
"40-day survival" claim becomes a real number once these citations and
their classifications are integrated. **Blocked on Track B** (see
`experiments/phase_1/decisions/TODO_REAL_DATA.md`).

---

## Data sources (v0 only — all real)

| Surface | Backed by | Path |
|---|---|---|
| Proposal Inbox | 60 Sonnet 4.6 extractions, 10 papers × 6 systems | `experiments/phase_1/results/extractions/` |
| Inbox provenance audit | Real paper text; `verify_excerpt_in_text` regex check | `research_practice/inbox/*.txt` + `experiments/phase_1/extractors/base.py` |
| Accept/Reject gate | 10 hand-extracted gold cards as pre-loaded "accepted" set | `tests/fixtures/research/gold/` |
| Cross-rater diff | Real judge results from Wk 9 inter-rater study | `experiments/phase_1/results/inter_rater_agreement.json` |

**No data on this list comes from `decisions/synthetic.py` or
`decisions/outcomes.py`.** That harness is v1 prototype and is
intentionally invisible in the v0 UI.

---

## Tech stack

### v0 — Streamlit (this week)

- **Reason:** the existing neuro-os UI is Streamlit (`ui/app.py`, 847
  lines, 4 tabs). Adding more pages costs an hour, not a week. The
  data is on disk in JSON form; reading + rendering is straightforward.
- **Cost:** zero new dependencies. Streamlit is already in
  `requirements.txt`.
- **Tradeoff:** Streamlit is fine for research demos, mediocre for
  product. Acceptable for v0 (audience = paper reviewers, HN crowd
  willing to `pip install`).

### v1 — Next.js 16 + React 19 + shadcn/ui (Q3 2026, Wk 14-20)

- **Reason:** for the public `world-os` spin-off repo to hit 1k stars,
  the UI needs production polish. Streamlit demos rarely virally
  spread; React apps with shadcn/ui look like 2026 SaaS and they
  share well.
- **Stack:** Next.js 16 (App Router), React 19, TypeScript, Tailwind,
  shadcn/ui, Zustand for state, fastapi or Inngest for the background
  skillify accumulator, Postgres / sqlite-cloud for persistence.
- **Explicit anti-stack:** **NOT OpenMAIC.** AGPL-3.0 license would
  virally relicense neuro-os, breaking commercial adoption. We borrow
  OpenMAIC's stack *choices* (Next.js + shadcn + LangGraph) without
  borrowing OpenMAIC's *code* (license incompatibility) or its
  *paradigm* (AI-teacher classroom is not the right metaphor for
  closed-loop research).

### v0 → v1 migration path

The Streamlit v0 surfaces map 1:1 to React routes. The data layer
(JSON files on disk for v0 → Postgres rows for v1) is hidden behind
the same Python module signatures. v1 work is mostly frontend; the
backend extraction / metrics / audit modules stay where they are.
**v0 is not throwaway** — it's the same product, lower-fidelity.

---

## Anti-goals (lessons encoded)

1. **Do NOT visualize the synthetic decision corpus or stipulated
   outcomes.** Every chart in the UI must trace to a real measurement
   on disk. If it depends on `SUCCESS_P_BY_SYSTEM` or `TRAJECTORY_PARAMS`,
   it does not ship in v0.
2. **Do NOT claim survival, override-trajectory, calibration, or
   transferability in the UI.** Those land when Track B brings real
   data. Until then, the relevant surfaces (3, 4) show "real-data
   integration in progress" with a link to `TODO_REAL_DATA.md`.
3. **Do NOT embed OpenMAIC or any AGPL-licensed dependency.** All
   third-party code must be MIT / Apache / BSD / ISC compatible with
   the rest of neuro-os.
4. **Do NOT build the "AI teacher" / classroom paradigm.** The user
   of world-os is a researcher reviewing cards, not a student watching
   a lecture. Wrong metaphor, wrong UX.
5. **Do NOT ship a UI that fakes interactivity.** The accept/reject
   gate must actually emit `OverrideEvent`s and persist them; the
   provenance audit must run the real regex; the cross-rater diff
   must read real judge results. No mock data; no Lorem Ipsum.

---

## Concrete v0 deliverable (this week)

- A new Streamlit app at `world_os/app.py` (or as new tabs grafted
  onto `ui/app.py`).
- Three working surfaces (1, 2, 5) backed by real data on disk.
- A README that explains how to run it and what each surface shows.
- Screenshot pack for the LinkedIn / HN / arXiv-paper companion.

Effort estimate: ~6-8 hours of Streamlit + data-loading work.
Achievable in one focused session.

---

## Open questions (pre-build)

1. **Should v0 modify `ui/app.py` directly or live in its own
   `world_os/app.py`?**
   - Recommend: separate file. The existing 4-tab app demos the OEC /
     ontology layer; the world-os surfaces demo the research vertical.
     Different audience, different framing. When world-os spins off,
     `world_os/` becomes the new repo root.

2. **Should the Accept/Reject gate actually mutate state, or just
   visualize a pending event?**
   - Recommend: v0 actually writes the override events to disk
     (real `agent/skillify/events.py::write_override_event` call).
     Read-only demos lose the closed-loop argument.

3. **Should the source-paper rendering show the full PDF or just the
   `.txt` extraction?**
   - Recommend: v0 uses the `.txt` extractions (already converted with
     pdftotext during Wk 4-5). PDF rendering in Streamlit is awkward;
     the `.txt` is what the extractors actually saw, so showing it is
     epistemically honest.

4. **Is "world-os" the right name?**
   - Open. Alternatives: `mechanism-os`, `reading-os`, `card-os`. For
     v0 inside neuro-os, the name doesn't matter; for the public spin-
     off, decide before Wk 11 HN launch.

---

## Next steps (post-brief)

1. Build v0 surfaces 1, 2, 5 in Streamlit. **Today.**
2. Take screenshots; add to `world_os/assets/`.
3. Write a 1-paragraph "live demo" section for the arXiv paper README
   pointing readers at the running UI.
4. Add to SUBMISSION_CHECKLIST.md: "ensure `streamlit run world_os/app.py`
   loads without errors before submission."
5. Defer surfaces 3 and 4 to Wk 14-20 (Track B).

---

**Owner:** Paul Wu. **Reviewed:** 2026-05-12 alongside the position-paper
v2 rewrite. **Aligned with:** [[phase-1-mechanism-survival-paper]],
[[goal-world-os-repo]], [[feedback-synthetic-data-is-not-measurement]].
