# Layer 1 Extraction — Ha & Schmidhuber 2018 (World Models)

## Paper Metadata

- **Title:** World Models
- **Authors:** David Ha, Jürgen Schmidhuber
- **Year:** 2018
- **Venue:** NeurIPS 2018 (also arXiv:1803.10122v4, May 2018)
- **arXiv / DOI:** arXiv:1803.10122
- **Reading time:** ~2 hours (interactive version at worldmodels.github.io first, then PDF)
- **Date processed:** 2026-05-12

────────────────────────────────────────────────────────────────────

## Core Claim (one sentence, plain language)

Build a generative model of the environment that compresses what the agent sees into a small code and learns to predict the next code — then train a tiny policy *inside that imagined world* instead of in reality, and the policy still works when you drop it back into the real environment.

────────────────────────────────────────────────────────────────────

## Underlying Mechanism

Three components, separately trained: **V** (a Variational Autoencoder) compresses each frame to a 32-dim latent `z`; **M** (an MDN-RNN) models `p(z_{t+1} | a_t, z_t, h_t)` — a probability distribution over next latents conditioned on action; **C** (a tiny linear controller) maps `[z_t, h_t]` to an action, optimized by CMA-ES evolution. The trick is that **most of the model's complexity lives in V+M (world model)**, so the small C only has to solve a much-smaller credit-assignment problem in the compressed latent space. Because M models a *distribution* over next latents (not a point estimate), you can roll forward purely from M's sampled outputs — and the temperature parameter τ controls how uncertain those samples are, which lets you train policies that don't overfit to a perfect dream.

────────────────────────────────────────────────────────────────────

## First Principle

Most learning shouldn't happen in reality — it should happen in a compressed internal model, with reality used only to (a) train the model in the first place and (b) verify the policy when you transfer it back. Reality is the slowest, most expensive, least controllable training environment available; once you have a tolerable predictive model of it, the rest of optimization belongs in imagination.

────────────────────────────────────────────────────────────────────

## Anti-Pattern

The trap is treating "model-based RL" as **a way to make sample-efficient RL by occasionally simulating one or two steps ahead inside an otherwise model-free pipeline** — Dyna-style architectures that still spend most of their wall-clock in real interactions. That's not what Ha & Schmidhuber are claiming. The claim is stronger: the *policy* should live entirely inside the world model. The deeper trap: confusing the model's job (predict the future distribution of compressed states) with the policy's job (choose actions). Each is small individually because they're separated; lump them together and you lose the leverage.

────────────────────────────────────────────────────────────────────

## Transferability Test

- **Inside Physical AI / construction:** Yes. A construction-site agent could train a V on perception data (compress the visual state of a site to a low-dim code), train M to predict how the site evolves under various interventions, and train C purely in imagination to plan multi-step actions (scaffold-here-then-pour-foundation-tomorrow). The actual site is needed only for V/M training data, not for policy search.
- **Outside Physical AI (other technical domains):** Yes. (a) LLM agents: tool-using LLMs that build internal scratchpad models of the API surface and "imagine" tool calls before executing are spiritually doing the same thing. (b) Recommender systems: model user preference dynamics, then optimize content sequences in imagination before pushing to live A/B. (c) Self-play in board games (AlphaGo's MCTS rollouts ARE the dream).
- **Non-technical domains (people, orgs, decisions):** Yes. (a) Mental rehearsal: athletes / surgeons explicitly visualize sequences of actions in compressed mental models before performing. (b) Strategy planning: "tabletop exercises" / scenario planning let teams optimize plans in imagined worlds before committing real resources. (c) Therapy: exposure therapy in imagination precedes real-world exposure.

Transfers cleanly to all three. **Not a local optimization.**

────────────────────────────────────────────────────────────────────

## Connection To OEC

- [x] **Observation** — V's encoder is the observation sensor; it compresses high-D pixels to a 32-D code.
- [x] **Evaluation** — M's prediction error is the evaluation signal: when M's predicted `z_{t+1}` diverges from the actual next observation's `z`, that's the delta-detection signal.
- [x] **Control — Feed-Forward (prediction, planning)** — M *is* the feed-forward predictor; rolling M forward generates the "dream" inside which C is trained.
- [x] **Continual loop** — On-paper, V/M are trained once and frozen; but the paper's appendix discusses iterative refinement, and the more general OEC framing closes the loop by re-training V/M when M's prediction error stays high.

The big OEC contribution: this paper makes **"observation = encoder," "evaluation = prediction-error," "control = imagination-rollout"** concrete as three trainable neural networks. That decomposition is exactly the substrate Phase 3 needs.

────────────────────────────────────────────────────────────────────

## Verdict

- [x] **Foundational** — load-bearing idea, read deeply, return often

Reasoning: World Models is the second of two anchor citations for Phase 3 of our research arc (component 2 of the three-component sketch in `neurips-2027-moonshot-outline.md` §2 = "dynamics model M with latent replay buffer"). Together with EWC (component 1) and Latent Replay (component 3), this paper *is* a third of the moonshot's intellectual debt.

────────────────────────────────────────────────────────────────────

## One-Sentence Compression

Compress observations to a small latent code, learn to predict the next code, and train your policy *entirely in imagination* — reality is just data for the compressor and the predictor, not the place where the policy is searched.

────────────────────────────────────────────────────────────────────

## Two-Builder Cross-Pollination

The lesson for builders: **separate the model of how-the-world-works from the policy of what-to-do**, and let each be small individually because they're decoupled. In a startup, this maps to: build a tight mental model of your market dynamics (V+M), then run cheap strategy experiments in imagination (tabletop exercises, financial models, A/B simulations) before betting real resources. The temperature parameter τ is the analog of "how rigorously to test contrarian scenarios" — a too-confident model dreams a perfect world and produces a brittle plan; a too-uncertain model dreams chaos and produces no plan at all.

────────────────────────────────────────────────────────────────────

## Open Questions

- **Aging of world models under distribution shift:** if the environment changes, V's compressions become stale and M's predictions drift. Ha & Schmidhuber don't address this; **that's exactly the Phase 3 question**.
- The agent in VizDoom can exploit imperfections in M during dream-training (e.g., find adversarial states where M's prediction is wrong). How do you regularize against this? The temperature parameter τ helps but doesn't solve it.
- How would this scale to embodied tasks with real-world physics (slippery floors, partial occlusion, sensor noise) where V's 32-D compression is much harsher? Open X-Embodiment (2023) data is the obvious next test.
- The 867-parameter controller is shockingly small. What's the right size for a continual-learning controller that has to handle a *family* of environments rather than one?
- Next papers to read because of this: Hafner 2023 (Dreamer V3) and Micheli 2023 (IRIS, transformer world models) — both already on the Phase 3 Tier 1/2 reading list.
