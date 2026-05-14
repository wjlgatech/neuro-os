# Phase 1 — Mechanism Survival: A Closed-Loop System for Research as Predictive Compression

> Working draft. Author: Paul Wu (wjlgatech) + 1–2 academic co-authors TBD. Companion repo: `neuro-os` (this repo, includes the personal reading practice in `research_practice/` — folded in on 2026-05-14, was originally a sibling project `research-os/`). Phase 1 of a two-phase arc; Phase 3 lives in `neurips-2027-moonshot-outline.md`.
>
> **Venue strategy (locked 2026-05-12, after NeurIPS 2026 deadline check):**
> - **Primary target:** ICLR 2027 (submission ~late Sept / early Oct 2026, decision Jan 2027). Track: D&B-equivalent / main / evaluations.
> - **Side track 1 — arXiv-first:** target July 2026. Claims priority, seeds `goal-world-os-repo` traction, kicks off `goal-love12xfuture-brand` content cadence.
> - **Side track 2 — NeurIPS 2026 Workshop:** workshop applications close 2026-06-06; workshop paper deadlines typically Aug–Sept. Opportunistic in-person presence at NeurIPS 2026 with a workshop version.
> - **Backup target:** NeurIPS 2027 Evaluations & Datasets Track (May 2027). **Avoid** unless ICLR 2027 declines — Phase 3 also targets NeurIPS 2027 main, and reviewer-overlap / anonymization risk is real.
>
> **Why this sequencing beats the original 13-day NeurIPS 2026 sprint:**
> Original Plan A was a hallucination — NeurIPS 2026 abstract was May 4 (8 days ago) and full paper was May 6 (6 days ago). The new sequencing gives **5 months of breathing room** for the N=10 corpus, the inter-rater pass, and the 40-day outcome window to mature instead of being rushed. Same paper, defensible execution.
>
> **Locked decisions (2026-05-12):**
> - Corpus: N=10 — EWC + World Models + Latent Replay + 7 to-be-curated.
> - Authorship: Paul + 1–2 academic co-authors (for credibility, inter-rater data, and double-blind affiliation).
> - Note: NeurIPS 2026 "Datasets & Benchmarks" track was renamed to "Evaluations & Datasets" — scope explicitly includes evaluation methodology as a contribution. The 2027 version of that track is the natural backup home.
>
> Status: outline-only — claims still need experimental backing.

---

## 0. The one-sentence pitch

Existing AI-for-research systems optimize for **summary fidelity** (BLEU, ROUGE, retrieval@k, faithfulness). We argue the right objective is **mechanism survival** — does the extracted mechanism continue to predict reality in adjacent decisions over a 40-day window — and we ship a closed-loop system, a schema, an eval corpus, and golden cases that measure it.

---

## 1. Why this paper, why now

Three claims the field is missing:

1. **Reading = predictive compression, not retrieval.** Every "AI research assistant" benchmark today measures whether a model can retrieve or summarize a passage. None measures whether the extracted understanding *predicted what happened next*. The PRD in `docs/prd/enhanced_research_prd.md` makes this explicit: *"Understanding means predictive compression. Verbal fluency mistaken for understanding is the anti-pattern."*
2. **Eval should be downstream, not intrinsic.** A mechanism extracted from a paper is useful iff it survives being cited in a real decision that has a real outcome. We have that loop (research → investment thesis → 40-day survival score; research → founder-loop drift detection → override evidence).
3. **The extraction policy should evolve from its own override history.** `skillify` already turns every human override of a system suggestion into evidence that re-prioritizes future extractions. This is a self-improving research prior — and to our knowledge no benchmark measures *override-rate-over-time* as the success signal.

Positioning sentence for the abstract: *"We reframe AI-assisted research as a closed-loop predictive-compression task, contribute the MechanismCard schema and the 40-day survival metric, and show that an evidence-graded extraction prior (skillify) reduces human override rate by X% on a corpus of N papers across M downstream decisions."*

---

## 2. Contributions

1. **MechanismCard schema** — a four-field commitment (`mechanism`, `invariant`, `prediction`, `failure_mode`) that operationalizes "you understood the paper" as four falsifiable predictions, not a paragraph.  
   Source of truth: `agent/research/ontology.py::MechanismCard`. Provenance pinned to source excerpt (`source_id`, `source_excerpt`, `line_range`) — Law 1 of the AI-Native Engineering Principles.

2. **Mechanism survival metric** — for each accepted card, track:
   - **Citation survival**: was the card cited in ≥1 downstream decision within 40 days?
   - **Prediction calibration**: did the card's `prediction` field match observed outcome (binary or graded)?
   - **Override frequency**: how often did the user override system suggestions that cited this card?
   - **Transferability lift**: does the same mechanism, applied to a different vertical, predict outcomes better than chance?

3. **Closed-loop ingestion → review → cross-vertical-share → outcome-tracking pipeline**, fully open-source. The five stages already exist as testable units:
   - Ingest (`agent/research/ingest.py`, `ingest_router.py`)
   - Review queue (`agent/research/proposals.py`)
   - Cross-vertical share (`agent/cross_vertical.py::read_shared`)
   - Belief-OS bias check (`agent/cross_modal.py::make_default_scorers`)
   - Override-event emission (`agent/skillify/events.py::write_override_event`)

4. **A Datasets & Benchmarks contribution**: the **MechanismCard Bench** — N papers across continual learning, world models, and on-device learning, each with (a) gold mechanism cards extracted by domain experts, (b) M downstream decision artifacts (investment theses, founder-loop drift cards) that cite or override them, (c) 40-day outcome labels. Companion corpus lives in `research_practice/inbox/` (starter: EWC, World Models, Latent Replay) + extended set TBD.

5. **An evaluation methodology**: golden cases (`tests/test_research_*`) that pin the extraction shape, plus a Belief-OS-style bias-check on the cards themselves.

---

## 3. Related work — and why none of it answers our question

| Family | What it measures | What it misses |
|---|---|---|
| RAG / GraphRAG (Lewis 2020, Edge 2024) | retrieval@k, faithfulness | does the retrieved fact help me decide? |
| LLM-as-judge for science (Lin 2024, etc.) | pairwise quality | no downstream outcome |
| Survey-generation systems (auto-survey, scite) | citation graph fidelity | confuses fluency for understanding |
| Continual learning benchmarks (CLEAR, Stream-51) | accuracy under shift | not about *humans reading papers* |
| Knowledge-graph extraction (REBEL, GenIE) | triple F1 | triples ≠ mechanisms; F1 ≠ predictive utility |
| AutoGPT-style research agents | task completion | hallucinated mechanisms, no provenance pinning, no override loop |

Closest neighbors:
- **DocPrompting / paper-QA**: same input (PDF), different output (Q&A vs falsifiable predictions).
- **Continual evaluation (Lin 2023)**: same eval philosophy (downstream task), different domain (model robustness, not human research).
- **Forecaster benchmarks (Karger 2024, Forecasting Riley)**: similar "did the prediction survive?" loop — we adapt their methodology to the per-paper level.

---

## 4. Method

### 4.1 Ingestion + extraction (Layer 1 in `research_practice/` parlance)
- Input: `RawSource` (text + provenance, frozen Pydantic). Format support: `.txt`, `.md`, `.vtt`, `.srt` today; PDF via pre-conversion.
- LLM-based extraction with provenance pinning. Output: `MechanismCardProposal` with `status="pending"`, `confidence ∈ {low, medium, high}`, `extraction_method`, `extraction_model`, and a mandatory `source_excerpt` (≤500 chars).
- Heuristic fallback when LLM unavailable, to keep the loop hermetic in CI.

### 4.2 Human review surface (Law 7 gate)
- `research review` CLI (already in `agent/cli.py`) — accept / reject / edit.
- Edit events become first-class skillify override events: the *human-vs-LLM* delta is the training signal.

### 4.3 Cross-vertical hand-off
- Default visibility: `[source_vertical]` (private). Explicit `share_with=[investment]` to broaden.
- Investment vertical files a position thesis citing the card → 40-day outcome window opens.
- Founder-loop vertical optionally consumes mechanism as a drift-detection prior.

### 4.4 Belief-OS bias-check
- Each accepted card runs through `make_default_scorers` for known cognitive-bias flags (authority, recency, novelty, confirmation).
- Flagged cards don't block — they get an `assumption` annotation that gets surfaced at decision time.

### 4.5 Outcome tracking
- `NightlySummaryBase` 4-metric rollup runs for 40 days after first citation.
- `golden_cases.py` provides the deterministic eval surface.
- `dashboard.py::DashboardSummary` aggregates survival rate, override frequency, and transferability lift.

### 4.6 Self-improving prior (the skillify loop)
- Every override emits `OverrideEvent` (via `agent/skillify/events.py`).
- Override events accumulate per (drift_mode, vertical) pair.
- Future extractions re-weight using accumulated overrides as a prior.
- **This is the closed loop**: extraction → review → outcome → override → better extraction.

---

## 5. Experiments

### 5.1 Datasets
- **Starter corpus** (`research_practice/PAPERS_MANIFEST.md`): EWC (Kirkpatrick 2017), World Models (Ha & Schmidhuber 2018), Latent Replay (Pellegrini 2019). Chosen for mechanism diversity (regularization / generative sim / latent rehearsal) within one topic family (continual learning).
- **Extended corpus** (TBD, target N≈30): sampled across (a) ML for continual learning, (b) world models / model-based RL, (c) embodied / physical AI grounding. Source: `research_practice/inbox/` + targeted arXiv pulls.
- **Decision corpus**: M synthetic + N real downstream decisions. Synthetic decisions generated from a held-out set of Yang-style investment transcripts (already wired in `tests/fixtures/research/yang/`). Real decisions from Paul's own founder-loop history (consented; private-by-default per `cross_vertical.py`).

### 5.2 Baselines
- **B1 — Vanilla RAG**: chunk + retrieve, no schema commitment.
- **B2 — GraphRAG (Microsoft 2024)**: hierarchical community summaries.
- **B3 — Summarization-only**: extract abstract + key sentences.
- **B4 — MechanismCard, single-shot**: our schema, no skillify prior, no human review (LLM auto-accept).
- **B5 — MechanismCard, human-reviewed**: schema + Law-7 gate, no skillify prior.
- **Ours**: full closed loop (schema + review + skillify prior + Belief-OS bias-check).

### 5.3 Metrics
1. **Mechanism survival rate** (primary): % of cards cited ≥1× in a downstream decision within 40 days.
2. **Override rate over time** (primary): does override frequency decrease as the skillify prior accumulates? Slope of the regression line is the key result.
3. **Prediction calibration** (Brier score against `prediction` field).
4. **Transferability lift** (secondary): same mechanism applied to a vertical it wasn't extracted for — predictive utility above random.
5. **Provenance audit pass rate**: % of cards whose `source_excerpt` can be regex-located in the source. We expect 100% for Ours (Law 1 enforces); baselines will fail.

### 5.4 Ablations
- − skillify prior (does the loop close?)
- − Belief-OS bias-check (does bias-flagging change override behavior?)
- − cross-vertical share (does the multi-vertical use case matter, or does single-vertical work?)
- − human review (Law 7 gate off — does auto-accept degrade survival?)

### 5.5 Hypotheses (declared before running)
- H1: Ours beats B1–B3 on survival rate by ≥2× (mechanisms are sparser but more useful than summaries).
- H2: Override rate decreases monotonically over time for Ours; flat for B4; flat for B1–B3.
- H3: Transferability lift is positive for `invariant`-keyed extraction; near-zero for `mechanism`-keyed alone.
- H4: Provenance audit pass = 100% for Ours, ≤60% for any LLM-baseline that doesn't pin excerpts.

---

## 6. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| 40-day window is too long for a 1-month rebuttal | high | Run two cohorts staggered; pre-register the metric so reviewers don't read it as cherry-picked |
| Corpus is too small (N=30) | medium | Frame as a **benchmark contribution** explicitly; pitch Datasets & Benchmarks track where small expert-labeled corpora are the norm |
| Reviewer bounces on "system paper, not method paper" | high | Lead with the **eval methodology** as the novelty; the system is the apparatus |
| The skillify prior fails to converge in N=30 papers | medium | Synthetic decision generation (`tests/fixtures/research/yang/`) can extend the override stream without extending the paper corpus |
| Paul is the only annotator (single-rater bias) | high | Recruit 2 external annotators for the gold cards before submission; report inter-rater agreement |
| Novelty overlap with forecaster benchmarks | medium | Cite Karger 2024 + Tetlock; differentiate at the granularity (per-paper, not per-question) |

---

## 7. Timeline — verified against actual CFPs

**Today: 2026-05-12.**

NeurIPS 2026 deadlines verified against `neurips.cc/Conferences/2026/Dates`:
- Abstract: 2026-05-04 AoE — **PASSED**
- Full paper: 2026-05-06 AoE — **PASSED**
- Workshops application: 2026-06-06 — **OPEN**
- Author notifications: 2026-09-24

ICLR 2027 deadlines (projected from ICLR 2026 confirmed pattern + deadline-aggregator sites, **must re-verify against official CFP when it drops, typically July–August 2026**):
- Abstract: **Sept 19, 2026 AoE** (projected — same date as ICLR 2026's actual)
- Full paper: **Sept 24, 2026 AoE** (projected — ICLR norm is 5 days after abstract)
- Author–reviewer discussion ends: early December 2026
- Decision notification: **late January 2027** (ICLR 2026 was Jan 25)
- Conference: April–May 2027

**Key implication for our schedule:** abstract and full paper land in the same week (Wk 19, Sept 15–21). Not a leisurely Wk 19 / Wk 20 split as originally drafted. Re-tighten Wk 18 polish to leave ≥3 days for any abstract-stage corrections before the full-paper deadline.

Realistic execution plan with verified timeline:

**June–July 2026 (8 weeks): Substrate + Corpus + arXiv-first**
- Wk 1 (May 12–18): Verify ICLR 2027 dates; co-author outreach drafted + sent; corpus locked; OSF pre-registration.
- Wk 2–3: Hand-extract 10 mechanism cards (3 starter + 7 curated). Mirror into `tests/fixtures/research/gold/`.
- Wk 4–5: Implement 5 baselines + Ours. Run on the N=10 corpus.
- Wk 6: Implement eval metrics + synthetic decision corpus. Run.
- Wk 7: Ablations. Inter-rater pass with co-author / paid annotator.
- Wk 8 (mid July): arXiv preprint + soft launch of `world-os` repo + first LinkedIn post.

**August 2026 (4 weeks): Workshop submission + paper draft**
- Identify target NeurIPS 2026 workshop(s) (e.g. continual learning, eval methodology, AI for science). Submit workshop version mid-August.
- Begin ICLR 2027 paper draft. Lead with eval methodology.

**September 2026 (4 weeks): ICLR 2027 submission**
- Polish paper draft; final inter-rater agreement check.
- Anonymize repo for double-blind.
- Submit ICLR 2027 abstract + full paper (deadline TBD — verify in Wk 1).

**October–December 2026 (12 weeks): Workshop presentation + Phase 3 begins**
- NeurIPS 2026 (Dec): workshop poster/talk if accepted. In-person presence regardless.
- Phase 3 architecture sketch begins (see `neurips-2027-moonshot-outline.md`).
- `world-os` repo HN launch timed to NeurIPS 2026 attendance.

**January 2027: ICLR 2027 decisions**

**If ICLR rejects:** rebut, then submit to NeurIPS 2027 Evaluations & Datasets Track (May 2027). Coordinate with Phase 3 to avoid reviewer overlap — different reviewer pool, different supplementary.

**If even NeurIPS 2027 declines:** arXiv-first is already done; the paper lives, the repo has traction, the career thesis is served. Move on to Phase 3 full-time.

---

## 8. Why this paper helps the career thesis ("capabilities that didn't exist")

The thesis from `career/README.md` is: *"You don't just write code or papers — you build capabilities that didn't exist."* This paper is the proof:

- **The schema didn't exist**: nobody else operationalizes paper-reading as `(mechanism, invariant, prediction, failure_mode)` with provenance pinning.
- **The metric didn't exist**: nobody else measures research-assistant quality by 40-day mechanism survival in adjacent verticals.
- **The closed loop didn't exist**: nobody else has shown an evidence-graded extraction prior that improves from human overrides in a research-reading context.
- **The corpus didn't exist**: nobody else has paired papers with downstream decisions and outcome labels at this granularity.

Recruiter narrative: *"I built the substrate (neuro-os), I built the eval (MechanismCard Bench), I shipped the paper, I shipped the open-source repo, and the personal practice (now at `research_practice/`) is folded into the substrate itself — reading IS the schema. The system reads me reading, and gets better at suggesting what to read next."*

---

## 9. Companion artifacts to ship with the paper

| Artifact | Path | Status |
|---|---|---|
| Schema source | `agent/research/ontology.py` | shipped |
| Ingestion sensor | `agent/research/ingest.py`, `ingest_router.py` | shipped |
| Proposal queue | `agent/research/proposals.py` | shipped |
| Dashboard | `agent/research/dashboard.py` | shipped |
| Cross-vertical share | `agent/cross_vertical.py` | shipped |
| Skillify event writer | `agent/skillify/events.py` | shipped |
| Belief-OS scorers | `agent/cross_modal.py` | shipped |
| Yang transcripts (synthetic) | `tests/fixtures/research/yang/` | shipped |
| Starter paper PDFs | `research_practice/inbox/` | needs download (`./download-starter-papers.sh`) |
| Gold mechanism cards (annotator-produced) | TBD: `research_practice/extracted/*.md` + `tests/fixtures/research/gold/` | NOT YET BUILT |
| 40-day decision-outcome corpus | TBD: `tests/fixtures/research/outcomes/` | NOT YET BUILT |
| Reviewer reproducibility script | TBD: `examples/neurips-2026-reproduce.py` | NOT YET BUILT |

The "NOT YET BUILT" rows are the long-hours work.

---

## 10. Open questions to resolve before drafting

1. **Track**: Datasets & Benchmarks vs main track? (Recommend D&B — it's where the corpus lives and reviewers accept smaller-N expert-labeled work.)
2. **Co-authors**: solo, or invite 1–2 collaborators to add credibility / second-rater data?
3. **Anonymity**: NeurIPS is double-blind. The `neuro-os` repo is public and identifiably Paul's. Plan: anonymize via a fresh shadow repo with the bare minimum to reproduce; restore identity post-acceptance.
4. **Compute claims**: only inference at extraction time + LLM API calls for baselines. No training claims to make. Easy to defend.
5. **Real-vs-synthetic decision corpus split**: how much of the 40-day decision corpus comes from Paul's own founder-loop history vs synthetic? Pre-register the ratio.
6. **Is `flywheel` cited or co-presented?** The closed-loop OEC philosophy comes from `flywheel`. Citing as related work is cleanest; making it a joint contribution is more ambitious but invites scope creep.

---

## Appendix A — The three starter papers, mapped to the schema

| Paper | mechanism | invariant | prediction | failure_mode |
|---|---|---|---|---|
| Kirkpatrick 2017 (EWC) | Fisher-weighted penalty on weight changes | Not all parameters are equal | Protect high-Fisher weights → less catastrophic forgetting | When task distributions shift adversarially, Fisher estimates lag |
| Ha & Schmidhuber 2018 (World Models) | VAE+RNN compressed model, policy trained in imagination | Most learning shouldn't happen in reality | A compact internal model trained offline can rival on-policy RL | Imagination diverges from reality when the world is poorly compressed |
| Pellegrini 2019 (Latent Replay) | Replay frozen mid-layer features instead of raw inputs | Compressed rehearsal is sufficient if the encoder is stable | On-device CL works without raw-data buffers | If the encoder shifts, latent replay corrupts memory |

Appendix A is the unit test for our own thesis: if the schema can't capture these three papers, the schema is wrong. (It can — but the exercise is the proof.)

---

## 5-month plan (May 2026 – Sept 2026 submission to ICLR 2027)

| Wk | Dates | Track | Deliverable |
|---|---|---|---|
| 1 | May 12–18 | Setup | Verify ICLR 2027 dates; co-author outreach drafted + sent (4 candidates); corpus locked (3 + 7); OSF pre-registration; identify target NeurIPS 2026 workshops |
| 2 | May 19–25 | Extraction | Download starter papers; hand-extract 3 starter mechanism cards (EWC, World Models, Latent Replay); mirror into `tests/fixtures/research/gold/`; co-author response gate (proceed with paid annotator fallback if no commit) |
| 3 | May 26–Jun 1 | Extraction | Curate + extract the 7 additional papers; lock N=10 corpus; PAPERS_MANIFEST.md updated |
| 4 | Jun 2–8 | Baselines | Implement B1 (vanilla RAG), B2 (GraphRAG), B3 (summarization), B4 (single-shot MechanismCard), B5 (reviewed) |
| 5 | Jun 9–15 | Baselines | Run all 5 baselines + Ours across N=10 corpus; capture raw outputs in `experiments/phase-1/` |
| 6 | Jun 16–22 | Eval | Implement survival, override-rate, calibration, transferability, provenance audit metrics |
| 7 | Jun 23–29 | Eval | Generate synthetic decision corpus from Yang fixtures + 40-day outcome labels |
| 8 | Jun 30–Jul 6 | Ablations | − skillify, − bias-check, − cross-vertical, − review (4 ablation runs) |
| 9 | Jul 7–13 | Inter-rater | Co-author / paid annotator parallel extraction pass; compute Cohen's κ per field |
| 10 | Jul 14–20 | arXiv | Draft arXiv preprint (sections 1–4); first internal review |
| 11 | Jul 21–27 | arXiv | Draft sections 5–7; **submit to arXiv mid-week**; soft-launch `world-os` repo; first LinkedIn announcement post |
| 12 | Jul 28–Aug 3 | Workshop | Identify final workshop target(s) at NeurIPS 2026; tailor workshop version (8pp) |
| 13 | Aug 4–10 | Workshop | Polish workshop submission; **submit to NeurIPS 2026 workshop** |
| 14–17 | Aug 11–Sep 7 | ICLR draft | Expand arXiv into full ICLR paper; add ablation tables, related work, supplementary, reproducibility script |
| 18 | Sep 8–14 | ICLR polish | Co-author final review; anonymization audit; supplementary lock |
| 19 | Sep 15–21 | ICLR submit | **Submit ICLR 2027 abstract** by Sept 19 AoE (projected) AND **submit full paper** by Sept 24 AoE (projected). Both in this same week. Re-verify dates against official CFP in Wk 8 (Task #24). |
| 20 | Sep 22–28 | Buffer / Workshop | Buffer week if ICLR slips; otherwise pivot to NeurIPS 2026 workshop final polish or early Phase 3 architecture sketch. |
| 21+ | Oct 2026 → | Phase 3 begins | World-OS repo HN launch coordinated with workshop acceptance; Phase 3 architecture sketch (`neurips-2027-moonshot-outline.md`) |

## Co-author shortlist — to contact Week 1

Profile we need: ML/NLP faculty or senior PhD with a track record in **eval methodology**, **continual learning**, or **AI-for-science**. Bonus if they have prior NeurIPS / ICLR D&B-equivalent acceptances. The pitch is *"contribute the inter-rater annotation pass and one section of related-work writing for second-author credit on a paper with shipped code and a defensible novelty, targeting ICLR 2027 with an arXiv preprint and NeurIPS 2026 workshop landing."*

Approach: 4 outreach emails Week 1, accept the first 1–2 to respond positively by end of Week 2. If zero responses, fall back to **solo + 1 paid annotator** ($500–1.5k) without changing the venue strategy.

Outreach template + shortlist lives in the task list — draft Week 1.

## Critical path — what blocks what

- **ICLR 2027 date verification (Wk 1)** blocks the entire backend of the schedule. Cheapest single task; do it first.
- **Corpus lock (Wk 3)** blocks baselines (Wk 4–5), which block eval (Wk 6–7), which blocks ablations (Wk 8) and writing.
- **Co-author commit (Wk 2)** blocks inter-rater pass (Wk 9). If no commit, swap in paid annotator on Wk 7.
- **OSF pre-registration (Wk 1)** must precede results (Wk 5) to avoid post-hoc-tuning reviewer challenge.
- **arXiv preprint (Wk 11)** is the gate for `world-os` soft launch + first brand post. Slipping arXiv slips the entire `/goal-2` and `/goal-3` ramp.
- **NeurIPS 2026 workshop applications close 2026-06-06.** Workshop *paper* deadlines (mid-Aug typical) gate Wk 13 submission. Workshop selection happens Wk 12 once we know which ones got accepted.

The substrate is shipped. The corpus, the gold cards, the inter-rater pass, the arXiv preprint, the workshop submission, and the ICLR paper are the long-hours work.
