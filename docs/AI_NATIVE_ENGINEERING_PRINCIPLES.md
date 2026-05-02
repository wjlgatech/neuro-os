# AI-Native Engineering Principles (Neuro-OS)

> This document defines non-negotiable laws governing the Neuro-OS system.

---

## Law 1: No Raw Knowledge Ingestion

No PDFs, blogs, papers, or repositories are accepted directly into the knowledge base as truth.

Every source MUST be converted into a structured representation before it can influence a primitive.

Required intermediate form:

```text
source -> structured extraction -> evaluation -> accepted knowledge
```

---

## Law 2: Mechanism Over Description

Neuro-OS prioritizes mechanisms, not summaries.

Every accepted concept must answer:

> What generates this behavior?

A descriptive fact is not enough. The system must identify causal structure, update rules, control loops, constraints, and failure modes.

---

## Law 3: Executable Knowledge

Every primitive must include:

- A code experiment
- A mental practice
- A real-world observation task
- A failure case

If the idea cannot be tested, implemented, or practiced, it is not yet Neuro-OS knowledge.

---

## Law 4: Evaluation Before Acceptance

No extracted knowledge enters `/primitives/` unless it passes the evaluation rubric.

Required metrics:

- Compression
- Transferability
- Executability
- Falsifiability

The system must reject or retry low-scoring extractions.

---

## Law 5: Deterministic Outputs Over Prompt Vibes

Pipelines must use fixed schemas and stable output locations.

Preferred formats:

- JSON for structured source extraction
- YAML for golden questions and test fixtures
- Markdown for human-readable architecture and primitives

Same input should produce the same class of output.

---

## Law 6: Explicit Failure Paths

Every agentic step must define:

- Failure condition
- Retry rule
- Rejection rule
- Human escalation path

No silent failures. No vague continuation.

---

## Law 7: Human-In-The-Loop Truth Control

AI can propose knowledge.
The evaluator can score knowledge.
Only the human review gate can approve truth mutation.

No autonomous update to source-of-truth primitives without review.

---

## Law 8: Minimal Primitive Set

Neuro-OS begins with 5 core mechanisms:

1. Predictive Processing
2. Hebbian Learning
3. Reinforcement Learning
4. Attention
5. Hierarchical Abstraction

New concepts must map to one or more of these before a new primitive is created.

---

## Law 9: Continuous Refinement With Versioned Justification

Primitives are living models, not static notes.

Any update must include:

- What changed
- Why it changed
- Which source justified it
- Which eval score changed

---

## Law 10: System Before Content

The system that produces knowledge is more important than the knowledge itself.

Neuro-OS is not a neuroscience archive.
It is a cognitive compiler that turns evidence into executable understanding.
