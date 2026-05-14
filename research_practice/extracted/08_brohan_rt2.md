# Layer 1 Extraction — Brohan et al. 2023 (RT-2)

## Paper Metadata
- **Title:** RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control
- **Authors:** Anthony Brohan et al. (Google DeepMind, ~40+ authors)
- **Year:** 2023
- **Venue:** arXiv (cited extensively; CoRL 2023)
- **arXiv:** arXiv:2307.15818
- **Date processed:** 2026-05-12

## Core Claim
Treat robot actions as *just another language*: tokenize them as text and co-fine-tune a large Vision-Language Model (VLM) on both web-scale VQA data and robot trajectory data. The unified output space lets web semantic reasoning transfer into low-level robot control — yielding generalization (novel objects, novel instructions) and emergent reasoning (chain-of-thought to pick the right tool) that pure robot-data training cannot match.

## Underlying Mechanism
Start with a pretrained large VLM (e.g. PaLI-X 55B or PaLM-E 12B). Express robot actions as discrete tokens: a 7-DOF action (Δtranslation_3, Δrotation_3, gripper_1) becomes 7 integers, each encoded as a text token (e.g. `"132 114 128 5 25 156"`). Co-fine-tune the VLM on (a) original web VQA tasks and (b) RT-1-style robot trajectories — same model, same parameters, mixed batches. At inference, the model outputs language tokens for VQA prompts and action tokens for robot-control prompts. The unified output format means no new parameters are introduced — all of the VLM's web knowledge stays intact and is available for grounding actions.

## First Principle
When your downstream domain is scarce-data, encode it in the input/output format of an abundant-data pretrained model rather than building a new architecture. Web text is 10⁹+ tokens; robot trajectories are 10⁶ — the only way to leverage the gap is shared format.

## Anti-Pattern
Treating VLA models as "just LLMs that output actions." The co-fine-tuning matters: train only on robot data and you lose the semantic reasoning; train only on web data and you lose grounding. The mixed-objective fine-tuning is the contribution, not the tokenization itself. Also: assuming this scales arbitrarily — physical skills are still bounded by the robot-data distribution; the VLM brings semantic *use* of skills, not new skills.

## Transferability Test
- **Physical AI / construction:** Yes — same recipe applies to embodied construction agents. A VLA model could be co-fine-tuned on (a) general web data + (b) site documentation + (c) trajectory data of equipment operation.
- **Outside Physical AI:** Any scarce-data domain: medicine (use general LLM, encode clinical actions as tokens), finance (encode trades as tokens), biology (encode lab actions as tokens for protein-language models). Even formal verification: encode proof steps as language tokens, leverage general LLM reasoning.
- **Non-technical:** Career switching — leverage abundant general skills (communication, judgment) by encoding domain-specific actions in a "general" frame (resumes, narratives) rather than starting from scratch.

Transfers cleanly to all three. **Not a local optimization.**

## Connection To OEC
- [x] Observation — VLM's vision encoder IS the observation sensor (reuses web-pretrained ViT)
- [x] Evaluation — VQA tasks DURING fine-tuning serve as constant evaluation that semantic skills aren't lost
- [x] Control — Feed-Forward — action tokens ARE direct closed-loop control
- [x] Continual loop — not explicitly; co-fine-tuning is one-shot, not iterative. Open for Phase 3.

## Verdict
- [x] **Foundational** for embodied AI; load-bearing for Phase 3's domain wedge

Reasoning: RT-2 is the dominant paradigm for embodied agents in 2024-2026. Phase 3's construction-site agent will likely either build on RT-2 (use the recipe) or compete with it (offer continual learning that VLA models lack). Either way, must know it deeply.

## One-Sentence Compression
Cast robot actions as text tokens, co-fine-tune a vision-language model on both web-scale VQA and robot trajectory data, and inherit semantic reasoning and generalization that pure robot-data training cannot match.

## Two-Builder Cross-Pollination
The builder's lesson: when your domain has 10⁶ samples and an adjacent abundant domain has 10⁹, the dominant move is interface-shifting (encode your domain in their format) rather than data acquisition. Holds for any startup with thin domain-specific data and an adjacent foundation-model surface — encode your problem as their input/output and leverage their pretrained generalization.

## Open Questions
- VLA models are FROZEN at deployment — they don't adapt on-site. Is that the gap Phase 3 fills? **Yes, this is precisely the moonshot wedge.**
- Inference speed at 55B parameters is brutal for real-time control — what gets sacrificed at 12B or 5B?
- Cross-embodiment: does RT-2 transfer across robots? **Open X-Embodiment answers this** (next paper).
- Emergent reasoning ("use a rock as a hammer") — how robust is it across genuinely novel objects vs in-distribution recombinations?
