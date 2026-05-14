# Phase 1 — NeurIPS 2026 Workshop Targets

> **Status as of 2026-05-12:** NeurIPS 2026 workshop applications close 2026-06-06. Accepted workshop list typically announced **August 2026**. We can't submit yet — we can only identify *likely* targets based on NeurIPS 2025 precedent and topic fit. Re-check the official accepted-workshops page in Wk 12 (early August) when the list publishes.
>
> **Strategy:** rank-order workshops by fit. Submit our workshop version (4–8 pages, distilled from arXiv preprint) to the #1 target. Keep #2 and #3 as warm fallbacks.

---

## Tier A — Direct topic match (highest fit)

### Target 1: Embodied World Models for Decision Making (likely returning for 2026)

**NeurIPS 2025 site:** `https://embodied-world-models.github.io/` — ran at NeurIPS 2025.

**Why it's #1 fit:**
- Workshop scope explicitly covers: "integrating perception with control, sim-to-real transfer, **continual learning and adaptation**, and deploying agents in open-ended tasks."
- The MechanismCard schema operationalizes "what a world model has learned about a domain" — directly relevant to their interest in evaluation of world models.
- 2025 organizers likely include researchers who would be strong external reviewers / endorsers for Phase 3 moonshot (`[[goal-neurips-2027-best-paper]]`). Workshop = pre-Phase-3 networking surface.

**Workshop version of our paper:** retitle to *"Mechanism Survival for World-Model Eval: A Closed-Loop Methodology"* and emphasize the embodied / world-model angle (~30% of the paper's content; we'd reweight to ~60% for this venue).

**Monitoring action:** check `embodied-world-models.github.io` weekly starting Wk 10 (mid-July) for 2026 announcement.

---

### Target 2: AI That Keeps Up (CCFM): Continual and Compatible Foundation Model Updates (likely returning for 2026)

**NeurIPS 2025 page:** `https://neurips.cc/virtual/2025/workshop/109584` — ran at NeurIPS 2025.

**Why it's strong fit:**
- Scope: "cost-effective methods for frequent updates and adaptation, minimizing forgetting and deterioration, ensuring a consistent user experience, and **designing dynamic evaluations that remain relevant as models evolve**."
- That last phrase is exactly what mechanism survival measures.
- Continual learning angle aligns with three of our N=10 corpus papers (EWC, Latent Replay, GEM).

**Workshop version of our paper:** retitle to *"Override-Rate as a Continual-Learning Eval Metric for AI-Assisted Research"* and lean hard on the override-trajectory hypothesis (H2). Foundation-model framing rather than research-assistant framing.

**Monitoring action:** check NeurIPS 2026 workshop announcement (mid-August) for CCFM 2026.

---

## Tier B — Adjacent topic match (medium fit; backup)

### Target 3: ML for the Physical Sciences (ML4PS) (annual workshop, runs every NeurIPS)

**NeurIPS 2025 site:** historical "Machine Learning and the Physical Sciences" workshop.

**Why it could work:**
- Construction-site framing (Phase 3 moonshot) + drug-metabolism transferability example (`omegapath`) both qualify as "physical sciences" if we frame the paper around the methodology being domain-portable.
- ML4PS values reproducibility and dataset releases — both core to our submission.

**Why not Tier A:**
- The workshop is biased toward physics/chemistry/astronomy applications. Our research-assistant framing is a stretch.
- Better suited to Phase 3 (the construction-site paper) than Phase 1.

**Decision:** submit only if Targets 1 and 2 don't materialize for 2026.

---

## Tier C — Speculative / not yet confirmed

These NeurIPS 2025 workshops *might* have a 2026 successor that fits us; needs verification when the 2026 list publishes.

- **Foundation Models for Science / Scientific Machine Learning** — if it runs, our research-assistant angle fits.
- **Evaluation of Generative Models** — if it widens scope to include extraction/structured-output eval.
- **AutoML / Meta-Learning** — only relevant if our skillify-prior section is highlighted.

**Decision:** add to monitoring list, don't plan around.

---

## What goes in the workshop version (8-page max)

**Cut from the full paper:**
- Most of related work (workshop reviewers know the field)
- Detailed ablations (mention results, defer full table to appendix)
- Provenance audit deep dive (state the structural argument, don't elaborate)

**Keep / strengthen:**
- The mechanism-survival framing (this is what differentiates us)
- One headline result per hypothesis (H1, H2)
- The closed-loop architecture diagram
- The MechanismCard schema (it's the contribution that ports across venues)
- A "future work" section that explicitly points at Phase 3

**Anonymization:** workshop versions are typically NOT double-blind (or have lighter review). Confirm per-workshop. If single-blind: we can include author names + repo links, which boosts world-os traffic. If double-blind: same anonymization as ICLR submission.

---

## Decision tree

```
Aug 2026: NeurIPS 2026 workshop list announced
  │
  ├── Embodied World Models 2026 accepted?
  │     ├── YES → submit workshop version to Target 1 (highest priority)
  │     └── NO  → ...
  │
  ├── CCFM 2026 accepted?
  │     ├── YES → submit workshop version to Target 2
  │     └── NO  → ...
  │
  └── Neither accepted?
        ├── ML4PS confirmed? → submit Tier B version
        └── Otherwise        → skip the workshop track; arXiv + ICLR cover the bases
```

---

## What to do in Wk 1 (this week)

1. **Bookmark** `https://neurips.cc/Conferences/2026/CallForWorkshops` and `https://blog.neurips.cc/category/2026-conference/` — these are the official announcement channels.
2. **Email Target 1 and Target 2 organizers from NeurIPS 2025** with a polite "are you planning to run this in 2026?" inquiry. Lead time helps if they're undecided.
3. **Don't write the workshop version yet** — it derives from the arXiv preprint (Wk 11). Premature drafting risks duplicated effort if the venue list shifts.

---

## Files & links

- NeurIPS 2026 Workshops CFP: `https://neurips.cc/Conferences/2026/CallForWorkshops`
- 2025 Embodied World Models: `https://embodied-world-models.github.io/`
- 2025 CCFM: `https://neurips.cc/virtual/2025/workshop/109584`
- NeurIPS 2026 blog (announcement channel): `https://blog.neurips.cc/category/2026-conference/`
