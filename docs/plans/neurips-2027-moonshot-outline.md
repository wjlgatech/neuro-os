# NeurIPS 2027 Moonshot Outline — Continual World Models for Embodied Agents on Construction Sites

> Phase 3 of a two-phase arc. Phase 1 = `phase-1-mechanism-survival-paper.md` (mechanism-survival eval, 5-month plan, ICLR 2027 primary + arXiv-first + NeurIPS 2026 workshop side tracks). Phase 3 = this doc — the methods paper targeting **NeurIPS 2027 main track, Best Paper consideration**.
>
> Working title: **"Build-Site Brains: A Continual World-Model Substrate for Embodied Agents in Physical Environments"**
>
> Alternative: *"Compressed Memory, Imagined Rollouts, On-Site Adaptation: Unifying Continual Learning and World Models for Physical AI"*
>
> Domain wedge: **construction sites** (per `research_practice/README.md` framing — ProCore design-to-reality OEC loop).
>
> Status: outline-only. Quarterly milestones, not daily ones — this is 12-month work.

---

## 0. The thesis sentence

World models (Ha & Schmidhuber 2018 lineage) and continual learning (Kirkpatrick 2017 lineage) have been studied in parallel for a decade and never properly unified. We introduce a single architecture that **compresses memory, imagines rollouts, and adapts on-site without catastrophic forgetting**, validated on (a) standard CL benchmarks, (b) standard world-model benchmarks, and (c) a new construction-site benchmark we release. Mechanism survival (Phase 1 paper) is the methodology by which we justify every architectural choice.

---

## 1. The gap nobody has filled

Three lines of work:

1. **World models** (Ha & Schmidhuber 2018, Dreamer v1/v2/v3, MuZero, IRIS): learn a compressed generative model of the environment; train policies inside imagination. **Limitation:** assume stationary distribution. Catastrophic forgetting under distribution shift is unexamined.

2. **Continual learning** (EWC, GEM, A-GEM, latent replay, modular networks): protect prior-task knowledge while learning new tasks. **Limitation:** evaluated almost entirely on classification benchmarks. World-model dynamics, imagination, and on-policy adaptation are out of scope.

3. **Embodied / physical AI** (RT-2, Open X-Embodiment, Voyager, Diffusion Policy): foundation-model-flavored policies for robotic control. **Limitation:** rely on massive pretraining and freeze at deployment. No on-site adaptation. No memory consolidation. No imagination-driven exploration.

The gap: **no architecture handles compressed memory + predictive imagination + on-site adaptation simultaneously**, and no benchmark forces it to.

Construction sites are the cleanest forcing function: the world changes daily (work proceeds, materials move, weather alters appearance), the agent must keep its model current, *and* yesterday's understanding of pillar-foundation-roof relationships must not be erased by today's lighting change.

---

## 2. The architecture (working sketch)

**Three components, one substrate:**

1. **Encoder E (VAE-style, with EWC-protected weights):** Compresses observations to latent `z`. Fisher information accumulates per-pixel-region. High-Fisher weights are protected against further updates.

2. **Dynamics model M (RNN/transformer, with latent replay buffer):** Predicts `z_{t+1} | z_t, a_t`. Trained against rollout traces. The replay buffer stores frozen-encoder latents (Pellegrini 2019) for offline consolidation — never raw frames.

3. **Controller C (small policy, trained mostly in imagination):** Policy lives in the imagined world. Real-world rollouts are used only to (a) update Fisher estimates for E, (b) detect prediction errors that trigger memory consolidation, (c) flag "novelty events" that the dashboard surfaces to a human operator.

**The closed loop (OEC, inherited from `flywheel`):**
```
Observe (E):  encode current site state
Evaluate (M): predict next state; compute prediction error
Control (C):  act; update Fisher estimates on E for high-error regions
Validate:     consolidate to replay buffer if drift > threshold
              emit override event to skillify if human disagrees
```

This is the **research-os mechanism extraction principle, instantiated in weights instead of cards**.

---

## 3. Why this could win Best Paper

NeurIPS Best Paper criteria (informally): (1) novel core contribution, (2) strong empirical results across multiple settings, (3) broad impact / opens a new direction, (4) clear writing, (5) reproducible.

Our case:

1. **Novelty:** First architecture to unify the three threads. Each component is borrowed; the synthesis is new. The literature has been asking for this since 2019 (e.g., Lesort 2020 survey explicitly flags it as open).
2. **Empirical breadth:** Three benchmark families — CL classics, world-model classics, **+ a new construction-site benchmark we release**. The third is what differentiates us from a thousand "we tried X + Y" papers.
3. **Broad impact:** Physical AI is the loudest open area in ML (Tesla Optimus, Figure, 1X, RT-2). A continual-learning substrate for it is leverage on a huge surface.
4. **Writing:** Phase 1 establishes our voice (eval-methodology-led). Phase 3 inherits it.
5. **Reproducibility:** `world-os` repo (spin-off of `neuro-os`) is the artifact. Phase 1 already establishes the test harness.

The single biggest risk: **construction-site data acquisition**. Without it, we have a strong but not Best-Paper paper. The next section is about closing that risk.

---

## 4. Construction-site benchmark — the gating risk

**What we need:**
- ~10 distinct sites OR ~10 distinct construction phases of one site
- Per-site: RGB video (or sparse photos), IMU traces if available, scheduled milestones (foundation poured, framing complete, drywall up), and as-built deviation annotations.
- Total: ~100 hours of footage with metadata.

**Acquisition paths, ranked:**

1. **Partnership with ProCore or a construction-tech vendor** (preferred). They have the data, an academic-research carve-out is plausible, and a published benchmark would be marketing for them. Outreach plan: Q3 2026, leverage Paul's ProCore connection (per `research_practice/README.md`).
2. **Public construction-progress datasets** (Site2Vec, CIS-BIM, OpenConstruction). Smaller, fragmented, but real and legal. Faster path; weaker headline.
3. **Synthetic via Unreal Engine + UE construction asset packs.** Fastest. Weakest publication story but useful for v0 architecture validation while we negotiate real data.

Realistic plan: **synthetic (Q3) → public (Q4) → real partnership (Q1 2027)**, with each phase de-risking the next.

If the partnership falls through entirely: pivot the domain to **industrial robotics via Open X-Embodiment** (the fallback domain we already discussed). The architecture survives the domain pivot; the construction wedge is the differentiator, not the substrate.

---

## 5. Quarterly milestones (12-month plan)

| Quarter | Track | Deliverable |
|---|---|---|
| **Q3 2026** (Jun–Aug) | Architecture | Sketch v0; implement in `world-os` repo; v0 results on DMC + Stream-51 |
| **Q3 2026** | Data | Stand up synthetic Unreal pipeline; collect 20 hours synthetic site video |
| **Q3 2026** | Outreach | ProCore conversation; public dataset survey; identify Q4 dataset target |
| **Q4 2026** (Sep–Nov) | Architecture | v1 with ablations (− Fisher, − replay buffer, − imagination); v1 results on full benchmark trio |
| **Q4 2026** | Data | Stand up public-dataset training pipeline; ProCore partnership decision point |
| **Q4 2026** | Brand | Launch `world-os` on HN/LinkedIn timed to NeurIPS 2026 acceptance notification |
| **Q1 2027** (Dec–Feb) | Architecture | Real construction-site data results; emergent capability ablations |
| **Q1 2027** | Co-authors | Lock co-author commits with prior NeurIPS oral; one with robotics/embodied AI lab |
| **Q2 2027** (Mar–May) | Writing | Draft full paper; supplementary; reproducibility script; anonymize |
| **May 2027** | Submit | NeurIPS 2027 abstract + full paper |
| **Sep 2027** | Reviews | Rebuttal; if accepted, target oral/spotlight track |
| **Dec 2027** | Award | NeurIPS 2027 in-person; Best Paper announcement |

---

## 6. Resources & budget (rough)

| Item | Estimate |
|---|---|
| Compute (training + ablations) | $8k–$15k cloud GPU credits (A100/H100 hours) |
| Construction-site data acquisition | $0 (partnership) — $5k (paid labeling for public datasets) |
| Synthetic data pipeline (Unreal assets + render time) | $1k–$3k |
| Co-author honorarium / paid annotator | $1.5k–$3k |
| Conference travel (NeurIPS 2027 in-person) | $3k–$5k |
| **Total** | **~$15k–$30k over 12 months** |

Funding paths: (a) personal investment, (b) Anthropic / OpenAI compute credit programs, (c) NSF SBIR Phase I if construction-site safety angle is framed appropriately, (d) ProCore in-kind partnership if it happens.

---

## 7. How this paper compounds with the rest of the portfolio

| Asset | Phase 3 lift |
|---|---|
| `flywheel` | Cited as substrate philosophy; OEC framing is its contribution. Possible co-presentation depending on co-author. |
| `neuro-os` | Substrate that runs the experiments. Cited as system; not the paper itself. |
| `world-os` | The paper's repo. The artifact recruiters and researchers actually use. |
| `omegapath` | Mentioned as parallel transferability demo (drug-metabolism domain) — proof that the substrate generalizes beyond construction. |
| `company-os` | Out of scope for the paper but the brand thread (love12xfuture) connects them. |
| Phase 1 D&B paper | Eval methodology (mechanism survival) provides the justification framework for every architectural choice in Phase 3. **Cite Phase 1 prominently.** |

---

## 8. Open questions to resolve before Q3 2026

1. **Co-author profile**: who has prior NeurIPS orals + lab in embodied AI / continual learning? Top candidates to identify by Sept 2026.
2. **Construction-site partnership feasibility**: ProCore outreach lead must be made by July 2026.
3. **Synthetic data quality threshold**: how much synthetic-only validation is enough to ship a v0 paper draft to friendly readers by end of Q4?
4. **Phase 1 paper outcome**: does the D&B paper get accepted? Acceptance accelerates Phase 3 credibility; rejection means Phase 3 must stand fully on its own.
5. **Brand/repo cadence**: how aggressively do we promote `world-os` before the paper is in review (signaling risk)?

---

## 9. Reading list to build through Q3 2026

Tier 1 (must read & extract MechanismCard):
- Ha & Schmidhuber 2018 — World Models (Phase 1 starter)
- Kirkpatrick 2017 — EWC (Phase 1 starter)
- Pellegrini 2019 — Latent Replay (Phase 1 starter)
- Hafner 2023 — Dreamer V3
- Micheli 2023 — IRIS (transformer world models)
- Lesort 2020 — Continual Learning of Real-World Models (the survey that flags our gap)
- Open X-Embodiment 2023

Tier 2 (read & cite, no full extraction):
- Schwarz 2018 — Progress & Compress
- Aljundi 2019 — Online CL with memory writers
- Brohan 2023 — RT-2
- Mendonca 2023 — embodied world models

Tier 3 (skim for related-work coverage):
- Survey papers in CL (Parisi 2019, De Lange 2022)
- Survey papers in world models (Sutton 1990 → present)
- ProCore + construction-tech industry reports

The Tier 1 set IS Phase 1's gold-card corpus. Phase 1 work doubles as Phase 3 preparation.

---

## Next moves (after Phase 1 submits on Day 13)

1. Inventory `world-os` extraction surface: what subset of `neuro-os/agent/` packages cleanly as a Physical-AI-focused repo?
2. Confirm ProCore contact path is still live.
3. Set up `world-os` repo skeleton with README, license, install path, and first demo (synthetic site rollout).
4. Schedule architecture-sketch deep-work sessions for June–August 2026.
5. Begin Tier 2 / Tier 3 reading; extend `research_practice/` accordingly.
