# Layer 1 Extraction — Micheli, Alonso, Fleuret 2023 (IRIS)

## Paper Metadata
- **Title:** Transformers are Sample-Efficient World Models
- **Authors:** Vincent Micheli, Eloi Alonso, François Fleuret
- **Year:** 2023
- **Venue:** ICLR 2023
- **arXiv:** arXiv:2209.00588
- **Date processed:** 2026-05-12

## Core Claim
You can build a sample-efficient world model by *tokenizing* frames into a discrete vocabulary via a VQ-style autoencoder, then modeling the interleaved (frame-token, action-token) sequence with a GPT-like autoregressive Transformer — and a policy trained purely in this Transformer's imagination achieves SOTA on Atari 100k.

## Underlying Mechanism
Two components: (1) **Discrete autoencoder** `E, D` — CNN encoder maps each frame to K tokens from a vocab of N (via vector quantization, like VQGAN); decoder reconstructs. Trained with L1 reconstruction + commitment + perceptual losses. (2) **GPT-like Transformer G** — operates on the interleaved sequence `(z_0^1...z_0^K, a_0, z_1^1...z_1^K, a_1, ...)`. Models three predictive distributions per step: next-frame tokens (autoregressively, including the partial frame already predicted), reward, termination flag. Policy is trained purely in imagination — Transformer rolls forward, decoder turns predicted tokens back into images when needed. Real environment is used ONLY to gather new data for retraining the world model.

## First Principle
When dynamics learning can be cast as sequence modeling over discrete tokens, Transformer scaling properties become exploitable. Discretization isn't always lossy — for dynamics learning it can be a feature (sharper predictions, decoupled vocabulary from continuous representation, autoregressive structure for free).

## Anti-Pattern
Treating IRIS as "Transformers naturally fit world models." Naive pixel-as-token doesn't scale (quadratic context cost). The contribution requires: (a) careful pretrained discrete autoencoder, (b) interleaved sequence format with per-frame token chunks, (c) autoregressive within-frame token prediction. Skip the autoencoder and the Transformer chokes on raw pixels.

## Transferability Test
- **Physical AI / construction:** Yes — site state can be tokenized (zone × object-type discrete vocabulary), and a Transformer can model how the site evolves token-by-token. Phase 3 candidate: IRIS-flavor architecture for construction-site dynamics.
- **Outside Physical AI:** Code generation (programs ARE discrete sequences). Music generation (notes as discrete tokens). Molecular design (SMILES tokens). Any control problem where state can be discretized without losing essential structure.
- **Non-technical:** Planning at any organization where actions and states can be enumerated (e.g. supply chain operations, hospital workflows) — Transformer becomes the predictor of "if this sequence of actions, what state follows."

Transfers cleanly to all three. **Not a local optimization.**

## Connection To OEC
- [x] Observation — VQ encoder IS the observation sensor (discrete latent space)
- [x] Evaluation — Transformer prediction error IS delta-detection
- [x] Control — Feed-Forward — Transformer rollout IS imagined planning at token granularity
- [x] Continual loop — collect → update world model → update policy in imagination → repeat

## Verdict
- [x] **Foundational** for transformer-flavored world models; complements Dreamer V3's RSSM/SSM family

Reasoning: IRIS is the Transformer-side of the modern world-model split (RSSM vs Transformer). Phase 3 may choose either or hybridize. Sample-efficient (~2 hours of gameplay = 100K frames) which matters for any real-world deployment.

## One-Sentence Compression
Tokenize frames into a discrete vocabulary via a VQ autoencoder, then let an autoregressive Transformer model the interleaved frame-token + action-token sequence — turn world-modeling into sequence modeling and inherit Transformer's sample efficiency and long-range coherence.

## Two-Builder Cross-Pollination
The builder's lesson: when you can discretize your domain without losing essential structure, you unlock the entire LLM tooling stack — autoregressive prediction, scaling laws, transfer learning. Worth investing engineering time in finding the right tokenization. In a startup, this maps to: when designing your data schema, prefer enumerated/categorical encodings over free-form text where possible — they enable downstream LLM pipelines that free text cannot.

## Open Questions
- Continuous dynamics (smooth motion) — does discretization quantize away essential structure?
- Quadratic context cost limits imagination horizon — is there a Mamba/SSM hybrid that retains the discrete-token structure but scales linearly?
- IRIS uses 2 hours of gameplay (Atari 100k) — what's the scaling for harder embodied tasks?
- Phase 3 question: VQ encoder + Transformer dynamics + Fisher-protected weights — three threads converging on the moonshot architecture.
