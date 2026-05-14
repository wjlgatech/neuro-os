# Layer 1 Extraction — Liang et al. 2022 (HELM)

## Paper Metadata
- **Title:** Holistic Evaluation of Language Models
- **Authors:** Percy Liang, Rishi Bommasani, Tony Lee, and 47 others (Stanford CRFM)
- **Year:** 2022 (v2 Oct 2023)
- **Venue:** TMLR (Aug 2023)
- **arXiv:** arXiv:2211.09110
- **Date processed:** 2026-05-12

## Core Claim
LM evaluation should be **holistic**: (1) make the taxonomy of scenarios × metrics *explicit* so absences are visible, (2) measure many metrics per scenario (accuracy + 6 others) so non-accuracy desiderata aren't relegated, (3) standardize adaptation across models so the model — not the scenario pipeline — is what's evaluated. HELM operationalizes this with 16 core scenarios × 7 metrics = 112 pairs (98 measured) + 7 targeted evaluations on 26 more scenarios + standardized evaluation of 30 prominent LMs.

## Underlying Mechanism
Top-down construction: enumerate the design space of evaluation (scenarios as task×domain×language triples; metrics as a 7-axis taxonomy including accuracy, calibration, robustness, fairness, bias, toxicity, efficiency). Then implement a deliberate subset, *naming what's missing*. Run 30 LMs across the matrix under standardized adaptation. Publish all raw prompts and completions for replication. Before HELM, prominent LMs shared on average only 17.9% of evaluation scenarios; HELM raises this to 96.0% — making side-by-side comparison possible for the first time.

## First Principle
Evaluation is a scientific object of study, not infrastructure. Benchmarks encode values; making those values explicit (the taxonomy) is the first step toward correctable evaluation. Multi-metric measurement reveals trade-offs that single-metric benchmarks structurally hide.

## Anti-Pattern
Treating accuracy as the default evaluation and deferring other desiderata (fairness, toxicity, calibration) to "separate benchmarks." This guarantees the others become second-class citizens. Or: treating a benchmark as canonical without making its taxonomy explicit — you can't tell what's missing if you can't see the design space. The deepest trap: confusing "many benchmarks" with "broad evaluation" when most benchmarks measure overlapping subsets of accuracy.

## Transferability Test
- **Physical AI / construction:** Direct — Phase 1's mechanism-survival eval methodology IS HELM-flavored. Make the taxonomy of (paper × extraction-dimension × downstream-vertical × outcome-metric) explicit; measure many metrics per paper, not just citation count.
- **Outside Physical AI:** Multi-criteria decision analysis (operations research). Medical trial design (efficacy + safety + quality of life as joint outcomes). Any context where a single metric proxies for a multi-dimensional outcome.
- **Non-technical:** Product KPIs (don't just measure DAU; measure DAU × retention × NPS × revenue concurrently). Engineering performance reviews (output × code quality × team impact × growth). Personal goals (career + relationships + health as joint, not sequential).

Transfers everywhere. **Not a local optimization. The most general paper in the corpus.**

## Connection To OEC
- [x] Observation — 30 LMs × 42 scenarios IS a vast observation surface
- [x] Evaluation — the taxonomy IS the evaluation methodology, literally
- [x] Control — Feedback — HELM is meant to *steer* the field (community priorities shift toward measured metrics)
- [x] Continual loop — explicitly "living benchmark" with versioned releases

## Verdict
- [x] **Foundational** — directly aligned with Phase 1's paper framing

Reasoning: HELM is the methodological anchor for Phase 1. We are not building a HELM-for-research-assistants in scope, but we ARE adopting HELM's methodology stance: explicit taxonomy, multi-metric measurement, standardized comparison. Cite HELM prominently in Phase 1's Related Work as the methodological precedent.

## One-Sentence Compression
Build a top-down taxonomy of (scenario × metric) pairs, evaluate every model on every pair under standardized conditions, and expose the trade-offs that single-metric benchmarks structurally hide — turning evaluation itself into a scientific object of study.

## Two-Builder Cross-Pollination
The builder's lesson: when a metric is being used to steer decisions, the right question isn't "is this metric high enough?" but "what's the design space of relevant metrics, what does our current metric set hide, and what trade-offs do we make visible?" The taxonomy-first move applies to any KPI-driven org. Surface the design space before optimizing — most teams optimize blindly inside a metric set they never questioned.

## Open Questions
- HELM is English-centric (acknowledged limitation). What's the cost of multi-lingual extension?
- The taxonomy embeds the authors' values about what matters (the 7 metrics are a choice). Who decides? HELM is "living" — what's the governance?
- Compute cost: running HELM on a new model is expensive and growing. How does the community sustain this?
- Phase 1 question: what's HELM's equivalent for AI research assistants? Our paper is partially the answer — `MechanismCard` schema × (survival, override rate, transferability, provenance) × multiple verticals.
- Next: BetterBench (Reuel 2024) — critique of benchmarks; PromptBench; the BIG-bench critique literature.
