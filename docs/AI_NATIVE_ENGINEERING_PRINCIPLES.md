# AI-Native Engineering Principles (Neuro-OS)

> This document defines non-negotiable laws governing the Neuro-OS system.
>
> Each law is tagged with **how it's enforced today**:
>
> * `[ENFORCED-by-test]` — `tests/test_engineering_principles.py` has a corresponding `test_law_N` that fails CI on violation.
> * `[ENFORCED-by-type]` — the Python type system (Pydantic, frozen dataclass, mypy) catches violations at construction.
> * `[ENFORCED-by-runtime]` — an allowlist or sandbox refuses violations at execution.
> * `[ASPIRATIONAL]` — there is no automatic enforcement; the law lives in `CLAUDE.md` as prompt-time guidance only. Violations CAN reach `main` undetected.
>
> If a law is `[ASPIRATIONAL]`, that's an honest tag, not an aspiration to weaken it. It means: design judgment can't be mechanized cheaply; the prompt is the only guardrail.
>
> Audience: this codebase is currently authored by **one human (Paul) plus AI assistants**. Some laws would need stricter enforcement for a multi-author team — see "Roadmap" at the bottom.

---

## Law 1: No Raw Knowledge Ingestion `[ENFORCED-by-type]` `[ENFORCED-by-test]`

No PDFs, blogs, papers, or repositories are accepted directly into the knowledge base as truth.

Every source MUST be converted into a structured representation before it can influence a primitive.

Required intermediate form:

```text
source -> structured extraction -> evaluation -> accepted knowledge
```

**How enforced:** every external input flows through a Pydantic `BaseModel` (e.g. `RawEvent`, `UrgeEvent`, `Priority`, `Contract` in founder_loop; `ResearchPriority`, `InvestmentPriority`, `StartupPriority` in the other three verticals). Bad data raises `ValidationError` at construction. `tests/test_engineering_principles.py::test_law_1_no_raw_ingestion` walks `agent/founder_loop/`, `agent/research/`, `agent/investment/`, `agent/startup/`, `agent/domain_app/` and asserts that any `json.loads`/`open()` reading external state feeds into a Pydantic model before reaching policy or memory.

---

## Law 2: Mechanism Over Description `[ASPIRATIONAL]`

Neuro-OS prioritizes mechanisms, not summaries.

Every accepted concept must answer:

> What generates this behavior?

A descriptive fact is not enough. The system must identify causal structure, update rules, control loops, constraints, and failure modes.

**How enforced:** prompt-time only. `CLAUDE.md` instructs the agent to prefer mechanisms; code review catches violations. **No automatic enforcement** — testing "does this paragraph name a mechanism" requires LLM-as-judge, which is probabilistic and not yet wired in. Violations CAN reach `main`.

---

## Law 3: Executable Knowledge `[ENFORCED-by-test]`

Every primitive must include:

- A code experiment
- A mental practice
- A real-world observation task
- A failure case

If the idea cannot be tested, implemented, or practiced, it is not yet Neuro-OS knowledge.

**How enforced:** the substrate (`agent/domain_app/`) requires every vertical's catalog (`DiagnosisCatalogProtocol`) to expose **exactly 6 named failure modes**, each with **≥1 `ConstructiveExpressionBase` option**. `tests/test_engineering_principles.py::test_law_3_executable_knowledge` walks `agent/founder_loop/data/sublimation_catalog.json` and asserts every `underlying_need` has: ≥1 option (code experiment), a chat surface that can propose it (mental practice), an observable signal in `FounderState` (observation task), and a named entry in `golden_cases.py` (failure case). The substrate-adapter tests in `tests/test_*_substrate_adapter.py` extend the same invariant to research / invest / startup.

---

## Law 4: Evaluation Before Acceptance `[ENFORCED-by-test]`

No extracted knowledge enters `/primitives/` unless it passes the evaluation rubric.

Required metrics:

- Compression
- Transferability
- Executability
- Falsifiability

The system must reject or retry low-scoring extractions.

**How enforced:** the L1 golden gate (`tests/test_adoptions.py::TestGoldenGate`) runs the rubric on every proposed primitive update; failed-rubric updates are rolled back. `tests/test_engineering_principles.py::test_law_4_evaluation_rubric` asserts the gate is wired into `agent/self_evolving_loop.py`. **Note:** for product-layer changes (vertical schemas, queues, catalogs), the equivalent gate is `tests/test_founder_loop_safety.py` for founder_loop plus the 4 nightly metrics on each vertical — same shape, different scope. Cross-vertical reads pass an extra gate (`tests/test_cross_vertical_e2e.py`) that defends the default-private boundary.

---

## Law 5: Deterministic Outputs Over Prompt Vibes `[ENFORCED-by-type]` `[ENFORCED-by-test]`

Pipelines must use fixed schemas and stable output locations.

Preferred formats:

- JSON for structured source extraction
- YAML for golden questions and test fixtures
- Markdown for human-readable architecture and primitives

Same input should produce the same class of output.

**How enforced:** every public class returned from a CLI or `/api` route is a Pydantic `BaseModel` or a `frozen=True` dataclass. `tests/test_engineering_principles.py::test_law_5_deterministic_outputs` walks the public surfaces of all four verticals (`agent/founder_loop/__init__.__all__`, `agent/research/__init__.__all__`, `agent/investment/__init__.__all__`, `agent/startup/__init__.__all__`) plus the substrate (`agent/domain_app/__init__.__all__`) and asserts every exported class is one of those two. Stable on-disk locations live in a single registered set in the same test.

---

## Law 6: Explicit Failure Paths `[ENFORCED-by-test]` (partial — see gap below)

Every agentic step must define:

- Failure condition
- Retry rule
- Rejection rule
- Human escalation path

No silent failures. No vague continuation.

**How enforced:** `tests/test_engineering_principles.py::test_law_6_explicit_failure_paths` walks the `ControlOp` enum and asserts every op has an entry in `policy._inverse()` (rejection rule). The dead-sensor branch in `policy.py` and the Belief-OS-flag branch both escalate to `escalate_to_human`. `urge_log.log_urge_event` rate-limits to 5/day with a configurable per-contract cap (the rejection rule for the urge surface, closing the historical gap from V0).

**Gap to close in v1:** there's no explicit retry rule for transient LLM failures in `predict.py` / `sublimate.py` — they fall back to keyword routing once and don't retry. Tracked in `docs/roadmap.md`.

---

## Law 7: Human-In-The-Loop Truth Control `[ENFORCED-by-runtime]` `[ENFORCED-by-test]`

AI can propose knowledge.
The evaluator can score knowledge.
Only the human review gate can approve truth mutation.

No autonomous update to source-of-truth primitives without review.

**How enforced:** at runtime, the `AUTO_APPLY_DEFAULT = {"continue"}` allowlist refuses any other op without explicit user graduation; the `mutable_paths` allowlist refuses writes outside the per-domain whitelist (`tests/test_self_modification.py::test_patch_op_refuses_paths_outside_allowlist`). `tests/test_engineering_principles.py::test_law_7_human_in_loop` asserts that all four vertical `Domain`s (founder_loop / research / investment / startup) ship with `mutable_paths=[]` (read-only L2) and that `AUTO_APPLY_GRADUATABLE` requires per-user opt-in. Promotion is per-vertical and gated; the founder_loop `/catalog-review` chat surface is the template.

---

## Law 8: Minimal Primitive Set `[ASPIRATIONAL]`

Neuro-OS begins with 5 core mechanisms:

1. Predictive Processing
2. Hebbian Learning
3. Reinforcement Learning
4. Attention
5. Hierarchical Abstraction

New concepts must map to one or more of these before a new primitive is created.

**How enforced:** prompt-time only. The neuroscience ontology in `agent/data/priority_rules.json` pins the 5 mechanisms, but there's no automatic check that NEW primitives proposed by the L1 loop map to one of them. Violations CAN reach `main`. **Status: aspirational by design** — the primitive set is expected to evolve; converting this to `[ENFORCED-by-test]` would freeze ontology growth, which is the wrong tradeoff for a self-evolving system.

---

## Law 9: Continuous Refinement With Versioned Justification `[ENFORCED-by-test]` (commits) `[ASPIRATIONAL]` (formal registry for product-layer)

Primitives are living models, not static notes.

Any update must include:

- What changed
- Why it changed
- Which source justified it
- Which eval score changed

**How enforced:** the pre-commit hook (`.pre-commit-config.yaml` + `scripts/check_commit_message.py`) requires every commit message to contain `What changed`, `Why it changed`, and `Validation` sections. `tests/test_engineering_principles.py::test_law_9_versioned_commit_format` asserts the last N commits on the current branch satisfy the format.

For L1/L2 self-modification (knowledge ontology + patch ops), the formal `versions/version_registry.jsonl` carries the four required fields.

**Gap that's `[ASPIRATIONAL]`:** product-layer schema changes (e.g. adding a field to `NightlySummary`) don't currently write to `version_registry.jsonl`. Git commits are the de facto record. Closing this would mean either extending the registry to cover product-layer schemas, or explicitly amending the law to scope it to L1/L2 only. Tracked in roadmap.

---

## Law 10: System Before Content `[ASPIRATIONAL]`

The system that produces knowledge is more important than the knowledge itself.

Neuro-OS is not a neuroscience archive.
It is a cognitive compiler that turns evidence into executable understanding.

**How enforced:** prompt-time only — this is a design philosophy, not a testable property. Every concrete law (1-9) is in service of Law 10; you can think of Law 10 as the meta-statement of why the others matter.

---

## Law 11: Generated Data Stays Out of the Repo `[ENFORCED-by-test]`

**Rule:** All runtime-generated artifacts (pipeline run traces, SQLite DBs, JSONL logs, compression outputs, proposal files, skill outputs) live in `~/.neuro_os_*/` or another path outside the repository tree. Nothing generated by running the system may be committed to git.

**Why this matters:** The repo is a deterministic description of *how* the system works. User data is what the system *produces*. Mixing them creates three failure modes:
1. Personal research data leaks into a public repo.
2. Git history bloats with high-churn binary/JSON blobs, making bisect and blame useless.
3. Experiments from one machine break `pytest` on another because fixture paths differ.

**Concrete boundary:**

| Belongs in repo | Belongs in `~/.neuro_os_*/` |
|---|---|
| `agent/`, `tests/`, `docs/` source files | `ingestion_runs.jsonl`, `mechanism_cards/`, `compressions/` |
| `tests/fixtures/**` (deterministic, version-controlled) | `runs.db` (SQLite pipeline run registry) |
| Pydantic schemas (shapes) | Actual JSON payloads produced at runtime |
| `.gitignore` itself | Everything matched by `.gitignore` |

**How to stay compliant:**
- All four verticals default their `home` to `~/.neuro_os_*/` — never override `home` to a path inside the repo.
- If a new tool writes output files, add the output directory pattern to `.gitignore` immediately, in the same PR.
- Use `pytest`'s `tmp_path` fixture to redirect vertical homes in tests — never write to `~/.neuro_os_*/` from tests.

**How enforced:** `tests/test_engineering_principles.py::test_law_11` — checks that no `.jsonl`, `.db`, or generated JSON blobs exist under `agent/` or the repo root (outside `tests/fixtures/`).

---

## How the laws map to enforcement layers

```
┌─────────────────────────────────────────────────────────────────────┐
│ L1 prompt-time      Laws 2, 8, 10  (judgment / philosophy)          │
│ CLAUDE.md           — only guardrail when violations are subjective │
│                                                                     │
│ L2 type-time        Laws 1, 5  (input + output structure)           │
│ Pydantic, frozen    — fastest feedback, fail at construction        │
│                                                                     │
│ L3 test-time        Laws 1, 3, 4, 5, 6, 7, 9, 11  (architectural)   │
│ pytest enforcers    — block at CI before merge                      │
│                                                                     │
│ L4 runtime          Law 7  (allowlists, last-line backstop)         │
│ patches, domains    — refuse at execution; no bypass possible       │
└─────────────────────────────────────────────────────────────────────┘
```

Most laws live at multiple layers (defense in depth). The cheapest layer where the law is reliably detectable owns the enforcement; weaker layers are belt-and-suspenders.

## Honest scoring as of `claude/enforce-principles`

| Law | Layer(s) | Status | Enforced today? |
|---|---|---|---|
| 1 No raw ingestion | L2 + L3 | ✅ ENFORCED | Yes — Pydantic at construction + walk-and-assert test |
| 2 Mechanism over description | L1 only | ⚠️ ASPIRATIONAL | No automatic gate; prompt-only |
| 3 Executable knowledge | L3 | ✅ ENFORCED | Yes — catalog walk-and-assert test |
| 4 Evaluation rubric | L3 | ✅ ENFORCED | Yes — golden gate (L1 layer) + safety tests (product layer) |
| 5 Deterministic outputs | L2 + L3 | ✅ ENFORCED | Yes — type system + public-surface walk-and-assert |
| 6 Explicit failure paths | L3 | ⚠️ ENFORCED with gap | Yes for inverse_op + rate-limits; retry rules are still aspirational |
| 7 Human-in-loop | L3 + L4 | ✅ ENFORCED | Yes — allowlists at runtime + walk-and-assert at test time |
| 8 Minimal primitive set | L1 only | ⚠️ ASPIRATIONAL | No automatic gate; prompt-only |
| 9 Versioned justification | L1 + L3 (commits) / L3 (registry, partial) | ⚠️ ENFORCED with gap | Yes for commit-message format; product-layer schema versioning is aspirational |
| 10 System before content | L1 only | ⚠️ ASPIRATIONAL | No automatic gate; meta-philosophy |
| 11 Generated data stays out of repo | L3 | ✅ ENFORCED | Yes — test_law_11 walks agent/ and repo root for stray .jsonl/.db blobs |

**Honest summary:** 6 of 11 fully enforced, 3 partial / with named gaps, 3 aspirational by design (judgment laws). The 3 aspirational laws are not failures — they're correctly tagged as such. The 2 with named gaps are real follow-up work.

---

## Roadmap (when current `[ASPIRATIONAL]` laws should graduate)

### When the team grows past 1 human + AI assistants

- Law 9 commit-message format → **mandatory pre-commit hook** (already drafted as `scripts/check_commit_message.py`; only the audience-trigger is gated).
- Law 7 catalog mutation → **`/catalog-review` chat surface** (currently deferred — see `docs/roadmap.md` LATER section).
- Add an explicit **law-revision reviewer** who is not the author. Single-author self-laws are weakly authoritative; team-author laws need separation of concerns.

### When the principles document itself starts evolving from real CI data

- The 10x design (deferred to v1): **`agent/data/principles_v1.json` as a flywheel `Domain`**. The markdown is auto-generated; the JSON is mutable under `mutable_paths` with golden-case gates; failed enforcers + benign-violation evidence triggers proposed law revisions. This closes the OEC loop on the laws themselves. Tracked in `docs/roadmap.md` LATER.

### Aspirational laws that COULD be mechanized but aren't worth the complexity yet

- Law 2 (mechanism over description) → could be a CI step that runs Claude on the diff and asks "does this commit name a mechanism?" — LLM-as-judge. ~$0.10 per PR. Not worth it until violations actually cost something.
- Law 10 (system before content) → meta-philosophy; not directly mechanizable.

### What I would NOT mechanize even if I could

- Law 8 (minimal primitive set). Freezing the primitive count to 5 contradicts the self-evolving design. The right tag is and remains `[ASPIRATIONAL]`.

---

## How to read this doc as an AI agent

If you are Claude reading this before writing code:

1. Find the law that applies to the change you're about to make.
2. Read its `[ENFORCED-by-X]` tag. That tells you whether your error will be caught automatically (don't worry about it as long as you write reasonable code) or only by the prompt (be more careful).
3. If the law is `[ASPIRATIONAL]`, you ARE the enforcer. There is no test to catch your mistake. Slow down.
4. Run `pytest tests/test_engineering_principles.py -v` before commit. If a test fails, fix the change OR propose a law revision in the same PR — don't silently delete the test.
