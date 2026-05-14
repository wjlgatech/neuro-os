# Layer 1 Extraction — Rusu et al. 2016 (Progressive Networks)

## Paper Metadata
- **Title:** Progressive Neural Networks
- **Authors:** Andrei A. Rusu, Neil C. Rabinowitz, Guillaume Desjardins, Hubert Soyer, James Kirkpatrick, Koray Kavukcuoglu, Razvan Pascanu, Raia Hadsell
- **Year:** 2016
- **Venue:** arXiv (also cited heavily through 2018+)
- **arXiv:** arXiv:1606.04671
- **Date processed:** 2026-05-12

## Core Claim
You can completely eliminate catastrophic forgetting by *architecture*, not regularization: instantiate a new neural-network column for each task, freeze prior columns, and let the new column receive lateral inputs from the frozen ones via small adapters.

## Underlying Mechanism
For task `k`, instantiate a column with parameters `Θ^(k)`. Each layer `h_i^(k)` takes input from its own previous layer `h_{i-1}^(k)` AND from previous columns' corresponding previous layers `h_{i-1}^(j)` (j < k) through learned adapter MLPs. Prior columns' parameters `Θ^(j)` are FROZEN during task-k training — no gradient flows back to them. Hence: zero catastrophic forgetting by construction. Transfer happens through the adapters, which can choose to reuse, modify, or ignore prior features. Analyzed via Average Fisher Sensitivity (AFS) which shows transfer occurs at multiple depths.

## First Principle
Capacity is cheap; learning is expensive. When you can afford parameter growth, separating tasks structurally is strictly safer than blending them parametrically — and modular reuse via adapters is a separate question from forgetting.

## Anti-Pattern
Treating Progressive Networks as a general continual-learning algorithm. They're really "no-forgetting-by-construction + cheap transfer." The trap: using them when you DO want representation sharing (which architectural separation kills) or when parameter count growth is a constraint (e.g. on-device CL).

## Transferability Test
- **Physical AI / construction:** Yes — a per-site or per-phase neural column with lateral connections to a shared foundation-model column. Different construction phases = different columns.
- **Outside Physical AI:** Microservices architecture (separate service per concern, immutable APIs, transfer via well-defined inter-service calls). Plugin systems (core stays frozen, plugins add capabilities). Mixture-of-experts in modern LLMs.
- **Non-technical:** Org structure — new functions get new teams rather than retraining existing teams (preserves institutional memory). Knowledge management — new domains get new ontologies that reference old ones rather than rewriting the old ones.

Transfers to all three. **Not a local optimization.**

## Connection To OEC
- [x] Observation — adapters from prior columns ARE perceptual sensors trained on prior tasks.
- [x] Control — Feed-Forward — the frozen prior columns ARE feed-forward feature extractors with task-specific specialization.
- [x] Continual loop — but at the *architecture* level, not the parameter level; loop iterations add columns, don't modify them.

## Verdict
- [x] **Foundational** for the architecture-growth CL family; complementary to EWC and Latent Replay

Reasoning: This is the third major CL mechanism (after regularization-EWC and storage-rehearsal-Latent Replay): architectural growth. Phase 1's N=10 corpus needs this diversity. Worth knowing the AFS sensitivity analysis maps directly to Fisher-based weight importance (Kirkpatrick 2017 + Rusu 2016 share authors).

## One-Sentence Compression
Spin up a new neural network column per task, freeze prior columns, and learn cheap lateral adapters to reuse prior features — make forgetting structurally impossible by trading parameter count for plasticity.

## Two-Builder Cross-Pollination
The builder's lesson: when forgetting is unacceptable and parameter growth is acceptable, architectural separation > weight regularization. In a startup: when a new business line is genuinely orthogonal to existing ones, spin up a new team with lightweight integrations rather than retraining the existing team. Microservices vs monolith decision is structurally the same.

## Open Questions
- Parameter count is linear in tasks — when does growth become prohibitive?
- Choosing which column to use at inference requires task label — how is this resolved in open-world deployment?
- Modern alternative: mixture-of-experts with sparse routing achieves similar separation with shared parameter budget. Is Progressive Networks just an MoE in disguise?
- Phase 3 question: can a world model be progressive — one V/M per environment family, lateral connections to share dynamics primitives?
