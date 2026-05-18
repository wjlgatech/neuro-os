# Neuro-OS

**What it is** — a local, self-modifying knowledge OS that catches your daily drift modes and converts them into evidence-graded decisions. Four verticals (Founder Loop / Research / Investment / Startup) on one substrate, plus **five compounding mechanisms** layered on top: corpus ingestion, dashboard, cross-vertical entity graph, cross-modal Belief OS, and skillify (catalog evolution from real overrides).
**Who it's for** — solo founders, researchers, calibrated investors, and indie builders who want one closed loop instead of five disconnected tools.
**Status** — v0.7 shipped: Founder Loop is the daily product; Research / Investment / Startup expose CLI + cross-vertical reads; ingestion and dashboard work without gbrain (`--prefer local`); skillify accumulates override evidence; anchors track faith / relational pillars. 100% local; no telemetry. **523 tests pass.**
**Try it** — `pip install neuro-os && neuro-os start` (boots at `127.0.0.1:8765`).
**Contribute** — read [`CONTRIBUTING.md`](./CONTRIBUTING.md) (humans) or [`CLAUDE.md`](./CLAUDE.md) (AI agents).

---

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

### Start here (returning after time away, or first visit)

| Doc | For whom | What's in it |
|---|---|---|
| [**STATUS**](./docs/STATUS.md) | Paul, Claude, anyone re-orienting | Auto-generated kitchen whiteboard: one-sentence north-star, the 3 most recent ships, what's active this week, what's parked but real, link table to every plan. Run `neuro-os status` to print it in your terminal. Regenerated on every commit by the pre-commit hook — staleness is structurally impossible. |

### For Founder Loop users (the daily product)

| Doc | For whom | What's in it |
|---|---|---|
| [**What is this?**](./docs/what-is-this.md) | Anyone curious | The metaphor stack — the deal, the score, the reward, the underlying needs. Plain English, ~800 words. |
| [**How to use it**](./docs/how-to-use-it.md) | Daily users | Five moments — start your day, check in, when you're tempted, look back, tweak the rules. With sketches. |
| [**How it works**](./docs/how-it-works.md) | Curious + contributors | Five-box architecture (sensors → brain → contract → carrot/stick → memory) in plain language. One diagram. |
| [**Roadmap**](./docs/roadmap.md) | Anyone | Feature-tier SHIPPED / NEXT / LATER per lane. Different scope from STATUS.md (north-star + active focus); both coexist by design. |

### For contributors and integrators

| Doc | For whom | What's in it |
|---|---|---|
| [**E2E test catalog**](./tests/e2e/scenarios.md) | Contributors | 29 scenarios (26 deterministic + 3 judgment) describing user journeys with personas, steps, expected outcomes — covers all four verticals. |
| [**E2E test runner README**](./tests/e2e/README.md) | Contributors | How to run the HTTP / Playwright / Computer Use harnesses. |
| [**Browser extension README**](./ui/browser_extension/README.md) | Power users | Manifest V3 setup, how the Sublimation Card injects, how the badge polls. |
| [**Tray app README**](./ui/tray_app/README.md) | Power users | Cross-platform tray icon (Linux / macOS / Windows). |
| [**Streamlit UI README**](./ui/README.md) | Researchers | The 4-tab Streamlit app: Try It / Watch It Learn / Self-Repair / Readiness. |
| [**AI-Native engineering principles**](./docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md) | Contributors | The 10 non-negotiable laws, each tagged `[ENFORCED-by-test/type/runtime]` or `[ASPIRATIONAL]`. |
| [**CONTRIBUTING.md**](./CONTRIBUTING.md) | Human contributors | One-page fast path: setup, the gates to run, where to put new code, the 3-section commit format, what NOT to do. |
| [**CLAUDE.md**](./CLAUDE.md) | AI agents writing code | The L1 prompt-time gate: where to put new code, what NOT to do, the commit-message format, how to add or revise a law. |
| [**Principle enforcers**](./tests/test_engineering_principles.py) | Contributors / CI | The L3 test-time gate: 8 deterministic checks for Laws 1, 3, 4, 5, 6, 7, 9. Run with `pytest tests/test_engineering_principles.py`. |

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
| `neuro-os loop urge entertainment --context "..." [--override-of <mode>]` | Log a user-reported urge. With `--override-of`, also auto-emits a skillify `OverrideEvent` so the catalog-evolution loop gets data from your daily flow. |
| `neuro-os loop anchor --kind {faith,relational} --context "..."` | Append a faith or relational anchor to the daily log. `count_anchors_per_day()` renders "5/7 days hit" on the dashboard. |
| `neuro-os loop nightly` | End-of-day rollup: prediction MAE, contract-honor rate, entertainment minutes used, sublimation success rate. |
| `neuro-os research ingest --prefer local --source-dir ~/reading/` | Native LLM extractor: walks `.txt` / `.md` / `.pdf` files → emits `MechanismCardProposal`s. No gbrain required. |
| `neuro-os research review --cli` | REPL for accepting / rejecting proposals (Law-7 human gate); accept prompt asks for entity slugs. |
| `neuro-os research dashboard --window 7` | Compound-curve rollup: drift histogram, stick-rate, never-fired catalog signal, action queue. |
| `neuro-os cross-vertical share-note --note-id <id> --with investment` | Broaden a note's visibility (research → invest hand-off, etc.). Default is private. |
| `neuro-os skillify extract --vertical research` | Aggregate ≥5 same-mode overrides into a `SkillProposal` candidate for `/catalog-review`. |

For step-by-step setup with screenshots, see [**How to use it**](./docs/how-to-use-it.md).

### Knowledge OS (the engine, in 60 seconds)

The fastest visualisation is the Streamlit app — five tabs, each a distinct lens on the system. Click any thumbnail to see the [full tour in `ui/README.md`](./ui/README.md).

| Tab | Screenshot |
|---|---|
| 🟢 Try It | [![Try It](ui/assets/01_try_it.png)](./ui/README.md#-try-it--paste-a-sentence-watch-it-classified) |
| 🌱 Watch It Learn | [![Watch It Learn](ui/assets/03_watch_learn.png)](./ui/README.md#-watch-it-learn--feed-a-contradiction-see-the-ontology-shift) |
| 🔧 Self-Repair (animated) | ![Self-repair animation](ui/assets/self_repair.gif) |
| 📊 Readiness | [![Readiness](ui/assets/05_readiness.png)](./ui/README.md#-readiness--does-my-x-have-what-neuro-os-needs) |

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
pytest                                  # 523 tests pass, 12 skipped
```

**More UI surfaces:**
- [Streamlit app tour](./ui/README.md) — 60-second intro with the 5 screenshots above
- [Browser extension](./ui/browser_extension/README.md) — Manifest V3, sublimation card on 8 distraction hosts
- [System tray app](./ui/tray_app/README.md) — cross-platform tank gauge (Linux / macOS / Windows)

Architecture deep-dive: [**How it works**](./docs/how-it-works.md).

---

## What this gives you

### Foundation (engine + four verticals)

1. **Closed-loop self-modification** — the system patches its own routing logic, sandbox-validated, with rollback baked in. Every patch goes through an op allowlist (`ALLOWED_OPS`) AND a path allowlist (`mutable_paths`) — both AND, not OR. → [Engineering principles](./docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md), `agent/self_modification.py`.
2. **Self-evolving knowledge loop with golden gate** — ingest text, detect contradictions, validate refinements, persist learning. Knowledge updates that would degrade classification on canonical inputs are rolled back even if their TRUE scores look perfect. → `agent/self_evolving_loop.py`, `tests/test_adoptions.py`.
3. **Pluggable Domain abstraction** — apply the same OEC machinery to any classification problem in 30 lines. A domain bundles ontology + golden cases + extractor + validators + mutable_paths. → `examples/04_custom_domain.py`.
4. **Belief OS as a primitive** — a contradiction-aware reasoning ontology built on the L1 loop. Six reasoning patterns (Bayesian updating, base-rate reasoning, falsifiability, expected value, second-order thinking, survivorship bias). Designed for *other products* to consume. → `agent/belief_os.py`, `examples/07_belief_os_consumer.py`.
5. **Founder Loop** — the daily reward-economy + sublimation product. Six underlying needs, three queue types (bookmarks, social, rubber-duck), four nightly metrics (MAE, contract-honor, entertainment-min, sublimation-success). → [**What is this?**](./docs/what-is-this.md), [**How to use it**](./docs/how-to-use-it.md).

### Five compounding mechanisms (Lanes 1-5, each shippable end-to-end)

Each mechanism plugs into the four-vertical substrate and starts paying off *as soon as you start using it*. Each is verified by its own test suite and documented in [`docs/how-it-works.md`](./docs/how-it-works.md#the-five-compounding-mechanisms).

| Lane | Capability | Where to look |
|---|---|---|
| **1 — Corpus ingestion** | Two extractors share one queue: `--prefer gbrain` (Plan B, `garrytan/gbrain` MCP) OR `--prefer local` (Plan A, native Anthropic Haiku + regex fallback for `.txt`/`.md`/`.pdf`). Auto-detect picks per invocation. → `agent/research/{ingest,gbrain_adapter,ingest_router,proposals}.py` |
| **2 — Skillify (catalog evolution)** | Repeated overrides on the same drift mode become a `SkillProposal` for `/catalog-review`. Law 7 honored: catalog mutation stays a separate human commit. `loop urge --override-of <mode>` auto-emits the override event in one command. → `agent/skillify/` |
| **3 — Cross-modal Belief OS** | Fan a decision through K scorers (default 3); disagreement above threshold raises a `low_confidence_warning` stronger than any single flag. Injectable scorers; tests pin every consensus path. → `agent/cross_modal.py` |
| **4 — Entity propagation** | First-class `Entity` schema in `cross_vertical.py` with the same default-PRIVATE invariant as `VerticalNote`. Accepting a `MechanismCard` prompts for entity slugs; `share_entity` broadens visibility. → `agent/cross_vertical.py` (`Entity`, `upsert_entity`, `share_entity`, `read_entity`, `list_entities`) |
| **5 — Dashboard** | Pure-aggregation rollup (`registry.jsonl` + `ingestion_runs.jsonl` + `proposals/*` + `mechanism_cards/*`) → compound curve, drift histogram, stick-rate, **drift modes that NEVER fired** (catalog candidates), action queue. → `agent/research/dashboard.py` |

```python
# Belief OS as a primitive — Founder OS approval-gate pattern
from agent.belief_os import check_decision_text

gate = check_decision_text("Drop out — Jobs and Gates dropped out and became billionaires.")
if gate.flag_for_review:
    raise ApprovalRequired(gate.flag_reason)  # → "survivorship_bias"
```

```python
# Lane 3 — same decision through 3 models (the disagreement signal)
from agent.cross_modal import run_cross_modal_check, make_default_scorers
from agent.investment import PositionThesis, run_cross_modal_bias_check

bias_check, eval_record = run_cross_modal_bias_check(thesis=my_thesis)
if eval_record.low_confidence_warning:
    print(f"3-model disagreement on this thesis ({eval_record.disagreement_score:.2f}) — review")
```

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
│   ├── cross_modal.py              # Lane 3 — K-scorer fan-out + CrossModalEval
│   ├── cross_vertical.py           # Lane 4 — Entity + share_entity + share_note
│   ├── domain_app/                 # the substrate (4 verticals layer on this)
│   ├── founder_loop/               # the daily product
│   │   ├── server.py               # local HTTP daemon
│   │   ├── conversation.py         # /onboard, /review, /queues chat surfaces
│   │   ├── sublimate.py            # diagnose underlying need
│   │   ├── policy.py               # carrot/stick decision tree
│   │   ├── anchors.py              # PR-2 — faith / relational daily anchors
│   │   ├── urge_log.py             # user-logged urge events
│   │   └── data/                   # sublimation_catalog.json + queues
│   ├── research/                   # research vertical
│   │   ├── ingest.py               # Plan A — native LLM extractor (.txt/.md/.pdf)
│   │   ├── gbrain_adapter.py       # Lane 1 — Plan B (gbrain MCP)
│   │   ├── ingest_router.py        # picks gbrain vs local per invocation
│   │   ├── proposals.py            # MechanismCardProposal queue + transitions
│   │   ├── dashboard.py            # Lane 5 — pure-aggregation rollup
│   │   └── ontology.py / catalog.py
│   ├── investment/                 # investment vertical (advisory-only)
│   ├── startup/                    # startup vertical
│   ├── skillify/                   # Lane 2 — catalog evolution from override events
│   │   ├── events.py               # OverrideEvent + write/read
│   │   ├── proposals.py            # SkillProposal queue
│   │   └── extract.py              # bucket → threshold-gate → SkillProposal
│   └── data/priority_rules.json    # the only file L2 is allowed to mutate
├── docs/                           # plain-English docs (linked above)
├── tests/                          # 523 pass, 12 skipped: unit + 26 e2e + 9 principle-enforcers
├── examples/                       # 9 runnable scripts (incl. cross-vertical demo)
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
