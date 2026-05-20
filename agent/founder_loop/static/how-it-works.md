# How it works

You don't need to read this to use the app. This is for people
who want to know what's inside, or who might contribute. Some of it
will sound technical near the end, but the first half should be fine
for anyone curious.

---

## Neuro-OS is one substrate, four instances

Neuro-OS ships **four verticals** — Founder Loop, Research, Investment
(advisory-only), Startup. They are not four separate codebases. They
are **one substrate** (in `agent/domain_app/`) and **four small
adapters** (in `agent/founder_loop/`, `agent/research/`,
`agent/investment/`, `agent/startup/`) that wire the same five-box
control loop to each vertical's vocabulary.

The substrate enforces, for every vertical:

- A typed daily **contract** (Pydantic, `frozen=True`).
- Exactly **6 named failure modes** ("drift modes") per vertical.
- ≥1 **constructive expression** option per failure mode.
- A **tank** that scores progress against the contract.
- A nightly **4-metric summary** + a `extra: dict` for vertical-specific signals.

Each vertical fills in the vocabulary; the loop is identical.

The whole thing is **five boxes** wired in a loop — the same five
boxes for all four verticals, just with different words on the
labels:

```
                              YESTERDAY-YOU
                                  │
                                  ▼
                          ┌───────────────┐
                          │   CONTRACT    │
                          │  (the deal)   │
                          └───────┬───────┘
                                  │
                                  ▼
   ┌───────────┐    ┌────────┐    ┌──────────────┐    ┌────────┐
   │  SENSORS  │ ─► │ BRAIN  │ ─► │ CARROT/STICK │ ─► │ MEMORY │
   │ (observe) │    │(predict│    │  (policy +   │    │(record │
   │           │    │  + dx) │    │   action)    │    │ + learn)│
   └───────────┘    └────────┘    └──────────────┘    └────┬───┘
                                                           │
                                                           ▼
                                                       TODAY-YOU
                                                     (sees the result)
                                                           │
                                                           ▼
                                                       TOMORROW
                                                  (signs a new contract)
```

The next section explains each box using **Founder Loop** as the
worked example (it's the most polished surface today). Then we show
the **per-vertical vocabulary table** — same five boxes, four
instances. Then we cover the **cross-vertical privacy boundary**.

---

## The five boxes — Founder Loop as the worked example

## Box 1 — **Sensors** *(what the app knows about your day)*

Every hour, the app wakes up and reads what you did. Right now it
reads from a workflowx export file — a log of "you spent 35 min on
this, 5 min on that, you switched contexts 4 times." If you don't
have workflowx, the file is empty and the app has no signal; it
guesses based on your past trajectory and asks you for intent.

**Where the app finds workflowx (auto-detect precedence):**

1. An explicit `--workflowx-fixture` flag wins everything.
2. The `WORKFLOWX_EXPORTS_PATH` environment variable (file or
   directory).
3. Platform-specific known directories — first match returns the
   most-recently-modified `.jsonl` inside:
   * macOS: `~/Library/Application Support/workflowx/exports/`,
     `~/.workflowx/exports/`
   * Linux: `~/.config/workflowx/exports/`,
     `~/.local/share/workflowx/exports/`, `~/.workflowx/exports/`
   * Windows: `%APPDATA%\workflowx\exports\`,
     `%LOCALAPPDATA%\workflowx\exports\`
4. Repo-local `./workflowx.jsonl` (dev convenience).
5. Fallback: `~/.founder_loop/workflowx.jsonl` (auto-created empty;
   the loop runs blind unless you log urges manually).

The daemon logs which branch fired at boot, so you always know
whether real signal is flowing. Run `neuro-os loop workflowx-detect`
without starting the daemon to print the result as JSON.

**The other channel is you.** When workflowx is silent (or wrong)
and you feel an urge anyway, you can tell the app directly:

```
neuro-os loop urge entertainment --context "want YouTube"
```

This writes to `~/.founder_loop/founder_events.jsonl` as a
`UrgeEvent`. The next tick reads recent events (15-minute window by
default) and treats your reported urge as **ground truth** — the
predictor's guess is overridden, the diagnosis runs against the
state, and the Sublimation Card surfaces in the dashboard. The
browser extension's "I'm tempted right now" button uses the same
mechanism via `POST /events`.

In the future, sensors include: sleep from your watch, last-meal time,
hours-of-screen-time, time-since-last-message-sent. The more sensors,
the better the diagnoses.

*Code: `agent/founder_loop/observe.py`,
`agent/founder_loop/workflowx_detect.py`,
`agent/founder_loop/urge_log.py`*

---

## Box 2 — **Brain** *(predict + diagnose)*

Two things happen here:

1. **Predict the next hour.** Based on what you just did, what you've
   done over the last 7 days, and what you said you wanted to do —
   how much distraction is incoming? What kind of urge is firing?
   This part runs Claude (an AI) when you have an API key, otherwise
   it falls back to a simple trajectory average.

2. **Diagnose the underlying need.** If an urge is firing, *which* of
   the six is it? Fatigue? Novelty-hunger? Social? Frustration?
   Decision-fatigue? Hunger? The diagnosis isn't from the AI alone;
   there's a small rule-book ("if sleep < 6.5 hours, fatigue") that
   triages, and the AI confirms or overrides.

The brain doesn't *do* anything yet — it just produces a forecast and
a diagnosis.

*Code: `agent/founder_loop/predict.py`, `agent/founder_loop/sublimate.py`*

---

## Box 3 — **Contract** *(yesterday-you's signature)*

The contract is what you signed this morning. It contains:

- Your **priorities** (1–5) — each with a tangible "done" signal.
- Your **entertainment ration** — how much YouTube/etc. you unlock at
  90% completion.
- The **threshold** — usually 90%.
- A few internal knobs that almost no one needs to touch.

The contract is just a JSON file at `~/.founder_loop/contracts.jsonl`
with one line per day. You don't write this by hand; the morning chat
on `/onboard` does.

The app keeps a running **tank score** by reading your activity log
and the contract together: how much progress have you made on the
priorities (credits)? How much have you done that drains the tank
(debits, like overriding a sublimation card)? The tank is a function
of these two, capped at 100%.

*Code: `agent/founder_loop/contract.py`,
`agent/founder_loop/priorities.py`,
`agent/founder_loop/reward_ledger.py`*

---

## Box 4 — **Carrot / Stick** *(what to do about the urge)*

This is where the brain meets the contract. The decision tree, in
plain language:

```
Is an urge firing? ──► No  ──► continue (do nothing)
                  └─► Yes ─┐
                           ▼
        Is the tank ≥ 90% ?
        ├─ Yes, within ration ──► UNLOCK ENTERTAINMENT (with timer)
        ├─ Yes, ration done   ──► gentle nudge, re-diagnose what's left
        └─ No                  ──► PROPOSE CONSTRUCTIVE EXPRESSION
                                   (the Sublimation Card)
```

Crucially, the carrot/stick layer **never blocks**. The "stick" is
that override-anyway costs tank-credits. You always retain agency.

*Code: `agent/founder_loop/policy.py`, `agent/founder_loop/act.py`*

---

## Box 5 — **Memory** *(records and learns)*

Every tick (every hour, or when you visit a distraction site) writes a
line to `~/.founder_loop/registry.jsonl`. Each line has the state, the
prediction, the action, whether the contract was honored, and the
delta to the tank.

At the end of the day, the **nightly summary** reads the whole day and
computes four numbers:

- **MAE** — Mean Absolute Error between what the brain predicted and
  what you actually did. Lower over time = the AI is learning you.
- **Contract-honor rate** — what fraction of decisions today went the
  way yesterday-you wanted. Higher over time = today-you is
  increasingly willing to keep the deal.
- **Entertainment minutes used** — total entertainment time consumed
  today (honored unlocks AND overrides combined).
- **Sublimation success rate** — of times the system proposed a
  constructive alternative, what fraction "stuck" — i.e. you didn't
  override the contract afterwards. The signal that says whether the
  philosophy is actually working.

The summary also surfaces **goldens failed** — pre-defined "the system
is broken if X" rules. Triggers a rebuild of either the predictor
prompt or the sublimation catalog when ≥2 fire in a 7-day window.

You see all four numbers in the `/review` chat page kickoff, and the
same numbers via `neuro-os loop nightly` in the terminal.

*Code: `agent/founder_loop/memory.py`,
`agent/founder_loop/golden_cases.py`*

---

## The same five boxes — four vocabularies

Every vertical instantiates the same five-box loop with its own
words. The substrate (`agent/domain_app/`) factors out the machinery;
each adapter fills in the vocabulary.

| Box | Founder Loop | Research | Investment *(advisory-only)* | Startup |
|---|---|---|---|---|
| **Contract** | Priorities + entertainment ration | At-most-one-paper + active thesis (40-day) | Position theses + invalidation conditions | Active hypothesis (40-day) + audience-signals goal |
| **Sensors** | workflowx exports + browser extension urges | Manual paper-extraction events | Manual position-edit events; chart-watching events | Manual audience-signal events; pivot urges |
| **Brain (drift modes)** | fatigue / novelty / social / frustration / decision-fatigue / embodied | paper-collector / topic-hopper / memorizer / authority-acceptor / overloaded / forgetting | emotional / narrative-following / price-obsessed / overconfident / social-proof / ego-attached | idea-chaos / broadcasting / feature-creep / vision-intoxicated / vanity-metrics / random-execution |
| **Carrot/Stick** | Sublimation Card; entertainment unlock at 90% | Constructive expression (extract → MechanismCard); continuity score rises | Belief OS bias check; defer 24h; falsification-condition prompt | Park-the-idea; reaffirm active hypothesis; pivot tax |
| **Memory** | MAE + contract-honor + entertainment minutes + sublimation success | mechanism cards/day + continuity score + prediction-log entries + assumption-map updates | calibration error + thesis survival + bias-detection rate + decision consistency | strategic continuity + trust density + audience signals + conversion quality |

The **substrate** (`agent/domain_app/state.py`,
`agent/domain_app/protocol.py`, `agent/domain_app/app.py`) defines:

- `ConstructiveExpressionBase` — the frozen Pydantic shape every
  vertical's options must conform to.
- `DiagnosisCatalogProtocol` — the contract for "give me the 6 needs
  and the options for any one of them."
- `DomainConfig` — the contract for "give me a vertical's name,
  catalog, and resource label."
- `DomainApp` — the orchestrator. Three hooks (`morning_ritual`,
  `tick`, `nightly`) delegate vertical-specific shape to the adapter
  while keeping `make_diagnosis`, `compute_tank`, and audit-trail
  logic shared.

Each vertical's adapter provides a `make_<vertical>_app(home=...)`
factory that returns a `DomainApp` wired with that vertical's
catalog, ontology, and morning/tick/nightly hooks. Founder Loop's
adapter (`agent/founder_loop/domain_app_adapter.py`) is the most
recent and the simplest — it wraps the existing
`sublimation_catalog.json` to satisfy `DiagnosisCatalogProtocol`
without invasive refactor; the deeper structural collapse is on the
roadmap.

---

## The five compounding mechanisms

Layered on top of the four-vertical substrate are five mechanisms that turn a daily ritual into a system that **gets sharper as you use it**. Each is independently testable; each plugs into the same Pydantic schemas the four verticals share. They are not part of the five-box loop — they consume its outputs (registry rows, accepted cards, override events) and produce typed artifacts the user reviews.

```
                    ╔═══════════════════════════════════════════╗
                    ║   THE FIVE-BOX LOOP (per vertical) above  ║
                    ║   produces:                               ║
                    ║     - registry.jsonl                      ║
                    ║     - mechanism_cards/*.json              ║
                    ║     - urge events / override evidence     ║
                    ╚════════════════╤══════════════════════════╝
                                     │
        ┌─────────┬──────────────┬───┴────────────┬──────────────────┐
        ▼         ▼              ▼                ▼                  ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌─────────────┐
  │ Lane 1:  │  │ Lane 5:  │  │ Lane 4:  │  │   Lane 3:    │  │  Lane 2:    │
  │ Corpus   │  │  Daily   │  │ Cross-   │  │ Cross-modal  │  │ Skillify    │
  │ ingest   │  │  rollup  │  │ vertical │  │ Belief OS    │  │ (catalog    │
  │          │  │          │  │ entity   │  │ (K-scorer    │  │ evolution)  │
  │ files →  │  │ "what's  │  │ graph    │  │ disagree-    │  │             │
  │ proposals│  │ trending"│  │          │  │ ment signal) │  │ overrides → │
  │          │  │          │  │          │  │              │  │ SkillProp   │
  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  └─────────────┘
       │             │              │              │                 │
       │             │              │              │                 │
       └─ each goes through a ──────┴── Law-7 human gate ─────────────┘
          (accept / reject / share — never auto-applied)
```

### Lane 1 — Corpus ingestion

Two extractors share one downstream queue. The router (`agent/research/ingest_router.py::detect_extraction_method`) picks per invocation based on `--prefer {auto,gbrain,local}`:

- **Plan B** (`gbrain-mcp`) — `agent/research/gbrain_adapter.py`. Reads a `gbrain export` JSON file, validates each entity through a frozen `GbrainEntity`, translates to `MechanismCardProposal`. Conservative skip policy (non-claims, thin excerpts, no causal verb) keeps the queue clean. Zero LLM calls in v0; gbrain does the heavy lifting upstream.
- **Plan A** (`llm-anthropic`) — `agent/research/ingest.py`. Walks `.txt`/`.md`/`.pdf` files, extracts text (PDFs via pure-Python `pypdf`), runs ONE Anthropic Haiku call per source with a structured-output Pydantic schema. Falls back to a regex heuristic when no API key is set (emits low-confidence proposals so the reviewer knows the LLM didn't run).

Both write to `~/.neuro_os_research/proposals/pending/` — same `MechanismCardProposal` schema, same `research review --cli` REPL. The user accepts / rejects (Law 7); accepted proposals become `MechanismCard` rows.

*Code: `agent/research/{ingest,gbrain_adapter,ingest_router,proposals}.py`. Tests: `tests/test_research_ingest_plan_a.py`, `tests/test_research_gbrain_adapter.py`, `tests/test_research_proposals.py`.*

### Lane 2 — Skillify (catalog evolution from real overrides)

Skillify watches for `OverrideEvent`s — typed records that say "the substrate proposed X, the user did Y instead." After ≥N (default 5) overrides on the same `(vertical, drift_mode)` bucket within a window (default 30 days), `skillify extract` proposes a new `ConstructiveExpression` candidate (`SkillProposal`).

The `SkillProposal` lives in `~/.neuro_os_skillified/proposals/pending/` for human review via `skillify review --cli`. Acceptance moves the file to `accepted/` — **it does NOT auto-mutate the catalog**. The catalog change is a separate human-authored commit. Law 7 (human-in-loop truth control) holds.

Override evidence collection: `loop urge --override-of <drift_mode>` writes both a `UrgeEvent` AND a skillify `OverrideEvent` in one CLI call. Without this flag, the override log stays empty and skillify never proposes anything — the auto-emission flag is the load-bearing piece.

*Code: `agent/skillify/{events,proposals,extract}.py`. Tests: `tests/test_lane2_skillify.py`.*

### Lane 3 — Cross-modal Belief OS (disagreement is the signal)

The single-model bias check (`agent/belief_os.py::check_decision_text`) has one failure surface: that one model's blind spots. Lane 3 fans the same decision text through K independent scorers (default 3 — Haiku / Sonnet / Opus) and computes a `disagreement_score`.

Disagreement above a threshold (`DISAGREEMENT_WARNING_THRESHOLD = 0.34`, i.e. any 1-of-3 minority) raises a `low_confidence_warning` that's a stronger "pause and look" signal than any single scorer's flag. When the panel agrees, the consensus verdict carries normal weight; when it disagrees, the `BiasCheck.reason` is prefixed with `[low_confidence: cross-modal disagreement]` so the nightly summary surfaces it.

Scorer callables are injectable. The default 3-pair panel calls `check_decision_text` with three different `llm_model` hints; tests use `make_fixture_scorers` for deterministic K-scorer scenarios. Parallel execution is a follow-up (sequential is fine for K=3 today).

*Code: `agent/cross_modal.py`, `agent/investment/config.py::run_cross_modal_bias_check`. Tests: `tests/test_lane3_cross_modal.py`.*

### Lane 4 — Cross-vertical entity graph

`Entity` is a typed page (`slug` / `kind` / `title` / `compiled_truth` / `mentioned_in_note_id`) that multiple verticals may reference. Same default-PRIVATE invariant as `VerticalNote`: an entity written by research is INVISIBLE to investment / startup / founder_loop unless explicitly shared.

`MechanismCardProposal` and `MechanismCard` carry an `entity_mentions: List[str]` field. The `research review --cli` accept prompt asks the user for entity slugs; for each, `upsert_entity` writes a new `Entity` row (default-PRIVATE to research). `share_entity(slug, add_visible=[...])` broadens visibility for ALL prior + future rows of that slug; reads from other verticals start succeeding after the share event.

Storage uses the existing `~/.neuro_os/cross_vertical.jsonl` store with a separate `row_kind: "entity"` discriminator (so it doesn't collide with `Entity.kind`). Append-only — multiple upserts of the same slug build a timeline; `read_entity` returns the latest visible snapshot.

*Code: `agent/cross_vertical.py` (`Entity`, `EntityKind`, `upsert_entity`, `share_entity`, `read_entity`, `list_entities`). Tests: `tests/test_lane4_entity_propagation.py`.*

### Lane 5 — Daily dashboard

A pure-aggregation rollup over the artifacts the other lanes already write. NEVER writes; reading the dashboard is idempotent.

Inputs (read-only):
- `registry.jsonl` — drift events + `propose_constructive_expression` ops
- `ingestion_runs.jsonl` — Lane 1 audit log
- `proposals/{pending,accepted,rejected}/*.json` — current queue snapshot
- `mechanism_cards/*.json` — accepted cards (the primary metric)
- `synthesis/runs/*.json` — Layer 2 synthesis runs (cluster counts)
- `briefs/*.json` — Layer 3 decision briefs (Meaning Density)
- `checkpoints.jsonl` — stop-condition convergence events

Outputs (frozen `DashboardSummary`):
- Compound curve: today / 7-day-avg / window-avg / trend (`up` / `flat` / `down` with 5% hysteresis)
- Drift-mode counts + top-3 ASCII histogram
- **`drift_modes_never_fired`** — modes the catalog claims exist but didn't fire in the window. Strong evidence the catalog is wrong.
- Constructive-expression stick-rate: same drift_mode + same primary_action within 7 days = stuck; same drift_mode + DIFFERENT primary_action = override
- Lane 1 ingestion totals (sources scanned, proposals emitted vs accepted vs rejected)
- Action queue (pending count + oldest age in hours)
- **Three-Layer Research OS signals** (research vertical only): `tier_balance` (seed / frontier / lateral / unknown), `verdict_histogram` (foundational / useful / misleading / skip / unrated), `synthesis_run_count`, `briefs_produced_in_window`, `latest_checkpoint_converging`, `checkpoint_no_streak`, and `system_health_flags`
- **`system_health_flags`** — `chaser_mode` / `hoarder_mode` / `rubber_stamping` / `no_synthesis` / `system_not_converging`. Each fires only on unambiguous evidence (sample-size guards prevent small-corpus noise).

*Code: `agent/research/dashboard.py`. Tests: `tests/test_research_dashboard.py`, `tests/test_research_three_layer.py`.*

### Layer 1 / 2 / 3 / 4 / 5 — Five-Layer Research OS (research vertical)

Lane 1 (above) is the per-paper extraction. The Three-Layer extension turns accumulated cards into decision-grade output; Layers 4 and 5 close the **compression → expression → refine** loop from the TRUE-E3 Living Knowledge Framework, so a compressed principle isn't just a static summary — it can be re-expanded into new forms, and what each form reveals feeds back into the schema:

- **Layer 1 deepening.** `MechanismCardProposal` and `MechanismCard` gained five optional fields beyond the original 4-tuple (`mechanism / invariant / prediction / failure_mode`): `first_principle`, `anti_pattern`, `transferability_test`, `verdict ∈ {foundational, useful, misleading, skip}`, `one_sentence_compression`. Plus a generic `framework_alignment: list[FrameworkAxisNote]` where the user's framework axes — supplied by hand in `~/.neuro_os_research/framework.json` — flow through unchanged. **The substrate refuses to hard-code a framework**; a Physical-AI reader uses {Observation, Evaluation, Control, Continual}; a value investor uses {Moat, Distribution, Unit economics}; the schema is the same.

- **Layer 2 — `agent/research/synthesis.py`.** Clusters accepted MechanismCards by their underlying causal **mechanism, not by topic**. Heuristic Jaccard clusterer + LLM clusterer (Anthropic Haiku, structured output). Frozen `MechanismCluster` + `SynthesisRun` schemas; runs persist at `synthesis/runs/<run_id>.json`. *This module is a Plan-A-style placeholder — the long-term backend is graphify (the separate graph-knowledge project); the follow-up PR is an adapter that delegates to graphify and falls back to the in-tree heuristic / LLM modes.*

- **Layer 3 — `agent/research/briefs.py`.** Given one `MechanismCluster` + a user-supplied `ProjectContext` (project_name, current_questions, collaborators, pending_decisions), generates a `DecisionBrief` (project_implications / next_decisions / next_experiments / questions_for_collaborators). LLM mode + heuristic templated mode. Persists at `briefs/<brief_id>.{json,md}`.

- **Checkpoint — `agent/research/checkpoints.py`.** After each synthesis cycle, two binary signals: `brief_produced` AND `mental_model_clearer`. Either-NO twice in a row → dashboard prints `system_not_converging`. This is the falsifiability gate the Research OS uses on itself; without it, the system can become a beautiful trap.

- **Layer 4 — `agent/research/compress.py`.** Builds a 3-level hierarchy from a `SynthesisRun`. **Level 0** is the core schema (3–5 nodes, highest abstraction); **Level 1** is one node per `MechanismCluster` (≤30); **Level 2** is one node per accepted `MechanismCard`. Each level points at its children; Level 1 nodes carry their parent_id (an L0 node), Level 2 nodes carry theirs (an L1 node). When >5 clusters exist, the L0 rollup groups them by overlapping `framework_axes_touched`, then merges smallest pairs until ≤5. Frozen `HierarchicalCompression`; persists at `~/.neuro_os_research/compressions/<id>.json`. Pure function — re-running on the same synthesis input produces identical structure (modulo `compression_id` and `created_at`).

- **Layer 5 — `agent/research/expression.py`.** Records that a compressed node was instantiated in one of 7 modalities (`visual / musical / physical / organizational / game / biological / narrative`). Content is text only — a prompt, code, pseudocode, or markdown spec — plus a `tool_hint` naming the external renderer (Tone.js, p5.js, Isaac Sim, etc.). Then a separate `reveal_expression` call closes the feedback loop: attach the insight the expression surfaced, optionally point at a node in the same compression to refine. **The reveal is the load-bearing claim**: without it, expression is decoration; with it, the cycle is generative. Validates that the source node and feedback target actually exist in the named compression so revealings can't dangle. Persists at `~/.neuro_os_research/expressions/<id>.json`.

*Code: `agent/research/{framework,synthesis,briefs,checkpoints,compress,expression}.py`. Tests: `tests/test_research_three_layer.py`, `tests/test_research_compress.py`, `tests/test_research_expression.py`.*

What the Five-Layer Research OS is NOT (intentional scope):

- *Not VR or embodied (E1 in TRUE-E3).* Walking the compressed graph in 3D space is a heavy lift with no near-term Phase-1 paper payoff; deferred.
- *Not interactive parameter dashboards (E2 in TRUE-E3).* Streamlit is in the repo but isn't wired to compressed principles.
- *Not a rendering engine.* The expression layer stores text + a tool hint. If you want a Tone.js track, an Isaac Sim scene, or a p5.js animation, you pipe the `content` field to the named tool yourself — neuro-os is the schema-keeper, rendering lives at the edges. This is deliberate: it lets the schema evolve without dragging multimedia deps into the core.

---

## MCP server (drive neuro-os from any AI agent)

`agent/mcp_server.py` exposes the high-leverage CLI surface as **Model Context Protocol** tools so any MCP-compatible AI agent — Claude Code, Cursor, `mcp-cli`, anything that speaks MCP stdio — can call neuro-os directly. The repo's `.mcp.json` at the root wires Claude Code automatically when started from a checkout that has `pip install -e ".[mcp]"`.

Tool list (9 tools, mirrors the load-bearing CLI subcommands): `research_ingest` / `research_synthesize` / `research_brief` / `research_checkpoint` / `research_dashboard` / `loop_anchor` / `loop_urge` / `cross_vertical_share_note` / `cross_vertical_query`.

Design choices:

- **Stdio transport.** No new network surface; the agent runs `neuro-os-mcp` as a subprocess and speaks MCP over stdin/stdout. The existing HTTP daemon at 127.0.0.1:8765 is unchanged.
- **Thin wrappers.** Each tool calls an existing `agent.*` function and returns the result as JSON. The MCP layer carries no business logic; the substrate is the single source of truth.
- **Optional dependency.** The `mcp` SDK is in `pyproject.toml` extras (`pip install -e ".[mcp]"`); the core install stays small.
- **No telemetry.** If a tool would call Anthropic (e.g. `research_synthesize` LLM mode), the call originates from the wrapped function, not the MCP layer.

*Code: `agent/mcp_server.py`. Config: `.mcp.json` at repo root. Tests: `tests/test_mcp_server.py`.*

---

## Cross-vertical privacy boundary

Each vertical writes to its own home dir
(`~/.founder_loop/`, `~/.neuro_os_research/`,
`~/.neuro_os_invest/`, `~/.neuro_os_startup/`). **Default is
private.** A research note is invisible to investment unless the
user explicitly shares it.

The boundary is enforced in `agent/cross_vertical.py`:

- Every shareable record is a `Shareable[T]` wrapping a payload
  plus a `share_event: ShareEvent` with `from_vertical`,
  `to_verticals: list[str]`, `consent_at: datetime`. Frozen.
- Only records with `to_verticals` containing the reader's vertical
  are visible to it. The default is `to_verticals=[]` (private).
- Reads go through `read_shared(reader_vertical, records)` which
  filters and returns a plain list. There is no other read path; if
  a vertical wanted to bypass it, it would have to import the
  payload type directly from another vertical's package, which the
  test in `tests/test_cross_vertical_e2e.py` flags as a violation.
- Sharing is a typed action: `share(payload, to_verticals=[...])`
  produces a new `Shareable`. There is no "broaden later" — extending
  visibility requires emitting a new share event with provenance.

The CI gate (`tests/test_cross_vertical_e2e.py`) has a
**privacy-assertion test** that constructs records in each vertical
and proves the others can't read them by default. If a future change
relaxes this, the test fails CI.

*Code: `agent/cross_vertical.py`, `tests/test_cross_vertical_e2e.py`*

---

## How it learns over time

The system has three feedback loops:

1. **Daily** — the predictor's prompt-cache hits accumulate; cheap
   improvements just by you being a recurring user.
2. **Weekly** — when goldens fail, the nightly summary suggests
   rewriting the predictor prompt or the sublimation catalog. v0
   surfaces this as a recommendation; v1 will apply it automatically
   under flywheel's L2 self-modification machinery.
3. **Per-session** — the chat onboarding adapts to your phrasing
   inside a single conversation (e.g. you say "PR" the first time
   and "pull request" the third; Claude handles both).

The L2 self-modification is the deepest part of the loop and the part
most under construction. See `docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md`
for the laws governing it. v0 ships `mutable_paths=[]` for all
verticals; promotion is per-vertical and gated.

---

## How the UIs fit in

**Founder Loop** has the deepest UI (browser extension + tray app + 3 chat
surfaces). **Research** now has 2 browser surfaces too (review + the
Living Knowledge spatial tree). **Investment** has a read-only browser
dashboard. **Startup** is still CLI-only. All surfaces use the same
Python engine.

**The full UI surface set:**

| Surface | Vertical | What it shows | Read more |
|---|---|---|---|
| **Browser extension** (Manifest V3) | Founder Loop | Toolbar badge + popup + new-tab dashboard + sublimation overlay on 8 distraction hosts. Polls `/tank` every 5 min; calls `/tick` when you visit a distraction host; mounts the Sublimation Card if the diagnosis fires. | [`ui/browser_extension/README.md`](../ui/browser_extension/README.md) |
| **System tray app** | Founder Loop | Cross-platform menu-bar gauge (Linux / macOS / Windows). Polls the daemon every 60s; renders tank %; click for tick / show contract / quit. | [`ui/tray_app/README.md`](../ui/tray_app/README.md) |
| **`/onboard` chat** | Founder Loop | Morning ritual: chat through today's priorities, sign the contract. Falls back to state-machine without an Anthropic key. | [how-to-use § Moment 1](how-to-use-it.md#moment-1--start-your-day) |
| **`/review` chat** | Founder Loop | Nightly review: chat through what happened, sign tomorrow's contract. | [how-to-use § Moment 4](how-to-use-it.md#moment-4--look-back) |
| **`/queues` chat** | Founder Loop | Curate bookmarks/social/rubber-duck queues. 30-second undo banner on AI-driven mutations. | [how-to-use § Moment 5](how-to-use-it.md#moment-5--tweak-the-rules) |
| **`/research/living-knowledge`** | Research | Spatial 3-level tree (L0 cores → L1 clusters → L2 cards), expression modals, single-turn chat-assist (brainstorm + interview). | [how-to-use § Browser UI for Layer 4+5](how-to-use-it.md#browser-ui--researchliving-knowledge) |
| **`/research/review`** | Research | Front-door for accepting / rejecting `MechanismCardProposal` rows. Expandable cards, entity-mention input, recently-resolved section. | [how-to-use § Research](how-to-use-it.md#research--for-a-researcher-building-a-world-model) |
| **`/invest/dashboard`** | Investment | Read-only rollup: cost-of-living coverage, options PnL, thesis correct rate, sleeve allocation bars, health-flags list with rationale. | [how-to-use § Investment dashboard](how-to-use-it.md#investment-dashboard) |
| **Streamlit app** (engine only) | (substrate) | Five tabs: Try It / Watch It Learn / Self-Repair / Readiness / About. NOT the daily-product surface; this is for understanding the engine itself in 60 seconds. | [`ui/README.md`](../ui/README.md) |

The CLI surface (`neuro-os ...`) is the universal fallback — every
operation a browser surface does, the CLI does too. The Startup
vertical is still CLI-only; its browser surfaces are roadmapped.

**Cross-origin security inheritance:** every browser surface above
goes through the same daemon dispatcher that PR #34 hardened. The
daemon refuses cross-origin browser requests (origin allowlist +
`Sec-Fetch-Site` check) before reaching any handler. A malicious
webpage cannot read or mutate any neuro-os state — research,
investment, or founder_loop — via the daemon, even while the daemon
is running.

```
       Browser extension                  System tray app                  Chat surfaces
  ┌──────────────────────┐         ┌──────────────────────┐         ┌──────────────────────┐
  │  Toolbar badge       │         │  Menu bar gauge      │         │  /onboard (morning)  │
  │  Popup dashboard     │         │  Always-visible      │         │  /review  (nightly)  │
  │  New tab dashboard   │         │  Quick actions       │         │  /queues  (curate)   │
  │  Sublimation overlay │         │                      │         │                      │
  │  (Founder Loop only) │         │  (Founder Loop only) │         │  (Founder Loop only) │
  └──────────┬───────────┘         └──────────┬───────────┘         └──────────┬───────────┘
             │                                │                                │
             │  HTTP                          │  HTTP                          │  HTTP
             │                                │                                │
             ▼                                ▼                                ▼
                          ┌───────────────────────────────────────┐
                          │   Local daemon  127.0.0.1:8765        │
                          │   (refuses non-loopback bind)         │
                          │                                       │
                          │   GET /tank, /contract, /today        │
                          │   GET /tick                           │
                          │   POST /chat, /sign, /diagnose        │
                          │   POST /events                        │
                          └─────────────────┬─────────────────────┘
                                            │
                                            ▼
                                ┌───────────────────────────────────┐
                                │     Python engine (one process)   │
                                │  ┌────────────────────────────┐   │
                                │  │  agent/domain_app/         │   │  ← substrate
                                │  └─────────────┬──────────────┘   │
                                │                │ DomainConfig     │
                                │   ┌────────────┴────────────┐     │
                                │   ▼      ▼       ▼          ▼     │
                                │ founder research invest  startup  │  ← 4 adapters
                                └───────────────────────────────────┘

       neuro-os {research,invest,startup} {onboard,tick,nightly}    (CLI for the other 3)
```

The daemon is one Python process. The browser/tray/chat UIs are dumb
clients that talk HTTP to it. The CLI verticals invoke the engine
directly without going through the daemon. This means:

- You can build a phone app, a Discord bot, an Apple Watch
  complication — they all just talk HTTP to the same daemon.
- If you replace the daemon with a hosted service (you wouldn't —
  privacy), the UIs don't change.
- If you replace the UIs with a single CLI, the engine doesn't change.
- A research/invest/startup chat UI can be built later without
  touching the substrate, because the substrate already exposes
  the same `morning_ritual` / `tick` / `nightly` shape Founder Loop's
  surfaces consume.

---

## What's special about this design

Four things, none of which are revolutionary alone, but the
combination is the actual product:

1. **The control loop is closed against a contract you signed.** Most
   productivity tools have a "rule"; this one has a "contract." The
   former is external; the latter is your own promise to yourself.
2. **The action layer prefers proposing alternatives over blocking.**
   Most habit apps treat distraction as the problem to suppress; this
   one treats distraction as a misaimed legitimate desire and tries to
   route the desire to a constructive expression.
3. **One substrate, four vocabularies.** The same closed loop is
   applied to four different lives (working / reading / investing /
   building) without a per-vertical fork. New verticals are an
   adapter, not a codebase.
4. **The whole thing runs on your laptop and is auditable.** Every
   decision, every override, every diagnosis is one line in a JSONL
   file you own. You can read it. You can delete it. No vendor sees
   it. Cross-vertical reads default-private and require explicit
   opt-in per record.

---

## What's still being built

See [the roadmap](./roadmap.md) for the honest list of what works
today vs. what's coming. Highlights:

- **Founder Loop:** browser/tray/chat surfaces shipped; refining.
- **Research / Investment / Startup:** CLI surface shipped; chat
  surfaces roadmapped; structural founder_loop refactor onto the
  substrate (replacing the adapter with subclassing) roadmapped.
- **40-day live trial across all four verticals** — the eval gate
  for "the substrate is real, not a coincidence."

Anything missing here? Open an issue. The five-box diagram is the
mental model we want to keep clean even as features grow underneath
it; if a future feature doesn't fit one of the five boxes, we should
question whether it belongs.
