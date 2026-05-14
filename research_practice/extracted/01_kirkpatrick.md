# Layer 1 Extraction — Kirkpatrick et al. 2017 (EWC)

## Paper Metadata

- **Title:** Overcoming catastrophic forgetting in neural networks
- **Authors:** Kirkpatrick, Pascanu, Rabinowitz, Veness, Desjardins, Rusu, Milan, Quan, Ramalho, Grabska-Barwinska, Hassabis, Clopath, Kumaran, Hadsell
- **Year:** 2017
- **Venue:** PNAS 114(13):3521–3526 (also arXiv:1612.00796v2, Jan 2017)
- **arXiv / DOI:** arXiv:1612.00796 / 10.1073/pnas.1611835114
- **Reading time:** ~2 hours
- **Date processed:** 2026-05-12

────────────────────────────────────────────────────────────────────

## Core Claim (one sentence, plain language)

Neural networks don't have to forget old tasks when they learn new ones — you can keep the old ones intact by slowing down learning *only* on the specific weights that mattered for the old tasks, while letting the rest of the network freely adapt.

────────────────────────────────────────────────────────────────────

## Underlying Mechanism

Over-parameterized neural networks have many weight configurations that solve any given task equally well, so a solution to task B is *likely* to exist in a region near the solution to task A. EWC exploits this by adding a quadratic penalty to the loss for task B, with each weight's penalty stiffness set by the **diagonal of the Fisher information matrix** computed at the task-A solution. Fisher diagonal estimates how sharply the loss curves around each weight — i.e., how much that weight "matters" for the old task. High-Fisher weights get strong springs back to their task-A values; low-Fisher weights are free. The mechanism is **selective plasticity driven by second-order information about the prior loss landscape**, not the weights themselves.

────────────────────────────────────────────────────────────────────

## First Principle

Not all parameters in a learned system are equal: a small subset carry most of the load, and protecting *those specifically* (rather than all uniformly, or none) is what enables continual change without collapse. Importance must be measured by how the system's behavior depends on each parameter — not by the parameter's magnitude or recency.

────────────────────────────────────────────────────────────────────

## Anti-Pattern

The trap is reaching for **uniform L2 regularization** (or weight decay) as a poor-man's EWC — penalize every weight equally to "keep the network from drifting too far." Figure 1 of the paper shows exactly why this fails: uniform penalty preserves task A but starves task B of capacity. The deeper trap: assuming you can identify which weights matter by inspecting *the weights* (magnitude, gradient norm). You can't. You have to inspect *the loss curvature around each weight* — that's the entire point of using Fisher information.

────────────────────────────────────────────────────────────────────

## Transferability Test

- **Inside Physical AI / construction:** Yes. A continual world model on a construction site must remember "the foundation is poured, that's load-bearing" while learning "today's scaffolding is moved." Fisher-protected weights of an encoder are exactly the analog: protect representations of permanent geometry, leave representations of daily changes free.
- **Outside Physical AI (other technical domains):** Yes. (a) LLM fine-tuning: LoRA / adapter methods that freeze the base and learn deltas are spiritually the EWC pattern. (b) Database design: hot-path columns (high access Fisher) should be protected from schema migrations; cold-path columns can be rewritten freely. (c) Codebase refactoring: load-bearing tests / interfaces should be frozen during refactors; helper code can churn.
- **Non-technical domains (people, orgs, decisions):** Yes. (a) Habit change: identify the few daily routines that carry most of your discipline (sleep schedule, morning ritual) and protect *those*, while letting other habits churn freely. (b) Organizational restructuring: institutional-knowledge holders and load-bearing roles are high-Fisher; reorgs that protect those while shuffling everything else succeed where uniform shuffles fail. (c) Product management: the 20% of features that drive 80% of retention are high-Fisher; redesigns must protect them or lose the user base.

Transfers to all three domains. **Not a local optimization.**

────────────────────────────────────────────────────────────────────

## Connection To OEC

- [x] **Observation** — Fisher computation *is* a sensor; it observes which parameters carry information about prior task performance.
- [x] **Evaluation** — The quadratic penalty *is* delta-detection: it measures distance from the prior solution, weighted by importance.
- [x] **Control — Feedback** — Differential plasticity *is* feedback control: each weight's gradient is scaled by its importance, so the system corrects in the directions that don't disturb prior tasks.
- [x] **Continual loop** — This is the canonical continual-learning algorithm. The loop runs once per task switch (Fisher recomputed at the boundary).

Critically: EWC's OEC pattern is **applied to the model's own weights**, not to the external world. That's the meta-move — observation/evaluation/control over your own parameters becomes the substrate for handling distribution shift.

────────────────────────────────────────────────────────────────────

## Verdict

- [x] **Foundational** — load-bearing idea, read deeply, return often

Reasoning: EWC is one of the two anchor citations for Phase 3 of our research arc (`neurips-2027-moonshot-outline.md` §2, component 1 = "EWC-protected VAE encoder"). Without understanding *why* it works (Fisher = second-order loss info, not first-order weight info), the Phase 3 architecture sketch is just word salad.

────────────────────────────────────────────────────────────────────

## One-Sentence Compression

Use Fisher information to figure out which weights actually carry the load for the old task, then constrain *only those* when learning the new — over-parameterized networks have enough slack to find the new solution in the manifold near the old one.

────────────────────────────────────────────────────────────────────

## Two-Builder Cross-Pollination

Don't protect everything equally; identify what's load-bearing and protect *it* differently. In a team: name the institutional-knowledge holders before any reorg. In a codebase: name the load-bearing tests and interfaces before any refactor. In a product: name the features that drive retention before any redesign. The diagonal-Fisher heuristic generalizes: importance is measured by how outcomes change when the thing is perturbed — not by how loud or visible the thing is.

────────────────────────────────────────────────────────────────────

## Open Questions

- The paper's Fig 3C nullspace result shows EWC's Laplace approximation **underestimates parameter uncertainty** — nullspace perturbations harm performance as much as inverse-Fisher perturbations. Would a proper Bayesian neural network (Blundell et al. 2015) fix this, and at what compute cost?
- Can Fisher be computed *online* (running estimate during training) instead of at discrete task boundaries? The Atari experiments waited 20M frames before activating EWC — what does the online version look like?
- **The Phase 3 question:** what's the EWC analog for continual learning of *world models*? The task isn't classification but next-frame prediction; the Fisher information would need to be computed against the dynamics prediction loss, and the encoder vs dynamics-model vs policy split needs to be examined. This paper doesn't answer it — that's our paper.
- How does EWC behave under adversarial distribution shift (task B is the opposite of task A, not merely different)? Likely degrades — Fisher overlap goes to zero, and EWC reduces to disjoint sub-networks.
- Next paper to read because of this: Schwarz 2018 "Progress & Compress" (extends EWC with policy distillation) — already on the Phase 3 Tier 2 reading list.
