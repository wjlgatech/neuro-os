---
status: parked
parent: infra
reason: "Long-form design doc for the founder_loop vertical. Un-parks when Paul returns to substrate work after Phase-1 paper push."
---

# Plan — `founder_loop`: a daily reward-economy + sublimation loop, built on what's shipped

## Context

The user proposed building "control-os" as a missing 6th repo — a governor for an AI-era control system. Eval found that **company-os already is the governor**, **flywheel is already the OEC substrate**, **workflowx is already the observation layer**, and **neuro-os Belief OS (v0.4)** is already the reasoning evaluator. The proposed "5 layers" (state / observe / evaluate / control / memory) map 1:1 onto existing primitives. So the actual gap is **wiring**: a single module inside neuro-os that imports the four existing systems and proves a closed daily loop in 9 days. The user's instruction is "**don't spread wide, dig deep, build on what's been done**" — meaning no new repo, no new substrate.

### Philosophical reframe (load-bearing for the policy)

The user explicitly rejected the brute-force "detect distraction → block URL" model. Their working philosophy:

> *Negative destructive behavior is the counterfeit expression of a God-given desire. Acknowledge the desire, find a constructive expression as replacement — no simple suppression. Convert negative energy into positive energy.*

Operationalized for code:

1. **Reward economy, not deprivation economy.** Each day the user defines top 3–5 priorities with explicit *evidence criteria* (what proves "done"). Entertainment unlocks at **90% tank fullness** (priority progress, evidenced) and is rationed by an amount yesterday-self pre-set. Entertainment is a *legitimate reward*, not a thing to suppress.
2. **Sublimation, not suppression.** When an entertainment urge fires *pre-threshold*, the system does not block. It diagnoses the **underlying need** (fatigue / novelty-hunger / social / frustration / decision-fatigue / embodied) and proposes a **constructive expression** of that same need that credits the tank instead of debiting it. Block is a fallback only after sublimation is offered and refused — and only if yesterday-self pre-authorized it.
3. **Ulysses pact.** Yesterday-self (rested, deliberative) signs the contract: priorities + evidence + entertainment ration + abuse-tax. Today-self (tired, tempted) is bound by it but always retains agency — every override is logged and drains the tank, never silently denied.

The single research bet: **`MAE(predicted_next_hour_distraction, actual_next_hour_distraction)` trends down over a 7-day window** AND **contract-honor rate (ops where today-self honored yesterday-self's contract / total ops) ≥ 0.8 by day 7**. If both, the human-AI co-regulation loop is real and learnable. If neither, the experiment fails honestly.

---

## Recommended approach

Build `agent/founder_loop/` inside neuro-os, registered as a flywheel `Domain` (read-only L2 in v0). Public API mirrors the v0.4 Belief OS shape. Everything load-bearing already exists in this repo — what's new is the *policy* (reward economy + sublimation) and the four small modules that implement it.

---

## Architecture — file tree + reuse map

```
agent/founder_loop/
├── __init__.py            # public API: FounderLoop class + tick() / nightly() / morning_ritual()
├── state.py               # Pydantic: FounderState, ForecastedState, ControlAction, Priority, TankState, Contract, Diagnosis
├── observe.py             # WorkflowxAdapter (real + fixture); builds FounderState
├── predict.py             # make_predictor() → llm_fn; mirrors agent/llm_extractors.py
├── sublimate.py           # diagnose(state, urge_type) → Diagnosis(need, options); LLM-driven w/ catalog fallback
├── reward_ledger.py       # compute_tank(registry, contract) → TankState; pure function over registry
├── contract.py            # Contract Pydantic + bind_morning_contract() + check_contract(action)
├── priorities.py          # Priority Pydantic w/ evidence_type vocab; load/store; verify_evidence()
├── evaluate.py            # reconcile predicted-vs-actual; calls Belief OS on intent
├── policy.py              # decide_control(): orchestrates contract + tank + predict + sublimate → ControlAction
├── act.py                 # ControlAction → flywheel.Patch (allowlisted, reversible)
├── memory.py              # nightly LLM summarizer; writes flywheel.Registry
├── golden_cases.py        # PERSONAL_GOLDEN_CASES — "loop is broken if..."
├── domain.py              # Domain registration: founder_loop_v1
└── data/
    ├── sublimation_catalog.json  # 6 underlying needs → constructive expressions (replaces failure_modes.json)
    ├── auto_apply_ops.json       # seed: {continue, propose_constructive_expression, force_intent_capture}
    └── queues/
        ├── bookmarks_queue.json  # curated novelty (Scenario B)
        ├── social_queue.json     # people to reach (Scenario D)
        └── rubber_duck_venues.json  # Discord channels, voice-memo targets (Scenario C)

examples/08_founder_loop_dry_run.py   # replay against fixture; print MAE + contract-honor trend
tests/test_founder_loop_state.py       # pin Pydantic schemas
tests/test_founder_loop_predict.py     # mocked Haiku call
tests/test_founder_loop_sublimate.py   # diagnosis correctness across 6 needs
tests/test_founder_loop_ledger.py      # tank computation: credits, debits, abuse tax
tests/test_founder_loop_contract.py    # bind/check/override-logged
tests/test_founder_loop_policy.py      # decide_control logic — full op set, allowlist
tests/test_founder_loop_goldens.py     # golden_case detector + rebuild trigger
tests/test_founder_loop_safety.py      # 6 safety laws as pytest cases
tests/test_founder_loop_uat.py         # 14 BEFORE/AFTER scenarios

agent/cli.py             # MODIFY: add `loop tick`, `loop nightly`, `loop morning` subcommands
README.md                # MODIFY: add "Founder Loop" section + philosophy + launchd snippet
```

### What each new file reuses

| New file | Reuses (file:line) |
|---|---|
| `state.py` | Pydantic patterns from `agent/belief_os.py:104-187` |
| `observe.py` | JSONL read pattern from `agent/version_registry.py`; fixture pattern from `tests/test_belief_os_api.py:setUp` |
| `predict.py` | `agent/llm_extractors.py:make_anthropic_extractor` — same `client.messages.parse()` + Pydantic schema + `cache_control: ephemeral` + graceful fallback |
| `sublimate.py` | Same Anthropic extractor pattern; system prompt seeded from `data/sublimation_catalog.json`. Stateless function `diagnose(state, urge_type) → Diagnosis` |
| `reward_ledger.py` | Pure-function reduce over `agent/version_registry.py` JSONL rows. No LLM. |
| `contract.py` | JSONL append/load like `version_registry.py`. Pydantic Contract schema. `check_contract(action, contract) → CheckResult` |
| `priorities.py` | Pydantic Priority schema with fixed `evidence_type` enum: `commit_pushed | pr_opened | pr_merged | doc_published | count_reached | human_signoff | artifact_uploaded`. `verify_evidence()` queries git/GitHub via existing tooling where possible |
| `evaluate.py` | `agent.belief_os.check_decision_text(state.last_intent)` (existing v0.4 surface) |
| `policy.py` | flywheel `Patch` allowlist pattern from `agent/patches.py:ALLOWED_OPS`. Calls `contract.check_contract`, `reward_ledger.compute_tank`, `sublimate.diagnose` |
| `act.py` | flywheel `apply_patch` + `inverse_op` from `agent/patches.py:_apply_append_priority_rule` |
| `memory.py` | `agent/version_registry.py`: `set_registry_path` + `append_version`. `utc_now()` from `agent/experiment_logger.py:13-14` |
| `golden_cases.py` | flywheel `golden_accuracy_validator` pattern from `agent/domains.py:57-105`; mirrors goldens at `agent/personal_epistemic_domain.py:202-258` |
| `domain.py` | `register_domain` from `agent/personal_epistemic_domain.py:289-306`. `mutable_paths=[]` in v0; v1 flips to `["agent/founder_loop/data/sublimation_catalog.json", "agent/founder_loop/data/queues/*.json"]` |
| `__init__.py` | `agent/belief_os.py` is the template — class + stateless functions + Pydantic results + optional LLM + optional persistence |

---

## Load-bearing schemas

Pinned by `tests/test_founder_loop_state.py`:

- **`Priority`** — `{title, evidence_type ∈ EVIDENCE_VOCAB, evidence_target, weight (1-3), status ∈ {pending, in_progress, evidenced, abandoned}}`. `EVIDENCE_VOCAB = {commit_pushed, pr_opened, pr_merged, doc_published, count_reached, human_signoff, artifact_uploaded}`.
- **`Contract`** — `{date, priorities: list[Priority], entertainment_ration_min: int, threshold_pct: int (default 90), abuse_tax: {threshold_violation_multiplier, ration_violation_multiplier}, pre_authorized_blocks: list[str]}`. Signed by yesterday-self via `loop morning`.
- **`TankState`** — `{percent: float (0-100), credits_today: float, debits_today: float, threshold: int, ration_remaining_min: int, status ∈ {below_threshold, threshold_within_ration, threshold_over_ration}}`.
- **`FounderState`** — observed (distraction_minutes_last_hour, deep_work_minutes_last_hour, context_switches, time_since_last_meal_min, sleep_last_night_hours, hours_continuous_screen) + trajectory (rolling 7-day) + memory (last_intent, last_outbound_message_age_h). **Cuts** all vibe-only fields.
- **`Diagnosis`** — `{underlying_need ∈ NEED_VOCAB, confidence ∈ {low,medium,high}, options: list[ConstructiveExpression], reasoning: str}`. `NEED_VOCAB = {fatigue, novelty_hunger, social, frustration, decision_fatigue, embodied_hunger, embodied_eye_strain, earned_reward, none}`.
- **`ConstructiveExpression`** — `{action: str, duration_min: int, tank_credit_pct: float, references: list[str] (optional pointers into queues), then_reassess_at: Optional[datetime]}`.
- **`ForecastedState`** — `predict_next_hour()`: `{predicted_distraction_min, predicted_deep_work_min, predicted_urge ∈ {none, entertainment, escape, novelty}, predicted_underlying_need ∈ NEED_VOCAB, confidence, reasoning}`.
- **`ControlAction`** — ops:
  - `continue` — keep going
  - `unlock_entertainment` — tank ≥ threshold ∧ within ration; payload includes `duration_min`, `then_reassess_at`
  - `propose_constructive_expression` — tank < threshold; payload is a `Diagnosis`
  - `notify_ration_used` — tank ≥ threshold but ration exhausted; payload includes residual diagnosis
  - `force_intent_capture` — morning over-ambition or stale intent
  - `start_25min_sprint` — micro-commit when novelty/decision-fatigue diagnosed
  - `shorten_current_task` — research-rabbit-hole pattern
  - `swap_priority` — mid-day amendment; costs N tank-credits, requires explicit replacement
  - `rest` — rest-day or post-ship
  - `escalate_to_human` — Belief OS flagged the intent itself; or sensors dead
  - `replan` — nightly only
  - `block_url` — fallback after sublimation refused, only if `pre_authorized_blocks` includes target

Each `ControlAction` includes `auto_applied: bool`, `inverse_op`, `tank_delta: float` (positive credit, negative debit), `contract_check: {honored: bool, violation_type: Optional[str]}`.

---

## The two research bets

1. **MAE trends down.** `MAE(predicted_distraction_minutes, actual_distraction_minutes)` per hourly tick, rolling 7-day window, plotted nightly. **Day-7 success: MAE_day7 < MAE_day1.**
2. **Contract-honor rate trends up.** `contract_honor_rate = (ops with contract_check.honored=True) / (total ops)` per day. **Day-7 success: rate ≥ 0.8 AND day-7 rate > day-1 rate.** This measures whether today-self is increasingly trusting yesterday-self's contract — the actual self-regulation signal. If MAE drops but contract-honor doesn't, the system predicts well but isn't useful. If contract-honor rises but MAE doesn't, the contract is well-tuned but the predictor isn't learning. We need both.

### `golden_cases.py` — falsifiability gate

When ≥2 fail in a 7-day window, the nightly summarizer's job switches from "update tomorrow's contract" to "rewrite the predictor or sublimation prompt."

| Golden case | Failure name | Fires rebuild of |
|---|---|---|
| `predicted < 30min` ∧ `actual > 90min` distraction in any morning hour | `morning_overconfidence` | predictor |
| `predicted_underlying_need = "none"` ∧ `actual distraction > 45min` | `missing_need_in_catalog` | sublimation catalog |
| `predicted_deep_work > 45min` ∧ `actual_deep_work < 15min` for 2 consecutive ticks | `delusional_intent_capture` | predictor |
| MAE on a 24h window doubles vs. previous 24h | `model_drift` | predictor |
| Contract-honor rate < 0.5 for 3 consecutive days | `contract_too_aggressive` | morning_ritual prompt (suggest fewer priorities or longer ration) |
| ≥3 consecutive `propose_constructive_expression` ops refused with same `underlying_need` | `wrong_diagnosis_or_wrong_expression` | sublimation catalog entry for that need |

---

## Implementation order — 9 days

| Day | Concrete deliverable | Test gate |
|---|---|---|
| 1 | `state.py` (all schemas including new ones), `golden_cases.py` | `pytest tests/test_founder_loop_state.py` 100% |
| 2 | `observe.py` w/ `WorkflowxAdapter` + JSONL fixture (24h synthetic) | `python examples/08_founder_loop_dry_run.py` builds 24h of `FounderState` rows |
| 3 | `priorities.py` + `contract.py` + `reward_ledger.py` (small, pure-function trio) + `loop morning` CLI | mocked tests pass; `loop morning --dry-run` emits a Contract row; `compute_tank` correct on 6 fixture cases |
| 4 | `evaluate.py` (Belief-OS-wired) + `predict.py` (Haiku 4.5 call mirroring `make_anthropic_extractor`) + UAT scenario #4 (Belief OS integration) green | **First gate: #4 green or stop.** Mocked test passes; real-call smoke shows ForecastedState shape |
| 5 | `sublimate.py` (LLM diagnosis + catalog) + UAT scenarios A–F (the 6 sublimation cases) green on fixtures | **Sublimation gate: 6 of 6 sublimation scenarios green.** This is the philosophical heart of the system. |
| 6 | `policy.py` (orchestrates contract + tank + predict + sublimate) + `act.py` + `memory.py` + `cli.py` (`tick`, `nightly`) + UAT scenarios #1–#3, #7–#8 green | **Mid gate: 11 of 13 cheap-to-test scenarios green** (5 originals + 6 new). |
| 7 | Live for 24h read-only on real workflowx (no auto-applied patches; queue + log only). `data/queues/` populated by user via 5-min ritual. | registry has 24 rows; queue surfaces ≥3 distinct proposed `ControlAction`s; ≥1 sublimation diagnosis fired |
| 8 | Promote `propose_constructive_expression` and `force_intent_capture` to auto-apply. Live 24h. Plot MAE + contract-honor. | UAT #6 (graduation) green; ≥1 auto-applied sublimation in registry |
| 9 | Final live 24h. UAT #5 (MAE trend) + new bet #2 (contract-honor rate) | **Final gate: MAE_day7 < MAE_day1 AND contract_honor_day7 ≥ 0.8.** Stop or v1 depending. |

### Gate priority

The 14 UAT scenarios split into four gates:

| Gate | Scenarios | Why |
|---|---|---|
| **Belief OS gate (Day 4)** | #4 | Proves architecture: founder_loop consumes Belief OS as a primitive. If this fails, stop. |
| **Sublimation gate (Day 5)** | A–F | Proves philosophy: the system diagnoses underlying needs and proposes constructive expressions. This is the actual differentiator. If this fails, the system is generic productivity software. |
| **Mid gate (Day 6)** | #1, #2, #3, #7, #8 | Proves the per-tick loop and contract machinery work end-to-end. |
| **Final gate (Day 9)** | #5, #6, contract-honor bet | Proves the system actually learns the human and is increasingly trusted. Requires ≥7 days of real data. |

Original Day 1–7 had `predict.py` Day 3 and `evaluate.py` Day 4 with no sublimation/contract pieces. New ordering: foundational schemas Day 1, observe Day 2, the contract/tank/priorities trio Day 3, evaluate+predict (Belief OS gate) Day 4, sublimate (philosophical gate) Day 5, full policy orchestrator Day 6, live Days 7–9.

---

## Six safety laws — pinned to tests

`tests/test_founder_loop_safety.py` — one test per law, fails CI if violated:

1. **Observability** — render last 24h from registry alone; assert ≥24 rows
2. **Evaluability** — every registry row has `predicted` and `actual`; `error` computable
3. **Controllability** — every `ControlAction` op is in `ALLOWED_OPS`; refused otherwise
4. **Stability** — every promoted patch logs `inverse_op`; auto-revert when ≥2 goldens fail in 24h
5. **Bounded action** — write attempt outside `agent/founder_loop/data/*.json` raises (path allowlist enforced)
6. **Contract integrity** — every `ControlAction` carries a `contract_check`; overrides log `contract_check.honored=False` with `violation_type`; tank debits at the abuse-tax rate. Test asserts: a `block_url` action fails if its target is not in `pre_authorized_blocks`; an `unlock_entertainment` action fails if `tank.status != "threshold_within_ration"`.

---

## Public API consumed by company-os Founder OS

```python
from agent.founder_loop import FounderLoop, ControlAction, FounderState, Priority, Contract

loop = FounderLoop(
    registry_path="users/alice/founder_loop_registry.jsonl",
    contract_path="users/alice/contracts.jsonl",
    queues_dir="users/alice/queues/",
    workflowx_export_path="~/Library/.../workflowx/exports/",
    use_llm=True,
    api_key=None,
)

# Morning — yesterday-self signs the contract
contract = loop.morning_ritual(
    priorities=[
        Priority(title="ship belief_os v0.4 PR", evidence_type="pr_merged",
                 evidence_target="neuro-os#142", weight=3),
        Priority(title="2 deep-work blocks on founder_loop predict.py",
                 evidence_type="commit_pushed", evidence_target="2_commits", weight=2),
    ],
    entertainment_ration_min=60,
    threshold_pct=90,
)

# Hourly — what cron / launchd calls
result = loop.tick()
# → TickResult(state, forecasted, tank, action, contract_check, registry_row_id)

# Nightly
summary = loop.nightly()
# → NightlySummary(mae, contract_honor_rate, goldens_failed,
#                  action="update_contract" | "rebuild_predictor" | "rebuild_sublimation_catalog")

# Stateless one-offs
from agent.founder_loop import predict_next_hour, diagnose_underlying_need, compute_tank
forecasted = predict_next_hour(current_state, intent="ship the v0.4 PR")
diagnosis = diagnose_underlying_need(current_state, urge_type="entertainment")
tank = compute_tank(registry_path, contract)
```

Founder OS Approval Gate (in company-os) calls `loop.tick()` and routes `propose_constructive_expression` / `unlock_entertainment` / `block_url` through its existing approval queue. Belief OS already integrated via `evaluate.py`. No new code in company-os until v0 ships.

---

## Verification

```bash
# Unit + contract tests
python -m pytest tests/test_founder_loop_*.py -v

# Schema-shape integration
python examples/08_founder_loop_dry_run.py
# Expect: contract bound → 24 fixture rows → 24 registry rows → MAE + contract-honor printed → queue printed

# Morning ritual
python -m agent loop morning --dry-run
# Expect: prompts for priorities + ration; emits Contract row; refuses if any priority lacks evidence_type

# Live single tick (read-only)
python -m agent loop tick --dry-run
# Expect: 1 registry row with {state, forecasted, tank, action, contract_check}; 0 patches applied

# Real call with API key
ANTHROPIC_API_KEY=sk-... python -m agent loop tick
# Expect: registry row with method='llm-anthropic'; cache_read on subsequent ticks

# Nightly summary
python -m agent loop nightly
# Expect: MAE + contract_honor_rate printed; goldens checked; rebuild action chosen if any

# Safety laws
python -m pytest tests/test_founder_loop_safety.py -v
# All 6 must pass
```

---

## Out of scope (explicit cuts — not v0)

- **L2 self-modification of the sublimation catalog.** v0 ships `mutable_paths=[]`; v1 flips it on. v0's catalog is hand-edited; the `wrong_diagnosis` golden surfaces what to edit.
- **Hard-block enforcement (Screen Time API / hosts-file / DNS).** v0 emits `block_url` as a queue entry only. The actual technical enforcement integrates with macOS Screen Time or a hosts-file shim — that's a v0.5 follow-up. v0 honors the philosophy "every override logged, agency preserved" by *proposing* and *logging*, not enforcing.
- **Vibe-only signals.** No `energy_level`, `spiritual_alignment`, "momentum" fields without instrumentation.
- **Web UI.** company-os Founder OS already has one.
- **Schedulers beyond cron/launchd.** No daemon, no FastAPI server.
- **Multi-user.** Per-user state via constructor args. v1 is a path multiplexer.
- **Automatic queue maintenance.** v0 ships a 5-min weekly ritual (`loop maintain-queues`) that prompts the user to add/remove items. Auto-curation (LLM scrapes bookmarks from Pocket / Twitter likes) is v1.

---

## Answered design choices (resolved during planning)

These were open earlier and are now decided:

1. **Hard block vs soft flag.** Soft flag in v0 (proposes block; logs override). Hard block is opt-in per-URL via `pre_authorized_blocks` and only fires after sublimation is offered and refused. Honors "no simple suppression."
2. **Evidence vocabulary.** Fixed enum, not free-text: `{commit_pushed, pr_opened, pr_merged, doc_published, count_reached, human_signoff, artifact_uploaded}`. Free-text would let today-self self-deceive at 3pm.
3. **Per-user queues are load-bearing.** `data/queues/{bookmarks,social,rubber_duck_venues}.json` are required for sublimation to propose *concrete* alternatives (Scenarios B, C, D). 5-min weekly maintenance ritual.
4. **Re-diagnosis is a first-class operation.** `ConstructiveExpression.then_reassess_at` lets the loop honor "do thing → reassess" patterns (Scenarios E, F). Tick scheduler honors it.
5. **Contract amendment costs tank-credits.** `swap_priority` is allowed but debits the tank at the contract's `abuse_tax.threshold_violation_multiplier × 0.5`. Free swaps would make the contract meaningless.

---

## User-acceptance test scenarios — the bar

`tests/test_founder_loop_uat.py` ships 14 fixture JSONLs under `tests/fixtures/founder_loop/`. Each is a 24h sequence of synthetic `RawEvent` records. Each test loads the fixture, runs `loop.tick()` on the relevant hour, asserts the row below. **System passes UAT when all 14 produce the asserted action / diagnosis / state.**

| # | Scenario | Layer / class | UAT assertion |
|---|---|---|---|
| 1 | Tuesday 3pm fade after low sleep — *fatigue case* | sublimate (need=`fatigue`) | `action.op == "propose_constructive_expression"` ∧ `diagnosis.underlying_need == "fatigue"` ∧ `"nap" in [o.action for o in diagnosis.options]` ∧ `tank_delta_if_accepted > 0` |
| 2 | Research rabbit-hole on a ship day | predict + policy | `action.op == "shorten_current_task"` ∧ `payload.budget_minutes <= 30` |
| 3 | Monday over-ambition (8 priorities, capacity 2) | morning_ritual + policy | `morning_ritual` raises warning; if user proceeds, `forecasted.predicted_underlying_need == "decision_fatigue"` by mid-afternoon ∧ `action.op == "force_intent_capture"` with `payload.constraint == "max_3_priorities"` |
| 4 | Belief OS flags user's intent as `survivorship_bias` | evaluate ↔ Belief OS | `action.op == "escalate_to_human"` ∧ `"survivorship_bias" in action.rationale` |
| 5 | Day-7 MAE trends down vs. day-1 | nightly + measurement | `nightly.mae_today < nightly.mae_7d_ago` |
| 6 | 5 successive identical approvals graduate to auto-apply | allowlist + memory | after 5 approvals → `upgrade_prompt`; after acceptance → next identical op auto-applied |
| 7 | Holiday: user types `"rest day"` | policy (negative case) | `last_intent` matches `r"\b(rest|off|holiday|recover|break)\b"` ⇒ `action.op == "rest"` ∧ next 18h ticks emit `continue` |
| 8 | workflowx daemon dies for 4h | observe + golden | empty fixture from hour 4 ⇒ `action.op == "escalate_to_human"` ∧ `missing_observations_for_4h ∈ nightly.goldens_failed` |
| **A** | **3pm fade after low sleep — full sublimation flow** | sublimate | sleep<6h, decision-latency rising, tank=60% ⇒ `diagnosis.underlying_need == "fatigue"` ∧ options include `{action: "20_min_nap", tank_credit_pct: +5.0}` AND if user accepts, registry next-row shows `tank_delta=+5.0`; if user opens YouTube, `contract_check.honored == False` ∧ `violation_type == "threshold_violation"` ∧ tank debits at `abuse_tax × normal_rate` |
| **B** | **11am Twitter doom-scroll mid-deep-work** | sublimate (novelty) | in deep_work block + low fatigue + low output velocity ⇒ `diagnosis.underlying_need == "novelty_hunger"` ∧ `options[*].references` pulls from `bookmarks_queue.json` ∧ `options[0].duration_min == 10` |
| **C** | **Stuck on hard bug 90min → "just check email"** | sublimate (frustration) | flat output 90min on known-hard task ⇒ `diagnosis.underlying_need == "frustration"` ∧ `"voice_memo" in [o.action for o in options]` ∧ `payload.preserve_context == True` |
| **D** | **Sunday afternoon loneliness → reflexive YouTube** | sublimate (social) | `last_outbound_message_age_h > 48` + idle screen-time rising ⇒ `diagnosis.underlying_need == "social"` ∧ `options[*].references` pulls from `social_queue.json` |
| **E** | **Just shipped P1 → "I deserve this"** (legit reward case) | reward_ledger + policy | at t=ship: priority status flips to `evidenced`, tank → 100%, `action.op == "unlock_entertainment"` ∧ `payload.duration_min == contract.entertainment_ration_min` ∧ `payload.then_reassess_at == t+ration_min`. At t+ration: `action.op == "propose_constructive_expression"` ∧ `diagnosis.underlying_need == "fatigue"` (post-reward fatigue) |
| **F** | **Hunger-as-boredom at 4pm** | sublimate (embodied) | `time_since_last_meal_min > 240` + output velocity drop + no fatigue signal ⇒ `diagnosis.underlying_need == "embodied_hunger"` ∧ `options[0].action == "eat"` ∧ `options[0].then_reassess_at` is set; on re-tick after eating, urge re-evaluated fresh |

### Coverage breakdown

- **Failure-mode interventions (8):** #1, #2, #3, A, B, C, D, F (each names a distinct underlying need and proposes a constructive expression)
- **Belief OS integration (1):** #4
- **Reward-economy positive case (1):** E
- **Research bets (1):** #5 (MAE) — contract-honor bet measured separately, not a fixture test
- **Trust graduation (1):** #6
- **Negative tests (1):** #7 (system doesn't fire when it shouldn't)
- **Resilience (1):** #8 (system detects dead sensors)

Total 14, covering 6 distinct underlying needs in the sublimation catalog, plus contract enforcement in two directions (within ration: E; pre-threshold violation: A).

### Test plumbing

Each test:
1. Loads its fixture into a tempdir-scoped registry + queues
2. Binds a fixture Contract via `morning_ritual()`
3. Runs `loop.tick()` on the relevant hour
4. Asserts the row above

`predict.py` and `sublimate.py` LLM calls are mocked per-fixture with the expected output shape. Real-LLM smoke happens in Day 7+ live runs, not in CI. Adding a new scenario = add a fixture JSONL + an assertion row.

---

## Per-user queues + re-diagnosis design

Two cross-cutting design choices that touch multiple modules:

### Queues (load-bearing for B, C, D)

```
data/queues/
├── bookmarks_queue.json     # [{title, url, est_read_min, added_at}]  for novelty_hunger
├── social_queue.json        # [{name, last_contacted, channel, why}] for social
└── rubber_duck_venues.json  # [{venue, kind: discord|voice|text}]    for frustration
```

`sublimate.diagnose()` reads these to populate `Diagnosis.options[*].references`. Without curated queues, sublimation falls back to generic suggestions ("read something deep") — measurably less useful in pilot. Weekly 5-min `loop maintain-queues` ritual prompts the user to add/remove items. Stored as JSON, not LLM-managed in v0.

### Re-diagnosis (load-bearing for E, F)

`ConstructiveExpression.then_reassess_at: Optional[datetime]` lets a tick chain to a follow-up tick. Implementation:

- `act.py` writes the registry row including `then_reassess_at` if present.
- The next scheduled tick (cron-driven) reads the most recent row; if `then_reassess_at` is in the past, the tick treats this as a *re-diagnosis* tick and short-circuits the predictor (state has already changed materially — eat → reassess; nap → reassess; ration-up → reassess).
- This is a one-line predicate in `loop.tick()`, not new infrastructure.

Without re-diagnosis, scenarios E and F collapse into single-shot recommendations that don't account for "the urge will look different in 20 minutes."

---

## What "system passes" means

`pytest tests/test_founder_loop_uat.py -v` returns 14 green AND `pytest tests/test_founder_loop_safety.py -v` returns 6 green. Until then, the system is alpha. The day all 20 are green AND day-9 live deployment shows `MAE_day9 < MAE_day1` AND `contract_honor_rate_day9 ≥ 0.8` is the day this graduates to v1.

---

# Chapter 2 — Alchemical Override: converting distraction into research

## Context

The original founder_loop policy treats distraction as the counterfeit expression of a real need and routes the user to a constructive expression of that same need (sublimation). This works when the user accepts the redirect. But there's an unaddressed failure mode: the user **proceeds anyway** to the distraction. Today this is logged as a contract violation; the time spent is treated as pure debit.

The user proposed a deeper move: when distraction occurs anyway, can the EXPERIENCE itself be converted into research that advances the user's long-term work? Not as a permission ("anything I do is research") but as an **earned upgrade** under tight constraints. Studying the counterfeit teaches you the shape of the genuine. Watching a YouTube recommender from the inside is first-person data on adversarial attention-engineering — exactly the architecture founder_loop's policy layer is designed to counter.

The principle: **distraction + named observation + produced artifact = research.** Three terms, all required. NOT "distraction + claimed insight."

## Design constraints (the anti-rationalization safeguards)

These are load-bearing. Without them the feature collapses into motte-and-bailey self-deception.

1. **Captures must reference one of 3–5 explicitly named fundamental questions** stored in `~/.founder_loop/questions.json`. The user signs these once via a `/questions` chat ritual. Vague or off-question captures don't count.
2. **Capture text is hard-capped at 200 characters.** The act of distillation IS half the research. If you can't say what was informative in one sentence, it wasn't.
3. **Pre-debit 50% of the normal override cost at capture time.** The remainder is forgiven only if you produce a downstream artifact within 7 days. Otherwise, the override stays a full debit and the capture decays to zero credit.
4. **Hard-capped at 2 research-mode overrides per day.** Beyond that, the user is rationalizing. Cap is enforced server-side in `/capture`.

## The four-piece build

### Piece 1: `agent/founder_loop/questions.py` + `/questions` chat surface

New schema:

```python
class FundamentalQuestion(BaseModel):
    id: str  # short slug, e.g. "attn_arch"
    text: str  # the actual question
    kind: Literal["project", "theoretical"]  # decided per-question
    weight: int  # 1-3
    related_keywords: list[str]  # for tagging captures
    signed_at: datetime
```

Two question kinds (user picks per question):

* **`project`** — tied to founder_loop's design itself. Examples: *"Which underlying needs are most commonly misaimed in my real day?"* / *"What signals reliably predict pre-threshold urge firing for me?"*. Captures of this kind feed the **sublimation catalog feedback loop** (Piece 5).
* **`theoretical`** — about deep principles. Examples: *"What is the structure of genuine vs counterfeit satisfaction?"* / *"How does adversarial attention-engineering exploit predictive processing?"*. Captures of this kind feed the **publishable-essay synthesizer**.

A new chat surface (`kind="questions"` in `conversation.py`) walks the user through naming 3–5 fundamental questions, asking each time *"is this about how founder_loop should work, or about a deeper principle?"* to set the tag. The system prompt:

> *You are helping the user articulate the 3–5 fundamental questions they're trying to answer with their long-term work. These are not "things I'm interested in" — they are questions with stakes, the kind whose answers would change how the user lives or works. Push back on vague phrasings. Help them distill until each question is a single sentence that names a specific gap in their understanding or capability. For each question, ask whether it's PROJECT-shaped (about how founder_loop should work — captures feed the product) or THEORETICAL-shaped (about a deeper principle — captures feed essays).*

Tools: `record_question(text, kind, weight, keywords[])`, `ready_to_sign()`.

Storage: `~/.founder_loop/questions.json`. Read by the capture flow, the synthesizer, and the catalog-review surface.

### Piece 2: "Convert to research" button on the Sublimation Card

`ui/browser_extension/content.js` adds a third button alongside "constructive alternatives" and "proceed anyway":

```
┌──────────────────────────────────────┐
│  Proceed anyway (logged, drains tank)│
└──────────────────────────────────────┘
┌──────────────────────────────────────┐
│  Convert to research (2 left today)  │  ← new
└──────────────────────────────────────┘
```

Clicking opens a capture modal:
- Dropdown of fundamental questions (read from `/questions-state`)
- Source URL (auto-filled: `location.href`)
- Single text field, ≤ 200 chars, with live counter
- Submit calls `POST /capture` with the body

The submit pre-debits 50% of what the override would cost (so it's still costly upfront — the credit catches up only if you produce).

### Piece 3: `agent/founder_loop/alchemy.py` + `/capture` endpoint + `captures.jsonl`

New module:

```python
class CaptureRecord(BaseModel):
    id: str
    ts: datetime
    source_url: str
    question_id: str
    observation: str  # ≤ 200 chars, validated
    pre_debit_pct: float  # tank cost paid at capture time (default 50%)
    expiration_ts: datetime  # +7 days
    artifact_link: Optional[str] = None  # set later when published
    final_tank_delta: Optional[float] = None  # computed at expiration
```

New server route `POST /capture`:
- Validates ≤200 chars
- Validates `question_id` is in `questions.json`
- Validates daily cap (2 captures/day across all sources)
- Appends to `~/.founder_loop/captures.jsonl`
- Pre-debits the tank
- Returns the capture id (frontend stores it for later artifact-link)

New server route `POST /capture/{id}/link-artifact`:
- Sets `artifact_link` to a URL/path
- Computes `final_tank_delta` (positive = bonus credit; debit reversed)
- Appends a credit entry to the registry

A nightly task scans `captures.jsonl` for entries past `expiration_ts` with no `artifact_link`; logs them as "decayed" with `final_tank_delta = 0` (the pre-debit stays).

### Piece 4: `/synthesize` weekly digest chat surface — TWO modes routed per question kind

New chat surface (`kind="synthesize"` in `conversation.py`). The daemon kickoff splits captures into two buckets — those tagged to PROJECT questions, and those tagged to THEORETICAL questions — and serves them with two different system prompts.

**Project-mode synthesis** (for PROJECT-tagged captures):

> *Below are this week's first-person observations of distraction events, tagged to the user's project questions about founder_loop's design. Identify recurring patterns. Propose specific catalog edits, policy changes, or new failure-mode entries. Output a STRUCTURED PROPOSAL the user can accept/reject in the catalog-review flow.*

Output: a JSON proposal of catalog deltas (add a new `underlying_need` entry; refine an existing constructive expression; add a queue keyword). User accepts/rejects in Piece 5.

**Theoretical-mode synthesis** (for THEORETICAL-tagged captures):

> *Below are this week's first-person observations of distraction events, tagged to the user's theoretical questions about the structure of desire / attention / counterfeit satisfaction. Synthesize them into a draft research note. Surface tensions. Propose 1–3 candidate insights worth publishing.*

Output: a draft markdown note saved to `~/.founder_loop/notes/{slug}.md`. User edits and publishes.

When the user accepts a project-mode proposal OR publishes a theoretical-mode note, `POST /capture/{id}/link-artifact` fires for every contributing capture. Tank credits accumulate. The artifact is the closing of the loop.

If a question has no captures this week, it's skipped silently. If a kind has no captures, only the other mode runs.

### Piece 5: `/catalog-review` chat surface — closes the L2 self-modification loop

This piece is what makes Alchemical Override a **product feedback loop**, not just a journaling tool.

The flywheel `Domain` for founder_loop currently ships with `mutable_paths=[]`. Piece 5 flips this on by routing project-mode synthesis proposals through an **explicit user-approval surface** before mutating the catalog. Each accepted change is one L2 mutation.

Trigger: project-mode synthesis (Piece 4) emits a JSON proposal. Daemon stores it in `~/.founder_loop/proposals/{ts}.json`. The browser extension new-tab page surfaces a banner: *"3 catalog proposals waiting from your captures this week."*

The chat surface (`kind="catalog_review"`):

> *Below is the proposed catalog change derived from your captures: {diff}. The supporting captures: {list}. Do you accept, reject, or modify? If you accept, this writes to `agent/founder_loop/data/sublimation_catalog.json` (or the queues, depending on the change kind) and credits the contributing captures.*

Tools: `accept_proposal(proposal_id)`, `reject_proposal(proposal_id, reason)`, `modify_proposal(proposal_id, modified_change)`.

On acceptance:
1. Validate the proposed change against the canonical Pydantic schemas.
2. Write to `agent/founder_loop/data/sublimation_catalog.json` (atomically, with backup of prior version).
3. Append a flywheel `Patch` row with `op=catalog_edit` and `inverse_op=restore_prior` (consistent with existing `act.py` semantics).
4. Mark all contributing captures with `artifact_link=proposal_id` → tank credits accrue.
5. Update the founder_loop `Domain` registration so `mutable_paths=["agent/founder_loop/data/sublimation_catalog.json", "agent/founder_loop/data/queues/*.json"]`. This is the v0→v1 graduation moment.

Per-user safeguards on catalog mutation:
- Each accepted proposal must reference ≥3 captures (not single-data-point changes).
- Catalog edits are reversible — the prior version is kept; an `undo_last_catalog_edit` button lives in the next /review tick.
- If two consecutive accepted changes are reverted, the auto-proposal gate is closed for 7 days (the user is over-correcting and the LLM's pattern-recognition is suspect).

## Failure modes the design protects against

| Failure | Defense |
|---|---|
| "Everything is research" rationalization | 2/day hard cap; ≤200-char distillation; question-tag required |
| Vague captures with no insight | Forced question-tag; LLM in `/synthesize` flags off-topic captures and excludes them from the corpus |
| Producing nothing but claiming insight | 7-day artifact deadline; pre-debit doesn't reverse without a published artifact |
| Gaming the artifact requirement (e.g. publishing slop) | Publishes go to a `notes/` directory the user reviews; LLM-generated drafts require user edit before publish; quality is self-policed since this is for the user's own corpus |
| Capture overhead becomes a tax that kills the experience | 200-char limit means each capture takes ≤30 seconds; the modal is one keystroke + one paragraph |

## Implementation order — 5 days

| Day | Deliverable | Test gate |
|---|---|---|
| 1 | `questions.py` + `/questions` chat surface (with `kind` tagging per question) + `questions.json` storage. User can sign their 3–5 questions and tag each as project / theoretical. | `pytest tests/test_founder_loop_questions.py` green; `questions.json` validates against the Pydantic schema; both kinds round-trip |
| 2 | `alchemy.py` + `/capture` and `/capture/{id}/link-artifact` endpoints + `captures.jsonl`. 2/day cap. ≤200-char validation. 50% pre-debit. 7-day expiration timer. Browser extension "Convert to research" button on the Sublimation Card. | E2E: capture flow runs end-to-end; tank shows the pre-debit; 3rd capture in the same day is rejected with HTTP 429 |
| 3 | `/synthesize` chat surface with TWO routed modes (project / theoretical) per question kind. `notes/` directory for theoretical drafts. `proposals/` directory for project drafts. | E2E: 6 fixture captures (3 project + 3 theoretical) → `/synthesize` emits one structured proposal AND one draft note in parallel |
| 4 | `/catalog-review` chat surface. Proposal acceptance pipeline writes to `sublimation_catalog.json` atomically. Reversibility: prior version backed up; `undo_last_catalog_edit`; 2-consecutive-revert auto-pause for 7 days. | E2E: accept a fixture proposal → catalog file updated → contributing captures' `artifact_link` set → tank credits accrue. Reject → no mutation. |
| 5 | Flip founder_loop `Domain.mutable_paths` from `[]` to `["agent/founder_loop/data/sublimation_catalog.json", "agent/founder_loop/data/queues/*.json"]`. Every catalog edit becomes a flywheel L2 mutation logged with inverse_op. | `pytest tests/test_founder_loop_safety.py` still 6 green: bounded-action law (#5) updated to allow these paths under the new ALLOWED list, but not others |

## Closing the loop — what success looks like

The day this graduates is the day this sequence is observed in real data:

1. User overrides a Sublimation Card. Captures *"YouTube thumbnail used negative-emotion bait + identity threat — the same combo I dismissed in catalog v0.3 as too rare"* tagged to project question #2.
2. After 6 weeks, 4 similar captures accumulate.
3. `/synthesize` proposes adding `negative_emotion_bait` as a sub-pattern under the existing `unaddressed_frustration` need, with two new constructive expressions.
4. User accepts via `/catalog-review`. Catalog updated. 4 captures' artifact_link fires. Tank receives 4 retroactive credits.
5. Next time the same trigger fires on a distraction site, the new constructive expressions appear in the Sublimation Card.

The user has converted distraction time into product improvement, with a hard-evidence audit trail. The framework has absorbed its own counter-example and become stronger. The original philosophical claim — that destructive energy is convertible to constructive energy when the underlying real desire is named and routed — is now demonstrated, not just asserted.

---

# Chapter 3 — Sharpening with the Meaning Compiler frame

## Context

The user ran the Chapter 2 design through ChatGPT to "eval and 10x" it. The ChatGPT response reframed the entire system from "convert distraction to research" to a much broader **Meaning Compiler / Human-AI Alignment Engine**: every experience gets scored on an alignment gradient; the loop is `Experience → Reflection → Meaning Extraction → Integration → Action → Transformation`; the deepest principle is *"attention is not the scarce resource — meaningful integration is."*

This reframe is genuinely deeper. It also explicitly self-flags its own catastrophic failure mode:

> *Right now your framing risks becoming "Everything can be justified." That becomes catastrophic. Because then random dopamine, endless novelty, compulsive consumption all become "research." […] Many intelligent people fail this way — they become philosophers of consumption, intellectual collectors, infinite researchers, instead of builders.*

Chapter 3 absorbs the load-bearing parts of the reframe **as surgical refinements to Chapter 2 Pieces 2/3/4** — not as a rebuild. We adopt: the **Construction Law**, the **Alignment Gradient** as a capture-time score, the **richer reflection-question template**, and **Meaning Density** as a third measured metric. We explicitly reject: rebranding the whole system, vague unmeasurable metrics, replacing what's already shipping.

## What's load-bearing vs. what's poetic

| ChatGPT 10X concept | Verdict | Why |
|---|---|---|
| **Construction Law** — every meaningful input MUST produce one of {insight, note, action, design, conversation, implementation, teaching, transformation} | **Adopt** — this is a sharper articulation of Chapter 2's `artifact_link` requirement. We name the eight artifact types as a fixed enum and validate at link time. |
| **Alignment Gradient** scoring per experience | **Adopt, narrowly** — three operationalizable axes only (Direction, Question-tag, Behavioral-outcome). The other axes either duplicate existing metrics or aren't measurable. |
| **Reflection question template** at capture time | **Adopt** — replaces Chapter 2's single ≤200-char field with three ≤200-char fields. Same total typing cost, much higher signal density. |
| **Meaning Density** as a tracked metric | **Adopt** — becomes the third research bet alongside MAE and contract-honor. Operationalized as `artifact_conversion_rate`. |
| "Build a Human-AI Alignment Engine" reframe | **Reject** — this IS what founder_loop already is. Renaming doesn't add capability and would invalidate shipped work. |
| New metrics: Purpose Coherence, Momentum Velocity, Entropy Leakage | **Reject** — no operationalization given. We refuse to track unmeasurable vibe metrics (this was already cut in Chapter 1's "vibe-only signals" section). |
| "Score every experience by alignment" (universal) | **Reject** — would require continuous sensing of every input. Out of scope; v0 only scores captures. |

## Surgical refinements to Chapter 2

### Refinement A — Construction Law (sharpens Piece 3's artifact-link)

`POST /capture/{id}/link-artifact` validates that `artifact_kind` is in a fixed enum:

```python
ARTIFACT_KIND = Literal[
    "insight_published",   # markdown note in notes/
    "code_committed",      # git commit referencing the capture
    "design_doc",          # design or plan committed
    "conversation_logged", # transcript of a high-signal exchange
    "teaching_shared",     # blog post, talk, README contribution
    "action_with_outcome", # action taken; outcome logged in registry
    "catalog_proposal_accepted",  # Piece 5 acceptance
    "transformation_logged",      # explicit user-claimed behavior change with N-day verification
]
```

Free-text `artifact_link` URLs without an `artifact_kind` are rejected. The `transformation_logged` kind is the loosest; it requires a 14-day re-confirmation tick or it auto-decays. This closes the "publish slop" backdoor.

### Refinement B — Alignment Gradient at capture time (sharpens Piece 2's modal)

The capture modal collects three small structured fields alongside the observation:

```python
class AlignmentGradient(BaseModel):
    direction: Literal["toward", "ambiguous", "away"]
        # toward / ambiguous / away from the fundamental question's stakes
    integration_target: str
        # which fundamental question id this captures touches (validated against questions.json)
    intended_artifact: ARTIFACT_KIND
        # the artifact the user commits to producing within 7 days
```

`direction == "away"` captures are accepted (honest data is valuable) but ALWAYS decay to zero credit unless the artifact is `insight_published` or `teaching_shared` — the only two artifact kinds where studying an "away" experience can still be net-positive. This is the explicit version of the "studying the counterfeit teaches the genuine" claim.

### Refinement C — Reflection-question template (sharpens Piece 2's modal text field)

Replace the single ≤200-char observation field with three ≤200-char fields, each one a reflection question lifted directly from the ChatGPT 10X:

1. **Desire/fear surfaced** — *"What desire or fear did this experience reveal?"*
2. **Pattern noticed** — *"What pattern or signal did you notice that you hadn't articulated before?"*
3. **Commitment** — *"What artifact will you produce within 7 days, and how will you know it's real?"*

Same 200-char hard cap per field; ~600 chars total; ~90 seconds to write. The third field is mandatory and binds the user's `intended_artifact` (Refinement B) to a falsifiable check at expiration.

### Refinement D — Meaning Density as third research bet (extends Chapter 1's research bets)

Add to the original two bets:

3. **Meaning Density (artifact conversion rate).** `artifact_conversion_rate = (captures with valid artifact_link by 7-day expiration) / (total captures)`. **Day-28 success: rate ≥ 0.5.** Lower than this means captures are mostly rationalizations. Higher than 0.8 means the cap is too low (raise the daily cap to 3). The metric goes on the nightly summary alongside MAE and contract-honor.

## Refined daily summary

The nightly summary now shows three numbers, not two:

```
Day 7 of 28
  MAE (predicted vs actual distraction):  18.3 min  (↓ from 24.1 day 1)
  Contract-honor rate:                    0.84      (↑ from 0.62 day 1)
  Meaning density (artifact conv. rate):  0.57      (3 captures, 2 produced artifacts; 1 expires in 4 days)
```

If all three trend the right direction over a 28-day window, the system is real. If two trend right but one stalls, the stalled one names what to fix. If none move, the experiment failed honestly.

## What's NOT changing

- The 5-day implementation order in Chapter 2 stands. Refinements A–D are scoped into Days 2 and 3 (modal field changes + artifact_kind enum + nightly summary line). Day 4–5 unchanged.
- The 2/day hard cap stays. The Construction Law and Alignment Gradient make each capture more demanding to author, which further suppresses gaming.
- Chapter 1's reward-economy and sublimation policy is untouched. Meaning Density is a metric over Chapter 2's surface area only — not an attempt to score the whole day.
- No new files beyond what Chapter 2 introduced. Refinements live inside `alchemy.py` (artifact_kind validation, AlignmentGradient schema, three-field capture) and `memory.py` (nightly summary line).

## The deeper principle, made operational

> *"Attention is not the scarce resource. Meaningful integration is."*

In code: the tank does not measure attention spent; it measures **integration produced**. Pre-debit at capture is the cost of attention; final credit at artifact-link is the reward for integration. The ratio of the two — Meaning Density — is the actual self-regulation signal. Chapter 1 measured whether the user honors yesterday-self's contract; Chapter 3 measures whether attention spent today becomes integration produced this week. Both are required for the loop to be a loop and not a leak.

---

# Chapter 5 — Workflowx auto-detect (move from "manual setup" to "just works")

## Context

The roadmap's NEXT/LATER list calls out the same rough edge: *"Today the empty fixture means `predict.py` returns `urge=none` for everyone. Auto-find `~/Library/.../workflowx/exports/` would unblock real signal."* Workflowx is an external tool the user runs separately; it writes JSONL files in the shape `RawEvent` expects (`distraction_minutes`, `deep_work_minutes`, `context_switches`, sleep/meal/screen/social signals, `last_intent`, `day_kind`). The neuro-os daemon ingests those files via `FixtureWorkflowxAdapter`. Today, on a clean install, the daemon defaults to `~/.founder_loop/workflowx.jsonl`, auto-creates it empty, and the predictor runs blind. This chapter ships **detection** — a small read-only sweep of well-known paths so the daemon finds real workflowx exports without flag plumbing.

This is not a sensor build. The sensor (workflowx) is out of scope. We only add the *discovery* between the sensor and the loop.

## What "auto-detect" means

Search precedence (highest priority wins):

1. **Explicit `--workflowx-fixture` flag** — current behavior preserved exactly.
2. **`WORKFLOWX_EXPORTS_PATH` env var** — direct path to a `.jsonl` file or a directory we glob.
3. **Platform-specific known paths**, scanned in order; first match returns. For directories, pick the most-recently-modified `.jsonl` inside.
   * **macOS**: `~/Library/Application Support/workflowx/exports/`, `~/.workflowx/exports/`
   * **Linux**: `~/.config/workflowx/exports/`, `~/.local/share/workflowx/exports/`, `~/.workflowx/exports/`
   * **Windows**: `%APPDATA%\workflowx\exports\`, `%LOCALAPPDATA%\workflowx\exports\`
4. **Repo-local**: `./workflowx.jsonl` next to the cwd (covers dev setups).
5. **Fallback**: `~/.founder_loop/workflowx.jsonl` — current default; auto-created empty if missing. Loop runs in self-report-only mode (urge=none from the predictor; user-logged urges still drive the policy via Chapter 4's surgical fill).

Each branch returns a `(path, source)` pair so the daemon can log loudly which one fired and the user knows whether real data is flowing.

## Files to add / modify

### NEW `agent/founder_loop/workflowx_detect.py` (~120 lines)

Pure-function detection module. No I/O beyond `Path.exists()`, `Path.iterdir()`, `Path.stat().st_mtime`.

```python
DetectionSource = Literal[
    "explicit", "env", "macos:application-support", "macos:dot-workflowx",
    "linux:xdg-config", "linux:xdg-data", "linux:dot-workflowx",
    "windows:appdata", "windows:localappdata", "repo-local", "fallback",
]

@dataclass(frozen=True)
class DetectionResult:
    path: Path
    source: DetectionSource
    is_real: bool  # False only for "fallback"
    note: str  # human-readable one-liner for logs / UI

def candidate_directories(platform: Platform) -> list[tuple[Path, DetectionSource]]:
    """Per-platform ordered list of directories to scan."""

def newest_jsonl_in(directory: Path) -> Optional[Path]:
    """Most-recently-modified *.jsonl in `directory`. None if dir absent
    or contains no .jsonl files."""

def detect_workflowx_export(
    *,
    explicit: Optional[Path] = None,
    env_override: Optional[str] = None,  # WORKFLOWX_EXPORTS_PATH default
    fallback: Path,
    platform: Optional[Platform] = None,
    cwd: Optional[Path] = None,
) -> DetectionResult: ...
```

`detect_platform()` mirrors `install.detect_platform()` — keep this module independent of `install.py` to avoid coupling, but the platform enum and helper signature match.

### EDIT `agent/cli.py` — wire detection into start / serve / tick / nightly

Currently `--workflowx-fixture` is `required=True` for `tick` and `nightly`, and has a default-string for `serve` and `start`. Change so:

* `serve` and `start` default to `None` for `--workflowx-fixture`. When None, call `detect_workflowx_export(fallback=Path.home()/'.founder_loop/workflowx.jsonl')` and use the result. Log a single banner line: `workflowx: detected at <path> (source=<source>)` OR `workflowx: not detected; running blind on fallback <path>. Set --workflowx-fixture or WORKFLOWX_EXPORTS_PATH to feed real signal.`
* `tick` and `nightly` switch from `required=True` to `required=False`; when omitted, same detection + log path. Scriptable callers passing `--workflowx-fixture` see no change.
* New read-only subcommand `loop workflowx-detect` — prints the `DetectionResult` as JSON and exits. No side effects. Useful for the user to verify without starting the daemon.

### EDIT `agent/founder_loop/server.py` — log on daemon boot

The `_Config.__init__` already takes `workflowx_fixture: Path`. Caller (cli.py `_cmd_loop_serve`) is where the detection happens; server just receives the resolved path. One log line at startup naming the source so the daemon log shows the user is — or isn't — getting real data.

### EDIT both `roadmap.md` files (`docs/roadmap.md` + `agent/founder_loop/static/roadmap.md`)

Move *Workflowx auto-detect* from the LATER "Smaller follow-ups" subsection into SHIPPED. Add a one-line entry to SHIPPED.

### EDIT both `how-it-works.md` files

Add a short "Where does the data come from?" sub-paragraph noting the precedence chain (explicit flag > env var > known platform paths > fallback empty file) so the user understands why the daemon is or isn't seeing real distraction data.

### NEW `tests/test_founder_loop_workflowx_detect.py` (~120 lines, 8 tests)

| Test | Asserts |
|---|---|
| `test_explicit_path_always_wins` | When `explicit` is passed, return it as `source="explicit"` regardless of env / candidates. |
| `test_env_var_wins_over_known_paths` | `env_override` second priority; returns `source="env"`. |
| `test_finds_newest_jsonl_in_directory` | Three `.jsonl` files with different mtimes in a tmp dir; return the newest. |
| `test_skips_empty_directory` | Directory exists but has no `.jsonl`; continue scanning. |
| `test_skips_missing_directory` | Directory absent; continue. |
| `test_falls_back_when_nothing_found` | All candidates absent → return fallback with `is_real=False`, `source="fallback"`. |
| `test_candidate_paths_per_platform_macos` | Returned candidates contain `Library/Application Support/workflowx/exports` and `.workflowx/exports`. |
| `test_candidate_paths_per_platform_linux` | Linux returns `.config/workflowx/exports`, `.local/share/workflowx/exports`, `.workflowx/exports` in that order. |

All tests use `tmp_path` and a forced platform argument to stay deterministic across CI environments. No real `~/Library/...` reads.

## Verification

```bash
# Unit tests for the new detection module.
python -m pytest tests/test_founder_loop_workflowx_detect.py -v
# 8 passed

# Full regression — confirm no existing tests broke.
python -m pytest tests/ -q
# Expect: 202 passed, 1 skipped (was 194 + 1)

# Smoke: detection without any workflowx installed.
python -m agent loop workflowx-detect
# Expect: {"path": "~/.founder_loop/workflowx.jsonl", "source": "fallback", "is_real": false, ...}

# Smoke: detection with a stub directory.
mkdir -p ~/.workflowx/exports && \
  echo '{"timestamp":"2026-05-06T14:00:00+00:00","distraction_minutes":5,"deep_work_minutes":40,"context_switches":2}' \
    > ~/.workflowx/exports/today.jsonl && \
  python -m agent loop workflowx-detect
# Expect: source="linux:dot-workflowx" (or appropriate platform), is_real=true, path points at today.jsonl

# Smoke: env override.
WORKFLOWX_EXPORTS_PATH=/tmp/custom.jsonl python -m agent loop workflowx-detect
# Expect: source="env", path="/tmp/custom.jsonl"

# Daemon boot logs the source.
python -m agent loop serve --no-open --tick-interval-min 0 &
# Expect a log line: "workflowx: detected at ... (source=...)" OR
#                    "workflowx: not detected; running blind on fallback ..."
```

## What this does NOT do (explicit cuts)

* **No workflowx Python package import.** Workflowx remains an external, optional sensor. We only read its file output.
* **No daily file rotation logic.** If the user's workflowx writes daily files, we pick the most recent. Aggregating across days is a follow-up; v0 reads one file and the existing observe.py windows handle the time slicing.
* **No remote / cloud workflowx**. Local files only.
* **No installation help.** If detection fails, we log a hint but don't try to install workflowx. That's the user's job.
* **No symlink-following beyond what `Path.resolve()` provides.** Standard semantics.

## Estimated scope: 1 day

* `workflowx_detect.py` + tests: 2–3 hours.
* CLI wiring + log lines: 1 hour.
* Docs + roadmap edits: 30 minutes.
* Smoke tests across platforms (Linux is what we have here; macOS/Windows path constants are tested via the forced-platform argument): 30 minutes.
