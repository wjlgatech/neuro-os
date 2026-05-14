# Starter Papers — Manifest

These three papers are the minimum viable version of the Research OS.
Together they cover the three OEC dimensions (memory, prediction, online
learning) using three completely different mechanisms (regularization,
generative simulation, latent rehearsal). If the framework can extract
transferable principles from these three, it works on anything.

────────────────────────────────────────────────────────────────────

## Paper 1 — Continual Learning Anchor

**Citation**
Kirkpatrick, J., Pascanu, R., Rabinowitz, N., Veness, J., Desjardins, G.,
Rusu, A. A., Milan, K., Quan, J., Ramalho, T., Grabska-Barwinska, A.,
Hassabis, D., Clopath, C., Kumaran, D., & Hadsell, R. (2017).
Overcoming catastrophic forgetting in neural networks.
*Proceedings of the National Academy of Sciences*, 114(13), 3521–3526.

**Links**
- arXiv:    https://arxiv.org/abs/1612.00796
- PDF:      https://arxiv.org/pdf/1612.00796
- PNAS:     https://www.pnas.org/doi/10.1073/pnas.1611835114

**Why this paper**
The EWC paper. Most-cited modern CL paper. Every CL paper since 2017 either
builds on it or argues against it. Without this, you can't read the field.

**Mechanism in one sentence**
Estimate which neural network weights matter for the old task (via Fisher
Information), then penalize changes to those weights when training on the new.

**First principle to extract**
Not all parameters are equal — protect load-bearing ones, leave the rest free.

**Reading time** ~2 hours (6 pages of main content + supplementary)

────────────────────────────────────────────────────────────────────

## Paper 2 — World Models Anchor

**Citation**
Ha, D., & Schmidhuber, J. (2018). World Models.
*Advances in Neural Information Processing Systems (NeurIPS)*, 31.

**Links**
- arXiv:        https://arxiv.org/abs/1803.10122
- PDF:          https://arxiv.org/pdf/1803.10122
- Interactive:  https://worldmodels.github.io   ← READ THIS FIRST

**Why this paper**
The modern world-models paper. THIS is what Thiago was pointing at when he
said "LLMs aren't designed for spatial reasoning, world models are." Cannot
have the next conversation with him without having read this.

**Mechanism in one sentence**
Train a generative model of the environment (VAE + RNN), then train a small
policy inside the imagined world rather than in reality.

**First principle to extract**
Most learning shouldn't happen in reality — it should happen in a compressed
internal model, with reality used only to correct the model.

**Reading time** ~2 hours (interactive version + paper)

────────────────────────────────────────────────────────────────────

## Paper 3 — On-Device CL Anchor

**Citation**
Pellegrini, L., Graffieti, G., Lomonaco, V., & Maltoni, D. (2019).
Latent Replay for Real-Time Continual Learning.
*arXiv preprint arXiv:1912.01100*. Later published in IROS 2020.

**Links**
- arXiv:    https://arxiv.org/abs/1912.01100
- PDF:      https://arxiv.org/pdf/1912.01100
- Code:     https://github.com/vlomonaco/ar1-pytorch
- Code:     https://github.com/lrzpellegrini/Latent-Replay

**Why this paper**
The practical on-device CL paper. If ProCore deploys continual learning on
edge devices (Quest, Halo, custom hardware), this is the architecture they'll
either converge to or have to explicitly argue against.

**Mechanism in one sentence**
Store mid-layer activations (not raw images) for replay; freeze early layers
so cached activations stay valid; only update late layers on-device.

**First principle to extract**
Separate what changes slowly from what changes quickly; only update the fast
layer. Same principle as Context → Modules → Weights.

**Reading time** ~2 hours (~12 pages, clear figures)

────────────────────────────────────────────────────────────────────

## Why These Three Together

                EWC                 World Models          Latent Replay
                ───                 ────────────          ─────────────
Mechanism:      Protect weights     Train in imagined     Replay mid-layer
                                    environments          activations

First Princ.:   Not all params      Most learning in      Separate slow- from
                are equal           compressed model      fast-change layers

OEC Layer:      Continual           Feed-forward          Continual
                (memory)            Control               (on-device)

Transfers to:   Identity, habits,   Strategy, planning,   Architecture,
                org structure       simulation, coaching  timescales

────────────────────────────────────────────────────────────────────

## After You've Processed These Three

Add to inbox/ next (in roughly this order):

- Lomonaco & Maltoni (2017) — CORe50 benchmark
- Hayes & Kanan (2022) — Online CL for Embedded Devices
- Wang, Zhang, Su, Zhu (2024) — TPAMI CL survey (the map)
- Khetarpal et al. (2022) — Continual RL review (the map for policies)
- LeCun (2022) — A Path Towards Autonomous Machine Intelligence
- Hafner et al. — DreamerV3 (modern world model that actually works on real tasks)

But do not download any of these until you have completed Layer 3 on the
first three. Stop-condition first, scale second.

────────────────────────────────────────────────────────────────────

## N=10 CORPUS LOCKED (2026-05-12) — Phase 1 paper experimental set

For the NeurIPS-track Phase 1 mechanism-survival paper, we extended the starter
3 to a locked N=10 corpus that surfaces maximally-distinct mechanisms across
continual learning, world models, embodied AI, and eval methodology. The full
list, with one-line rationale for inclusion:

### Continual learning (3 mechanisms, 3 papers)
1. **Kirkpatrick 2017 (EWC)** — regularization-penalty CL (anchor #1)
2. **Pellegrini 2019 (Latent Replay)** — storage-rehearsal CL (anchor #3)
3. **Lopez-Paz & Ranzato 2017 (GEM)** — gradient-constraint CL
4. **Rusu et al. 2016 (Progressive Networks)** — architecture-growth CL

### World models (3 mechanisms, 3 papers)
5. **Ha & Schmidhuber 2018 (World Models)** — V+M+C with policy in imagination (anchor #2)
6. **Hafner et al. 2023 (Dreamer V3)** — RSSM at scale with robust normalization
7. **Micheli et al. 2023 (IRIS)** — discrete-token transformer world model

### Embodied AI (2 papers — Phase 3 wedge)
8. **Brohan et al. 2023 (RT-2)** — vision-language-action via action-as-token
9. **Open X-Embodiment Collaboration 2023** — cross-embodiment dataset + RT-X

### Evaluation methodology (1 paper — Phase 1 framing anchor)
10. **Liang et al. 2022 (HELM)** — top-down (scenario × metric) taxonomy for LM eval

### Why these ten together (mechanism diversity matters more than topic coverage)

The three CL mechanisms (penalty / storage / constraint / architecture) demonstrate
that the same problem admits structurally different solutions. The three world-model
papers span generative-RNN / RSSM / Transformer for the same prediction task.
RT-2 and OXE represent the modern embodied paradigm Phase 3 must engage with.
HELM is the methodology anchor — our paper IS a HELM for AI research assistants.

If the MechanismCard schema can extract distinct, transferable mechanisms across
all ten, the schema is doing its job. That's the structural argument for our
paper: a sufficient schema captures the field's structure, not just its content.

Companion gold fixtures (Pydantic-validated MechanismCards) live in:
`/Users/jialiang.wu/Documents/Projects/neuro-os/tests/fixtures/research/gold/`

Companion Layer 1 extractions (full templates) live in:
`/Users/jialiang.wu/Documents/Projects/research-os/extracted/`

All 10 have verdict=foundational (deliberate — the gold set is the load-bearing
subset; lighter verdicts come later as the corpus expands toward N=30+ for the
ICLR 2027 submission expansion).
