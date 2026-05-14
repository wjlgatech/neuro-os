# Layer 1 Extraction — Lopez-Paz & Ranzato 2017 (GEM)

## Paper Metadata
- **Title:** Gradient Episodic Memory for Continual Learning
- **Authors:** David Lopez-Paz, Marc'Aurelio Ranzato
- **Year:** 2017
- **Venue:** NeurIPS 2017
- **arXiv:** arXiv:1706.08840
- **Date processed:** 2026-05-12

## Core Claim
A new task's gradient is *safe* if it doesn't worsen loss on any stored old-task example — and if a proposed gradient violates that, you can project it onto the nearest "safe" gradient by solving a tiny QP.

## Underlying Mechanism
Per-task episodic memory `M_t` stores a subset of raw examples from each past task. At each step, compute the gradient `g` on the current example and the gradients `g_k` on each stored memory. If `⟨g, g_k⟩ ≥ 0` for all k, accept `g`. Otherwise solve a quadratic program in `t-1` dimensions (one per past task) to find `g̃` — the closest vector to `g` satisfying the inequality constraints — and apply that instead. This is a *hard constraint* on plasticity, in contrast to EWC's soft penalty, and it preserves positive backward transfer (`g̃` can still *improve* old-task loss).

## First Principle
Constraint-based plasticity beats penalty-based plasticity when you can directly observe what "old performance" means via stored examples. The constraint is exact (linear in gradient space); the penalty is a Laplace approximation.

## Anti-Pattern
Treating GEM as "just another regularizer." The gradient projection is a hard inequality constraint, not a soft penalty — semantically different from EWC. Also: confusing GEM's storage of raw examples with the storage-free promise of EWC; GEM *is* rehearsal at the gradient level.

## Transferability Test
- **Physical AI / construction:** Yes — a continual perception model could store small per-day mini-datasets of "what the site looked like" and constrain new-day gradients to not worsen yesterday's predictions.
- **Outside Physical AI:** Hard-constraint optimization in general (KKT conditions, projected gradient methods). Multi-objective RL where each old reward is a constraint.
- **Non-technical:** Employee skill training — don't degrade current competencies while adding new ones (the constraint version). Org change management — keep institutional commitments as inequality constraints during reorg planning.

Transfers to all three. **Not a local optimization.**

## Connection To OEC
- [x] Observation — gradient inner products `⟨g, g_k⟩` ARE the sensors for "would this update hurt old tasks."
- [x] Evaluation — the inequality check IS delta-detection on past-task safety.
- [x] Control — Feedback — the QP projection IS feedback control on the gradient direction.
- [x] Continual loop — runs every step, not just at task boundaries; finer-grained than EWC.

## Verdict
- [x] **Foundational** for the CL methods space; useful as a Phase 1 baseline mechanism

Reasoning: GEM is the canonical "constraint" CL method, distinct from EWC (penalty) and Latent Replay (storage). Phase 1's N=10 corpus needs this mechanism diversity. Likely Phase 1 baseline B-extension for ablation against EWC.

## One-Sentence Compression
Constrain new-task gradients to have non-negative inner product with stored old-task gradients, projecting them onto the safe cone via a tiny QP when violated — turning EWC's soft "don't forget" penalty into a hard "don't get worse" constraint.

## Two-Builder Cross-Pollination
The builder's lesson: when you can store *examples* of what mattered (not just summaries), you can phrase change requests as inequality constraints rather than penalty trade-offs. In a startup: "don't worsen current customer NPS while shipping new features" is a constraint, not a penalty. The constraint version forces explicit accountability; the penalty version invites trade-off rationalization.

## Open Questions
- Does GEM scale to dozens of tasks? The QP is in `t-1` dimensions, growing with task count — O(t²) per step. The paper tops out at ~20 tasks.
- Hybrid: can EWC's Fisher penalty and GEM's gradient constraint coexist? (Schwarz 2018 "Progress & Compress" is the next step.)
- What's the world-model analog? Storing dynamics-prediction gradients per task is unexplored — Phase 3 question.
- Next: A-GEM (Chaudhry 2019) — average-gradient version, dramatically faster.
