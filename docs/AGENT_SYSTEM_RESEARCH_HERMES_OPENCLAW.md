# Agent System Research: Hermes, OpenClaw, and Neuro-OS

## Purpose

This document captures external research patterns from Hermes and OpenClaw and translates them into Neuro-OS engineering decisions.

Neuro-OS does not copy their architecture. It adopts the useful operating principles and re-centers them around TRUE + OEC.

---

## External Systems Reviewed

### Hermes Agent

Observed themes:

- Self-improving learning loop
- Agent-curated memory
- Autonomous skill creation
- Skill self-improvement during use
- Cross-session recall
- User modeling
- Tool and terminal backends
- Scheduled automations

Key lesson:

> Persistence alone is not learning. Learning requires experience to become reusable skill.

Neuro-OS interpretation:

- Feedback memory is not enough.
- Experiments must become refinement signals.
- Repeated successful refinements may become reusable TRUE skills.

---

### OpenClaw

Observed themes:

- Local-first autonomous agent runtime
- Human-readable agent configuration
- Gateway/runtime architecture
- Channels and integrations
- Skills/plugins ecosystem
- Model-agnostic execution
- Privacy-first design
- Sandbox and permissions as first-class concerns
- Heartbeat-style autonomous operation

Key lesson:

> Autonomy without governance becomes risk. Governance must live in the runtime, not only in the prompt.

Neuro-OS interpretation:

- Tool access must be scoped.
- Self-modification must use sandbox apply + test + promote/rollback.
- Prompt/rule/tool changes must be observable and versioned.

---

## Design Differences

| Dimension | Hermes | OpenClaw | Neuro-OS |
|---|---|---|---|
| Primary goal | Agent improves with use | Agent executes across tools/channels | Knowledge and system truth evolve safely |
| Memory | Persistent skill/user memory | Local/persistent assistant memory | TRUE decision memory + experiment memory |
| Skills | Creates and improves skills | Installs and runs skills/plugins | Promotes validated mechanisms into reusable truth procedures |
| Runtime | Multi-backend agent runtime | Gateway + channels + tools | OEC control loop + TRUE validation loop |
| Safety | Tool/backend boundaries | Sandbox, permissions, security guide | Sandbox self-modification + metrics gate + rollback |
| Evaluation | Learning loop quality | Operational capability | TRUE survival + system OEC metrics |

---

## Neuro-OS Operating Principle

> Truth is not information. Truth is survivable, usable, repeatable transformation.

> System evolution is not self-editing. System evolution is observable, evaluated, controlled, and validated change.

---

## Engineering Decisions for Neuro-OS

### 1. Observe the whole harness

Observe:

- Source text
- Extracted mechanism
- TRUE scores
- Decision
- Failed dimensions
- Prompt version
- Tool version
- Middleware step
- Runtime errors
- Experiment result

Do not observe only the foundation model.

---

### 2. Evaluate with explicit criteria

Knowledge uses TRUE:

- E: Experienceable / Experimentable
- U: Understandable / Usable
- R: Repeatable / Refinable
- T: Transferable / Transformable

System behavior uses OEC:

- O: Observability completeness
- E: Evaluation correctness
- C: Control precision and validated improvement

---

### 3. Control through bounded changes

Allowed change types:

- Prompt rule update
- Extractor cue update
- TRUE threshold update
- Primitive template update
- Test case addition

Disallowed without human approval:

- Broad autonomous code rewrite
- Removing tests
- Lowering thresholds without justification
- Expanding tool permissions
- Editing source-of-truth primitives without review

---

### 4. Validate before promotion

Every proposed change must compare:

- before accuracy
- after accuracy
- before TRUE score
- after TRUE score
- error count
- failed dimension count
- regression count

Promotion rule:

```text
promote if:
  accuracy improves or stays equal
  TRUE score does not regress
  no new golden-case errors appear
  no safety gate is violated
else rollback
```

---

## Build Target

Neuro-OS should implement a self-modification controller with this loop:

```text
observe logs + golden cases
  -> evaluate behavior
  -> propose bounded control changes
  -> apply to sandbox plan
  -> run validation tests
  -> promote, reject, or require human review
```

---

## Anti-Patterns

- Treating memory as learning
- Letting the model rewrite production files directly
- Trusting self-evaluation without golden tests
- Adding autonomy before observability
- Lowering thresholds to make the system look better
- Equating tool access with intelligence
- Allowing plugins/skills without permission boundaries

---

## Neuro-OS Thesis

Hermes teaches: skill grows from repeated experience.

OpenClaw teaches: autonomous agents need local runtime, tools, and permissions.

Neuro-OS adds: truth and self-evolution must pass TRUE + OEC before being promoted.
