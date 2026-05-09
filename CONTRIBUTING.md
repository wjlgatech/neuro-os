# Contributing to Neuro-OS

> One-page fast path for human contributors. If you're an AI agent writing code in this repo, read [`CLAUDE.md`](./CLAUDE.md) instead — it's the prompt-time guardrail layer aimed specifically at LLM contributors.

## 60-second orientation

Neuro-OS is **one substrate** (`agent/domain_app/`) with **four verticals** layered on top: `agent/founder_loop/`, `agent/research/`, `agent/investment/`, `agent/startup/`. Each vertical is the same closed-loop OEC machine (Observe → Evaluate → Control → Validate) with different vocabulary. The cross-vertical interface (`agent/cross_vertical.py`) is **default-private** — one vertical can't read another's data without explicit sharing.

The codebase is governed by **10 laws** in [`docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md`](./docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md). Each law is honestly tagged `[ENFORCED-by-test/type/runtime]` or `[ASPIRATIONAL]`. The deterministic gate is [`tests/test_engineering_principles.py`](./tests/test_engineering_principles.py).

## Setup

```bash
git clone https://github.com/wjlgatech/neuro-os.git
cd neuro-os
pip install -e ".[dev]"
bash scripts/install_hooks.sh    # commit-msg + pre-commit (law gate)
```

The hook script enables `commit-msg` (enforces the 3-section message format, Law 9) and `pre-commit` (runs `tests/test_engineering_principles.py`, Laws 1/3/4/5/6/7/9). Installed via `core.hooksPath`; no global git config is touched.

## Run the gates

```bash
pytest tests/                               # full suite (~30s)
pytest tests/test_engineering_principles.py # the law gate (run before every commit)
ruff check agent/ tests/                    # lint must be clean
```

All three must be green before you push.

## Pick something to work on

Open [`docs/roadmap.md`](./docs/roadmap.md) and look at the **NEXT** column. Each entry has a "Days" estimate and a design pointer. Items in `LATER` are intentionally deferred — don't pick those without raising an issue first. Items in `SHIPPED` are done; PRs that "improve" shipped items should justify the regression risk.

If you have a new idea that isn't on the roadmap, open an issue describing the failure mode you're addressing before writing code. The roadmap is the single source of truth for what's planned, in flight, and done.

## Where to put new code

The `CLAUDE.md` "Where to put new code" table covers all common cases (new sensor, new schema, new ControlOp, new cross-vertical share, new chat surface, new CLI subcommand, new patch op). Read that table; it's the same answer whether you're a human or an AI.

In short: most new work lands in one of the four vertical packages, never crosses vertical boundaries except through `agent/cross_vertical.py`, validates inputs with frozen Pydantic, and ships with at least one test.

## Things you must NOT do

- Don't introduce a free-text input that flows into the loop without Pydantic validation (Law 1).
- Don't return `dict` to the user — use a frozen Pydantic model or frozen dataclass (Law 5).
- Don't add a `ControlOp` without an inverse in `policy._inverse()` (Law 6).
- Don't read another vertical's data without going through `agent/cross_vertical.read_shared(...)` (privacy is default-PRIVATE).
- Don't flip any vertical's `mutable_paths=[]` to non-empty without a human gate (Law 7).
- Don't commit without the 3-section message format (Law 9; pre-commit hook will block you).
- Don't bypass the hooks with `--no-verify` unless you're amending a hook with a follow-up commit naming the new edge case it should accept.

## Commit message format

Every commit message MUST contain three sections:

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

Cosmetic / docs-only commits can collapse to `What changed: <one line>` and skip the others. Anything touching `agent/` or `tests/` must include all three. The `commit-msg` hook checks for these section headers.

## Pull requests

- Branch off `main`. Name your branch descriptively (`feature/<short-slug>` or `fix/<short-slug>`).
- Keep PRs focused on a single change. The reviewer's time is the bottleneck, not yours.
- The PR description should mirror the commit message: What / Why / Validation, plus a Test plan.
- CI runs the full pytest suite + ruff + the principle gate. All three must pass.
- DO NOT merge your own PR unless the maintainer explicitly delegates it.

## When you're stuck

- A test is failing in a way that suggests **the law is wrong, not the code** → propose a law revision in the same PR (see [`CLAUDE.md`](./CLAUDE.md) "How to revise an existing law"). Don't silently delete the test.
- A pre-commit hook is blocking a legitimate commit → fix the issue, or amend the hook in a follow-up commit naming the new edge case. Never bypass with `--no-verify`.
- The substrate raises at construction (e.g., your vertical's catalog isn't exactly 6 named failure modes with ≥1 constructive expression each) → that's the substrate defending its invariants. Adjust your catalog, don't disable the check.

## Where the design notes live

In-flight feature design that's referenced from in-repo docs (e.g., from `docs/roadmap.md`) lives at [`docs/plans/`](./docs/plans/). Personal scratch notes that aren't referenced from the public docs stay in `~/.claude/plans/` (out of repo).

## Code of conduct

Be technically honest. Don't paper over failure modes with comments — fix them or document them as known issues. Don't add "framework-style" abstractions for hypothetical future contributors — the audience today is small. When in doubt, ship the simplest version that passes the laws and let the next failure mode pull complexity in.
