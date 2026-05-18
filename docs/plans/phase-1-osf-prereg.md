---
status: active
parent: phase-1-paper
acceptance: "Pre-registration submitted to osf.io/prereg/ with DOI before Wk 4 experiment runs begin. Must happen before any survival/calibration numbers are computed on real corpus."
---

# Phase 1 — OSF Pre-Registration Draft

> **Purpose:** Paste this into [OSF pre-registration](https://osf.io/prereg/) before any results are computed (target: Wk 1, before Wk 4–5 experiment runs). Pre-reg DOI/link must be cited in the ICLR 2027 submission to defend against post-hoc-tuning reviewer challenges.
>
> **OSF template recommended:** "Prereg Challenge" or "OSF Preregistration" (standard, no domain template needed).
>
> **Public status:** Make immediately public (registered prereg with timestamp is the entire point).

---

## 1. Title

**Mechanism Survival: A Closed-Loop Eval Methodology for AI Research Assistants**

## 2. Authors

Paul Wu (independent / TBA institutional affiliation via co-author). Co-author(s) TBD by 2026-05-26 — see `phase-1-coauthor-outreach.md`.

## 3. Description (1 paragraph)

Existing AI-for-research systems are evaluated on summary fidelity (BLEU, ROUGE, retrieval@k, faithfulness). We propose that the correct objective is **mechanism survival** — whether an extracted mechanism continues to predict reality in adjacent decisions over a 40-day window. We pre-register four hypotheses comparing a closed-loop MechanismCard extraction system (Ours) against four baselines (vanilla RAG, GraphRAG, summarization-only, single-shot MechanismCard, reviewed MechanismCard) on a corpus of N=10 papers across continual learning, world models, and embodied AI, paired with M synthetic + N real downstream decisions.

## 4. Hypotheses

**H1 — Mechanism survival rate** (primary): Ours achieves a mechanism-citation survival rate at least 2× the strongest summary-fidelity baseline (RAG, GraphRAG, or summarization-only) over a 40-day post-extraction window.

**H2 — Override-rate trajectory** (primary): The override rate (humans rejecting or editing system-extracted mechanism cards) decreases monotonically over time for Ours; the override rate is flat or rising for the single-shot MechanismCard baseline (B4). The slope of the regression line (override rate vs. time) is the test statistic.

**H3 — Transferability lift** (secondary): For Ours, the same mechanism applied to a different vertical than it was extracted for predicts downstream outcomes better than chance. Specifically, transferability lift is positive for `invariant`-keyed extraction (Cohen's *d* > 0.3) and near-zero (|*d*| < 0.1) for `mechanism`-keyed extraction alone.

**H4 — Provenance audit pass rate** (secondary): The fraction of Ours's extracted cards whose `source_excerpt` field can be exactly regex-located in the source paper is 100% (Law 1 of `neuro-os` enforces this by construction). The same fraction is ≤60% for baselines that don't pin excerpts (B1, B2, B3).

## 5. Design

Between-subjects on the system (Ours vs. 5 baselines). Within-subjects on the paper corpus (each paper extracted by all 6 systems). Within-subjects on the decision corpus (each downstream decision can cite any system's extracted card).

## 6. Sampling plan

- **Paper corpus:** N=10. Selected purposively for mechanism diversity across continual learning (EWC, GEM, A-GEM), world models (Ha & Schmidhuber, Dreamer, MuZero), on-device CL (Latent Replay), and embodied AI (Open X-Embodiment, RT-2). Locked by end of Wk 3 (2026-06-01).
- **Decision corpus:** M=30–50 decisions. Sources: (a) 30 synthetic Yang-style investment transcripts already wired in `tests/fixtures/research/yang/`, (b) 10–20 real founder-loop drift cards from Paul's own usage (consented; private-by-default per `agent/cross_vertical.py`).
- **Synthetic/real ratio:** pre-register the ratio publicly. Target 70/30 synthetic/real for N=50.

## 7. Variables

**Independent:**
- System (Ours, B1, B2, B3, B4, B5)
- Paper ID (categorical, 10 levels)
- Vertical (research/investment/founder-loop)
- Time-since-extraction (continuous, 0–40 days)

**Dependent:**
- Mechanism citation count (count, per card)
- Mechanism citation survival (binary, ≥1 citation within 40 days)
- Override frequency (rate, overrides per system-suggestion)
- Prediction calibration (Brier score on `prediction` field)
- Transferability lift (Cohen's *d* between in-vertical and cross-vertical citation rates)
- Provenance audit pass (binary, per card)

**Control:**
- Reviewer identity (Paul; co-author for inter-rater pass)
- Annotation timing (24h max between extraction and review per card)
- Random seed for stochastic baselines (B1, B2 RAG retrieval)

## 8. Analysis plan

**H1 (survival rate):** Two-proportion z-test, one-sided, Ours > max(B1, B2, B3). α = 0.05. Bonferroni-corrected for 3 baseline comparisons → effective α = 0.0167. Effect size: difference in proportions.

**H2 (override trajectory):** Linear regression of override-rate-per-week against week-number. One-sided test of slope_Ours < 0 AND slope_B4 ≥ 0. α = 0.05 each, Bonferroni-corrected → α = 0.025. Pre-specified intercept = override rate at week 1.

**H3 (transferability lift):** Mixed-effects model with random intercept per paper. Fixed effect: extraction key (`invariant` vs. `mechanism` vs. `prediction` vs. `failure_mode`). Test Cohen's *d* for `invariant` vs. random shuffle. Pre-specified threshold: *d* > 0.3 for H3 confirmed.

**H4 (provenance):** Simple proportion test. No statistical test needed — claim is structural (Law 1 enforces 100% for Ours, baselines that don't pin excerpts cannot achieve >60% by construction unless they coincidentally regex-match).

## 9. Inference criteria

- α = 0.05 family-wise, Bonferroni-corrected within each hypothesis.
- Confirmatory: H1, H2, H3, H4 above.
- Exploratory (declared but not formally tested): correlation between confidence-field self-reports and survival rate; differential survival across mechanism types (CL vs. world model vs. embodied).

## 10. Exclusion criteria

- Cards with `confidence="low"` are included in primary analysis (transparency). A pre-specified sensitivity analysis excludes them.
- Decisions that cite zero cards from any system are excluded from per-card metrics but included in per-decision baselines.
- The 40-day window starts at card-acceptance time, not extraction time, to align with the closed-loop philosophy.

## 11. Stopping rule

No interim analyses. All data collection completes by Wk 9 (2026-07-13). Analysis begins Wk 10. No data collection or hypothesis revision after Wk 9.

## 12. Deviations protocol

Any deviation from this pre-registration must be documented in the paper with: (a) what changed, (b) why, (c) what the original-protocol result would have been if computable. Deviations move the affected hypothesis from confirmatory to exploratory.

## 13. Files & artifacts

- Code: `https://github.com/wjlgatech/neuro-os` (will be anonymized for double-blind via `https://anonymous.4open.science/`)
- Corpus: `research_practice/inbox/` + `tests/fixtures/research/gold/` (gold cards) + `tests/fixtures/research/outcomes/` (40-day labels)
- Pre-reg link (this document, once submitted to OSF): [TBD — paste OSF DOI here after submission]

---

## Submission checklist

- [ ] All four hypotheses (H1–H4) explicitly numbered and falsifiable
- [ ] Statistical tests pre-specified with α and corrections
- [ ] Corpus and decision-source ratio frozen
- [ ] Co-author affiliation added (post Wk 2)
- [ ] OSF submission timestamped before Wk 4 (first experiment run)
- [ ] Submission DOI/link saved here for paper citation
