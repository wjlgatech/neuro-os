# Neuro-OS

> A self-evolving, self-modifying knowledge OS plus **four verticals** running on a shared `agent/domain_app/` substrate. Each vertical is the same closed-loop OEC machine (Observe → Evaluate → Control → Validate) with different vocabulary.

## Four verticals on one substrate

| Vertical | Audience | Primary metric | Primary resource | 6 named failure modes |
|---|---|---|---|---|
| **Founder Loop** (`agent/founder_loop/`) | Solo founders fighting distraction | prediction MAE | entertainment minutes | fatigue / novelty / social / frustration / decision_fatigue / embodied |
| **Research** (`agent/research/`) | Researchers turning paper-collecting into recursive world-model refinement | mechanism cards/day | papers read | paper_collector / topic_hopper / memorizer / authority_acceptor / overloaded / forgetting |
| **Investment** (`agent/investment/`) ⚠️ advisory-only | Investors converting emotional reactions into epistemic calibration | calibration error | position edits | emotional / narrative_following / price_obsessed / overconfident / social_proof_following / ego_attached |
| **Startup** (`agent/startup/`) | Founders converting reactive chaos into market-aligned convergence | strategic continuity score | thesis pivots | idea_chaos / broadcasting / feature_creep / vision_intoxicated / vanity_metrics / random_execution |

Plus the underlying **Knowledge OS** engine (L1 self-evolving ontology + L2 self-modification with allowlisted patches, sandboxed validation, one-step rollback).

The substrate (`agent/domain_app/`) enforces, for every vertical:
* Exactly **6 named failure modes**, each with **≥1 constructive expression** (substrate raises at construction otherwise).
* **4 first-class metrics** + an `extra: dict` for vertical-specific (anti-metric-overload).
* **`Confidence` enum** shared (low / medium / high) — no parallel float scales.
* **`ContractCheck`** on every action (audit trail).

The cross-vertical interface (`agent/cross_vertical.py`) lets one vertical read another's outputs — **default-PRIVATE**; explicit `share_with=[...]` to broaden. Investment positions, startup confidentials, and research IP stay in their own vertical unless the user opts in. See `examples/09_cross_vertical_demo.py` for an end-to-end research → investment hand-off with the privacy boundary verified.

---

## 📚 Documentation

Start here. All detailed docs live behind these links:

### For Founder Loop users (the daily product)

| Doc | For whom | What's in it |
|---|---|---|
| [**What is this?**](./docs/what-is-this.md) | Anyone curious | The metaphor stack — the deal, the score, the reward, the underlying needs. Plain English, ~800 words. |
| [**How to use it**](./docs/how-to-use-it.md) | Daily users | Five moments — start your day, check in, when you're tempted, look back, tweak the rules. With sketches. |
| [**How it works**](./docs/how-it-works.md) | Curious + contributors | Five-box architecture (sensors → brain → contract → carrot/stick → memory) in plain language. One diagram. |
| [**Roadmap**](./docs/roadmap.md) | Anyone | Three honest columns: SHIPPED / NEXT / LATER. No vapor. |

### For contributors and integrators

| Doc | For whom | What's in it |
|---|---|---|
| [**E2E test catalog**](./tests/e2e/scenarios.md) | Contributors | 23 scenarios (20 deterministic + 3 judgment) describing user journeys with personas, steps, expected outcomes. |
| [**E2E test runner README**](./tests/e2e/README.md) | Contributors | How to run the HTTP / Playwright / Computer Use harnesses. |
| [**Browser extension README**](./ui/browser_extension/README.md) | Power users | Manifest V3 setup, how the Sublimation Card injects, how the badge polls. |
| [**Tray app README**](./ui/tray_app/README.md) | Power users | Cross-platform tray icon (Linux / macOS / Windows). |
| [**Streamlit UI README**](./ui/README.md) | Researchers | The 4-tab Streamlit app: Try It / Watch It Learn / Self-Repair / Readiness. |
| [**AI-Native engineering principles**](./docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md) | Contributors | The 10 non-negotiable laws, each tagged `[ENFORCED-by-test/type/runtime]` or `[ASPIRATIONAL]`. |
| [**CLAUDE.md**](./CLAUDE.md) | AI agents writing code | The L1 prompt-time gate: where to put new code, what NOT to do, the commit-message format, how to add or revise a law. |
| [**Principle enforcers**](./tests/test_engineering_principles.py) | Contributors / CI | The L3 test-time gate: 8 deterministic checks for Laws 1, 3, 4, 5, 6, 7, 9. Run with `pytest tests/test_engineering_principles.py`. |
| [**Agent-system research notes**](./docs/AGENT_SYSTEM_RESEARCH_HERMES_OPENCLAW.md) | Researchers | External-pattern review (Hermes, OpenClaw) translated into Neuro-OS decisions. |

---

## 🚀 Quickstart

### Founder Loop (the daily product)

```bash
pip install neuro-os
neuro-os start
```

That boots the local daemon on `127.0.0.1:8765`, **auto-detects your workflowx export** (or falls back honestly to an empty fixture), and opens [`/onboard`](http://127.0.0.1:8765/onboard) in your browser. Set `ANTHROPIC_API_KEY` and pass `--use-llm` for the natural-language flow; otherwise it falls back to a state machine.

| Daily commands | What it does |
|---|---|
| `neuro-os start` | Boot the daemon + open `/onboard`. Auto-detect workflowx. Auto-tick every 60 min. |
| `neuro-os autostart install` | Run on every login (launchd / systemd-user / Task Scheduler). `--dry-run` previews. |
| `neuro-os loop urge entertainment --context "..."` | Log a user-reported urge from the terminal. The next tick honors it as ground truth. |
| `neuro-os loop workflowx-detect` | Read-only: print where the daemon will look for workflowx. |
| `neuro-os loop nightly` | End-of-day rollup: prediction MAE, contract-honor rate, entertainment minutes used, sublimation success rate. |

For step-by-step setup with screenshots, see [**How to use it**](./docs/how-to-use-it.md).

### Knowledge OS (the engine, in 60 seconds)

The fastest visualisation is the Streamlit app:

![Self-repair animation](ui/assets/self_repair.gif)

```bash
git clone https://github.com/wjlgatech/neuro-os.git
cd neuro-os
pip install -e ".[ui]"
streamlit run ui/app.py
```

Or stay in the terminal:

```bash
python -m agent extract "Dopamine neurons encode reward prediction error signals."
python examples/03_self_repair.py      # watch the system fix itself
pytest                                  # 222 tests, 12 skipped
```

Architecture deep-dive: [**How it works**](./docs/how-it-works.md). Streamlit tabs: [**ui/README.md**](./ui/README.md).

---

## What this gives you

Five capabilities, each verified by tests. For the deep-dive on any one, follow the link.

1. **Closed-loop self-modification** — the system patches its own routing logic, sandbox-validated, with rollback baked in. Every patch goes through an op allowlist (`ALLOWED_OPS`) AND a path allowlist (`mutable_paths`) — both AND, not OR. → [Engineering principles](./docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md), `agent/self_modification.py`.
2. **Self-evolving knowledge loop with golden gate** — ingest text, detect contradictions, validate refinements, persist learning. Knowledge updates that would degrade classification on canonical inputs are rolled back even if their TRUE scores look perfect. → `agent/self_evolving_loop.py`, `tests/test_adoptions.py`.
3. **Pluggable Domain abstraction** — apply the same OEC machinery to any classification problem in 30 lines. A domain bundles ontology + golden cases + extractor + validators + mutable_paths. → `examples/04_custom_domain.py`.
4. **Belief OS as a primitive** — a contradiction-aware reasoning ontology built on the L1 loop. Six reasoning patterns (Bayesian updating, base-rate reasoning, falsifiability, expected value, second-order thinking, survivorship bias). Designed for *other products* to consume. → `agent/belief_os.py`, `examples/07_belief_os_consumer.py`.
5. **Founder Loop** — the daily reward-economy + sublimation product. Six underlying needs, three queue types (bookmarks, social, rubber-duck), four nightly metrics (MAE, contract-honor, entertainment-min, sublimation-success). → [**What is this?**](./docs/what-is-this.md), [**How to use it**](./docs/how-to-use-it.md).

```python
# Belief OS as a primitive — Founder OS approval-gate pattern
from agent.belief_os import check_decision_text

gate = check_decision_text("Drop out — Jobs and Gates dropped out and became billionaires.")
if gate.flag_for_review:
    raise ApprovalRequired(gate.flag_reason)  # → "survivorship_bias"
```

---

## Repository layout

```
neuro-os/
├── agent/                          # the engine
│   ├── api.py / cli.py             # process_text, ingest_documents, neuro-os CLI
│   ├── domains.py                  # Domain abstraction
│   ├── self_evolving_loop.py       # L1 (knowledge loop)
│   ├── self_modification.py        # L2 (code loop)
│   ├── patches.py                  # ALLOWED_OPS, apply_patch, inverses
│   ├── belief_os.py                # reasoning-pattern primitive
│   ├── founder_loop/               # the daily product
│   │   ├── server.py               # local HTTP daemon
│   │   ├── conversation.py         # /onboard, /review, /queues chat surfaces
│   │   ├── sublimate.py            # diagnose underlying need
│   │   ├── policy.py               # carrot/stick decision tree
│   │   ├── workflowx_detect.py     # auto-detect platform paths
│   │   ├── urge_log.py             # user-logged urge events
│   │   └── data/                   # sublimation_catalog.json + queues
│   └── data/priority_rules.json    # the only file L2 is allowed to mutate
├── docs/                           # plain-English docs (linked above)
├── tests/                          # 234 total: unit + 23 e2e + 9 principle-enforcers
├── examples/                       # 8 runnable scripts
├── ui/                             # Streamlit + browser extension + tray app
└── pyproject.toml
```

---

## Contributing

The smallest unit of value-add is one of:

* **A new patch op.** ~30 lines: handler + entry in `ALLOWED_OPS` + paired inverse + a test in `tests/test_self_modification.py`.
* **A new domain.** A `Domain(...)` + `register_domain(...)` + a golden set. See `examples/04_custom_domain.py`.
* **A new validator.** A `Callable[[str], dict]` returning `{success, ...}`. Pytest, ruff, type checks, shadow traffic — anything you can run in a subprocess.
* **A new e2e scenario.** Add it to [`tests/e2e/scenarios.md`](./tests/e2e/scenarios.md) with a stable ID, then implement in the matching harness.

Run the tests with `pytest`. Mutations must keep the suite green. The non-negotiable laws are in [**AI-Native engineering principles**](./docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md).

---

## Safety properties

Verified by the test suite:

| Property | Test |
|---|---|
| Unknown ops are refused without filesystem touch | `tests/test_self_modification.py::test_unknown_op_is_refused` |
| Targets outside `mutable_paths` are refused | `tests/test_self_modification.py::test_patch_op_refuses_paths_outside_allowlist` |
| Patches that regress goldens are rolled back; live tree untouched | `tests/test_adoptions.py::TestGoldenGate::test_loop_reverts_merge_when_goldens_regress` |
| Daemon refuses non-loopback bind | `tests/test_founder_loop_server.py` |
| Malformed workflowx JSONL is skipped, not crashed on | `tests/e2e/test_http_scenarios.py::test_S15_malformed_workflowx_skips_bad_lines` |
| User-logged urge overrides predictor's "none" | `tests/test_founder_loop_golden_2pm.py::test_user_logged_urge_overrides_predictor_predicting_none` |

Operating principles: sandbox-first, one mutation per tick, reversible (every promotion logs a `rollback_patch`), provenance (every mutation lands in `versions/version_registry.jsonl`).

---

## License

MIT — see `pyproject.toml`.

*Built on the OEC pattern from `agent/self_evolution_controller.py` (Observe → Evaluate → Control → Validate). Closed by `agent/self_modification.py`. Daily-product surface is `agent/founder_loop/`.*
