# CLAUDE.md — operating manual for AI agents working in this repo

> If you're a Claude (or other LLM) about to write code in this repo,
> read this first. The non-negotiable laws are in
> [`docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md`](docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md).
> The deterministic gate is `tests/test_engineering_principles.py`.

## Audience

This codebase is currently authored by **one human (Paul) plus AI assistants**. Enforcement is calibrated for that case: prompt-time guidance + structural tests + runtime allowlists. When (if) the audience expands to multiple humans or open-source contributors, the enforcement strictness needs to ratchet up — see the "Roadmap" section in `docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md`.

## Two artefacts you must read before touching code

1. **[`docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md`](docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md)** — the 11 laws, each tagged with how it's enforced (`[ENFORCED-by-test]`, `[ENFORCED-by-type]`, `[ENFORCED-by-runtime]`, or `[ASPIRATIONAL]`). Read it. The tags are honest — laws marked aspirational do not have automatic enforcement, so the prompt is your only guardrail there.
2. **[`tests/test_engineering_principles.py`](tests/test_engineering_principles.py)** — the deterministic gate. Run it before every commit:

   ```bash
   pytest tests/test_engineering_principles.py -v
   ```

   Every law that ends with `[ENFORCED-by-test]` has a corresponding `test_law_N` in this file. If your change makes one fail, fix the change OR (rarer) propose an explicit law revision in the same PR.

## Before every commit

1. Run `pytest tests/` — full suite must be green.
2. Run `ruff check agent/ tests/` — no findings.
3. Run `pytest tests/test_engineering_principles.py -v` — the law-gate must be green.
4. Write a commit message matching the format below.

## Commit-message format (Law 9 — versioned justification)

Every commit message body MUST contain three sections in this order:

```
<one-line summary>

What changed
  - <bullet 1>
  - <bullet 2>

Why it changed
  <one paragraph naming the failure mode being fixed, the feature being
  added, or the law being honored>

Validation
  - <how you verified: which tests, which CLI smoke, which manual check>
```

The pre-commit hook (`.pre-commit-config.yaml`) checks for these section headers. Cosmetic / docs-only commits can use `What changed: <one line>` and skip the others, but anything touching `agent/` or `tests/` must include all three.

## Where to put new code

Neuro-OS is **one substrate** (`agent/domain_app/`) with **four
verticals** layered on top: `agent/founder_loop/`, `agent/research/`,
`agent/investment/`, `agent/startup/`. New work generally goes in one
of those four packages or — more rarely — in the substrate itself.
Cross-vertical reads go through `agent/cross_vertical.py`.

| If you are adding... | Put it under | Pydantic-validate? | Test? |
|---|---|---|---|
| A new substrate primitive (used by all 4 verticals) | `agent/domain_app/state.py`, `protocol.py`, or `app.py` | YES — frozen if returned to user | unit test pinning the shape; substrate adapter test in `tests/test_*_substrate_adapter.py` (founder_loop case is the template) |
| A new schema or vocabulary inside one vertical | `agent/{founder_loop,research,investment,startup}/state.py` (or a new module if cross-cutting) | YES — frozen if returned to user | unit test pinning the shape |
| A new failure-mode (drift mode) for a vertical | the vertical's `catalog.py` (must keep `len(underlying_needs) == 6`); ensure ≥1 `ConstructiveExpressionBase` option per need (Law 3) | YES | substrate adapter test asserts the 6-mode invariant |
| A new ControlOp (founder_loop) | `agent/founder_loop/state.ControlOp` enum + `policy.py` decision tree + `policy._inverse` mapping | n/a | golden-case test in `tests/test_founder_loop_policy.py` AND inverse test |
| A new sensor / sensor input (founder_loop) | `agent/founder_loop/observe.py` or a new module mirroring `urge_log.py` | YES | unit test for parsing + an e2e scenario in `tests/e2e/scenarios.md` |
| A new sensor for research/invest/startup | the vertical's `ontology.py` or a new sibling module | YES | unit test pinning the shape |
| A new CLI subcommand | `agent/cli.py`. Founder-loop subcommands live under `loop`; the other three use top-level `research`/`invest`/`startup` namespaces wired by `_add_vertical_subcommands()`. Top-level cross-cutting subtrees (`skillify`, `cross-vertical`) live alongside as separate `_add_*_subcommands` helpers | n/a | `tests/test_verticals_cli.py` for top-level subcommands; `tests/e2e/test_http_scenarios.py` if it touches the daemon |
| A new cross-vertical share/read | `agent/cross_vertical.py` (`VerticalNote` + `Entity` are the two shareable record types; default visibility is `[source_vertical]`; explicit `share_with=[...]` to broaden) | YES — frozen models | privacy-assertion test in `tests/test_cross_vertical_e2e.py` AND `tests/test_lane4_entity_propagation.py` if it touches the entity surface |
| A new entity kind | extend `agent/cross_vertical.py::EntityKind` literal; nothing else changes (the upsert / read / list flow is generic) | YES — frozen | `tests/test_lane4_entity_propagation.py::test_list_entities_filter_by_kind` extended with the new kind |
| A new ingestion source format | `agent/research/ingest.py::_extract_text` + `SUPPORTED_EXTS` + a fixture-loader helper in tests | YES — text → `RawSource` is Pydantic-validated | `tests/test_research_ingest_plan_a.py::test_extract_text_<format>` |
| A new bias-check scorer | `agent/cross_modal.py::make_default_scorers` adds the (label, callable) pair; the `Scorer` type signature is `(text) -> (flag, primitive, reason)` | YES — return must match | `tests/test_lane3_cross_modal.py::test_make_default_scorers_*` |
| A new dashboard metric | `agent/research/dashboard.py::DashboardSummary` schema + the matching aggregator function (one of `_aggregate_*` / `_compute_*`) + `render_text` line | YES — frozen | `tests/test_research_dashboard.py::test_*` (model + render + CLI) |
| A new compression-rollup strategy (Layer 4) | `agent/research/compress.py::_group_clusters_to_l0` is the only place that decides how Level-1 clusters map up to Level-0 nodes. Default: group by shared `framework_axes_touched`, then smallest-pair merge until ≤5. New strategies plug in here, keyed by a `--strategy` arg on `compress` if/when needed. Hierarchy shape is enforced by `HierarchicalCompression` (frozen; max 5 L0 nodes, max 30 L1 nodes) | YES — frozen `HierarchicalCompression` + `CompressedNode` | `tests/test_research_compress.py::test_compress_*` (algorithm shape + storage round-trip) |
| A new expression modality (Layer 5) | extend `agent/research/expression.py::EXPRESSION_MODALITIES` tuple + `ExpressionModality` Literal. Nothing else changes — `record_expression` and `reveal_expression` are modality-agnostic. The modality affects only the schema validation and the optional `tool_hint` convention | YES — frozen `Expression` | `tests/test_research_expression.py::test_modality_must_be_in_allowlist` extended with the new value |
| A new override-emission point | `agent/skillify/events.py::write_override_event` is the only writer; new emission points just call it. The CLI flag pattern is `--override-of <drift_mode> --override-vertical <v>` (mirrors `loop urge`) | YES — frozen `OverrideEvent` | `tests/test_paul_week_features.py::test_loop_urge_with_override_of_emits_skillify_event` (template) |
| A new chat surface | `agent/founder_loop/conversation.py` (`kind="..."`) + a route in `server.py` (founder_loop only today; research/invest/startup chat surfaces are roadmapped — the CLI REPLs `research review --cli`, `skillify review --cli` are the v0 gates) | n/a | a Playwright test in `tests/e2e/test_browser_scenarios.py` |
| A new browser surface (HTML page served by the daemon) | New file under `agent/founder_loop/static/<name>.html` (vanilla HTML/CSS/JS, no external assets — keep the dark-mode aesthetic from `onboard.html`). Add a `_serve_<name>_page` handler in `agent/founder_loop/server.py` and wire it into `_dispatch_get`. Mutation endpoints go in `_dispatch_post`. Existing examples: `research-living-knowledge.html` (#36), `research-review.html` (#38), `invest-dashboard.html` (#39) | n/a | a daemon-route test in `tests/test_<name>_ui.py` spinning up the real server on a random port; pin a CORS regression test (attacker Origin + Sec-Fetch-Site cross-site) specifically for the new routes |
| A new doc | `docs/<name>.md`. Mirror to `agent/founder_loop/static/<name>.md` if served by daemon | n/a | link-check (manual) |
| A new patch op (L2 self-modification) | `agent/patches.py` `ALLOWED_OPS` + handler + paired inverse | n/a | `tests/test_self_modification.py` allowlist refusal test |

## What you must NOT do

- Do not introduce free-text inputs that flow into the loop without Pydantic validation (Law 1).
- Do not add a `ControlOp` without an entry in `policy._inverse()` (Law 6 enforces this).
- Do not flip `mutable_paths=[]` to non-empty for any vertical without a `/catalog-review`-equivalent human gate (Law 7). All four verticals ship with `mutable_paths=[]` today; promotion is per-vertical and gated.
- Do not write a function that returns `dict` to the user — use a Pydantic model or a frozen dataclass (Law 5).
- Do not let one vertical read another's data without going through `agent/cross_vertical.read_shared(...)` — the privacy-assertion test in `tests/test_cross_vertical_e2e.py` will fire. Default cross-vertical visibility is private.
- Do not let any vertical's catalog drift from "exactly 6 named failure modes, ≥1 option per failure mode." This is the substrate's invariant; the substrate-adapter tests defend it.
- Do not commit without the three-section message format (Law 9; pre-commit hook will block you).
- Do not write generated data into the repo tree (Law 11). All runtime artifacts (JSONL logs, SQLite DBs, JSON payloads from pipeline runs) go to `~/.neuro_os_*/`. If a new tool writes output files, add the pattern to `.gitignore` **in the same PR**. `test_law_11` will catch any `.jsonl`/`.db` files that slip through.

## How to add a new law

1. Open a PR that:
   - Adds the law text to `docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md` with the appropriate `[ENFORCED-by-X]` or `[ASPIRATIONAL]` tag.
   - If `[ENFORCED-by-test]`: adds the corresponding `test_law_N` to `tests/test_engineering_principles.py`.
   - If `[ENFORCED-by-type]`: adds the type / Pydantic constraint and a test that proves a violation raises.
   - If `[ENFORCED-by-runtime]`: adds the allowlist entry / safety check + a test in `tests/test_founder_loop_safety.py`.
   - If `[ASPIRATIONAL]`: NAME why it's aspirational (no testable form yet) AND name the prompt-time hint that's expected to enforce it.

The PR title should start with `Law N+1:` so the audit history is grep-able.

## How to revise an existing law

Same shape as adding, but include in the PR description:

- What violation evidence triggered the revision (link to specific commits or CI runs that fired the law).
- Whether the revision tightens or loosens the law.
- Whether the test still passes against the new wording (it should — if it doesn't, you're rewriting the test, which is a different decision).

Law revisions are a separation-of-concerns issue today (single author writes, enforces, and uses the laws). When the team grows, this section should require an explicit reviewer who is not the author. Tracked in `docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md` under "Roadmap."

## Failure escalation (when you're stuck)

- A test is failing in a way that suggests the law is wrong, not the code → propose a law revision in the same PR (per "How to revise" above), do not silently delete the test.
- A pre-commit hook is blocking a legitimate commit → DO NOT use `--no-verify`. Either fix the issue or amend the hook with a follow-up commit naming the new edge case it should accept.
- The deterministic enforcer in `test_engineering_principles.py` doesn't yet cover a law you're trying to honor → add the enforcer first, in a separate commit, before the change that needs it.

## What this file is NOT

- Not a substitute for `docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md` — that's the source of truth for the laws.
- Not a substitute for `tests/test_engineering_principles.py` — that's the deterministic gate.
- Not a place to encode product roadmap (use `docs/roadmap.md`) or feature design (use `docs/plans/` for design notes referenced from in-repo docs; `~/.claude/plans/` for personal in-flight scratch that isn't referenced from anywhere public).

This file is the *prompt-time* layer of a 4-layer enforcement stack:

```
L1 prompt-time   ← THIS FILE (CLAUDE.md)
L2 type-time     ← Pydantic schemas + frozen dataclasses + ruff
L3 test-time     ← tests/test_engineering_principles.py + tests/test_founder_loop_safety.py + the rest of pytest
L4 runtime       ← agent/patches.py ALLOWED_OPS + agent/domains.py mutable_paths
```

Each layer catches a different failure mode. Read the principles doc for which law lives at which layer and why.
