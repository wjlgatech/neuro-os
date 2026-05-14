# Layer 1 Extraction — Hafner et al. 2023 (Dreamer V3)

## Paper Metadata
- **Title:** Mastering Diverse Domains through World Models
- **Authors:** Danijar Hafner, Jurgis Pasukonis, Jimmy Ba, Timothy Lillicrap
- **Year:** 2023 (v2 Apr 2024)
- **Venue:** arXiv (later published)
- **arXiv:** arXiv:2301.04104
- **Date processed:** 2026-05-12

## Core Claim
A single fixed hyperparameter configuration of a world-model-based RL algorithm can master 150+ tasks across Atari, ProcGen, DMLab, Minecraft, and control suite — *if* you carefully normalize every loss and target so gradient scales decouple from signal magnitudes.

## Underlying Mechanism
Recurrent State-Space Model (RSSM): encoder maps inputs `x_t` to discrete latents `z_t`; sequence model `h_t = f_φ(h_{t-1}, z_{t-1}, a_{t-1})` predicts recurrent state; dynamics predictor learns `p(ẑ_t | h_t)`. Actor + critic trained purely in imagination (rolling forward h_t, z_t, predicted reward `r̂_t`). The key engineering contribution is a constellation of robustness tricks: (a) **symlog** transformation for reconstruction and value targets, (b) **free bits** to prevent KL collapse in the latent (clip dynamics/representation losses below 1 nat), (c) **categorical critic** with exponentially-spaced bins, (d) **percentile-based return normalization** to stabilize entropy regularization across reward scales, (e) mix categorical encoder/dynamics with 1% uniform noise to keep KL well-behaved. Together they make the same `(η, β, γ, ...)` work across 150+ tasks.

## First Principle
Hyperparameter sensitivity is a symptom of poorly-normalized gradient flow. Solving robustness across domains means making every loss term invariant to the absolute scale of the target — not tuning the loss per domain. The trick scales horizontally (more tasks) AND vertically (model sizes).

## Anti-Pattern
Treating Dreamer V3 as "just a bigger world model." The architecture is largely Dreamer V2; the contribution is the *constellation* of normalization tricks. Skip those and the same architecture fails to converge on harder/diverse domains. The other trap: copying one trick (e.g. symlog) without the others; they synergize.

## Transferability Test
- **Physical AI / construction:** Direct — Phase 3 architecture sketch (`neurips-2027-moonshot-outline.md`) is essentially "Dreamer V3 + continual learning for construction sites." The symlog/free-bits/percentile machinery transfers directly.
- **Outside Physical AI:** Robust optimization in general (Adam's effective per-parameter normalization is spiritually the same). Financial models (normalize returns before optimizing). Reward-shaping research more broadly.
- **Non-technical:** Strategic planning across markets with very different scales — normalize KPIs to comparable ranges before optimizing strategy. Comparative team performance reviews — normalize scope before judging output.

Transfers cleanly to all three. **Not a local optimization.**

## Connection To OEC
- [x] Observation — encoder + RSSM IS the observation pipeline
- [x] Evaluation — dynamics loss + reconstruction loss IS delta-detection on model fidelity
- [x] Control — Feed-Forward — imagined rollouts ARE feed-forward planning at scale
- [x] Continual loop — replay buffer + actor-critic loop runs continuously during interaction

## Verdict
- [x] **Foundational** — direct predecessor to Phase 3 architecture

Reasoning: Dreamer V3 IS the modern face of the Ha & Schmidhuber lineage. Phase 3's world model component must engage with this paper deeply. The normalization tricks are what makes the moonshot achievable rather than a tuning slog.

## One-Sentence Compression
Train an RSSM world model + actor-critic in its imagination, and make the whole stack robust across domains via symlog losses, free bits, percentile-normalized returns, and categorical-binned critics that decouple gradient scale from target magnitude.

## Two-Builder Cross-Pollination
The builder's lesson: when generality across domains is the goal, generality comes from principled normalization, not from per-domain tuning. The Dreamer V3 recipe is "make every signal scale-invariant before training" — a meta-principle. Applies to running a team: when comparing performance across functions, normalize before drawing conclusions; otherwise the high-variance functions dominate the gradient.

## Open Questions
- Can the same normalization tricks be applied to continual learning? Phase 3 question.
- Sample efficiency is still 100K-100M frames. What's the next 10× — better world models or better exploration?
- How does Dreamer V3 fail under distribution shift mid-training? Not studied in the paper; relevant for embodied deployment.
- Next: IRIS (Micheli 2023) for transformer-based alternative; Mendonca 2023 for embodied extensions.
