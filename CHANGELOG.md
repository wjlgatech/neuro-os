# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic
Versioning](https://semver.org/spec/v2.0.0.html).

## [0.10.1] — API-key help modal on chat surfaces

The API-key pill on the chat surfaces (`/onboard` / `/review` / `/queues`)
is now clickable when in fallback mode. Clicking opens a small help
modal that explains where to get an Anthropic key, how to export
`ANTHROPIC_API_KEY` in the shell, and how to restart the daemon so the
new key takes effect. Documentation only — no in-app credential paste,
no new daemon route accepting credentials. The env var stays the
canonical mechanism, which keeps the daemon's HTTP surface
credential-free (no POST endpoint to attack even with CORS hardening).

Closes the audit gap surfaced after the audit closed: the pill said
"no API key — fallback mode" with no path forward for the user.

Single file: `agent/founder_loop/static/onboard.html`. No server
changes. No new tests (existing 721-pass suite confirms no
regression).

## [0.10.0] — Design-audit round-trip: polish + safety pass, research review, invest dashboard

Three PRs (#37, #38, #39) close all 10 fixes from the `/design-consultation`
structural audit against the 5 axes (consistency, completeness, simplicity,
simplicity-of-clarity, efficiency, safety). 722 tests pass after the
round-trip, up from 687 before.

### Added — design-audit polish + safety pass (#37; fixes 2-7, 9, 10)

- **Living Knowledge UI (`/research/living-knowledge`)**:
  - L0/L1/L2 legend at the top of the tree explains the hierarchy in
    one line (was opaque to first-time users).
  - Modality dropdown options carry `title=` tooltips + a live `.help`
    text under the dropdown that updates on change — each of the 7
    modalities now has a one-line explanation of what it reveals.
  - Delete button on the expression-detail modal: `confirm()` →
    `POST /research/living-knowledge/delete` → 30-second undo banner
    anchored to the page; clicking Undo calls
    `POST /research/living-knowledge/restore`. Deletes move the file
    to `expressions/_trash/` (soft-delete), so even after the undo
    window closes the file is recoverable manually.
  - `?` help-link in the header deep-links to `/how-to-use` anchored
    at the Layer 4 + 5 section.
- **Chat surfaces (`/onboard` / `/review` / `/queues`)**:
  - API-key pill in the header matching the Living Knowledge page
    (green = LLM ready, amber = fallback mode, red = daemon offline).
    Trust signal: the user always knows whether their content goes to
    Anthropic.
  - `?` help-link deep-linking to `/how-to-use` anchored per kind
    (morning / review / queues).
  - **Sign-overwrite confirmation**: when today's contract is already
    bound, the first Sign click shows a red warning banner; only the
    second click actually overwrites. Prevents misclick regret.
  - **Queue-mutation undo**: the `/queues` chat snapshots the queue
    state via `GET /queues-state` before each AI turn that might
    mutate, then surfaces a 30-second undo banner if mutations
    happened. Clicking Undo posts the snapshot back via a new
    `POST /queues-restore` route that overwrites the queue files
    atomically.
- **Browser extension popup + newtab**:
  - Static tank-percentage legend explaining the reward economy in
    plain English with a link to `/how-it-works`. Static HTML so the
    explanation is visible even before the popup's JS modules load.
- **New server routes** (all on the founder_loop daemon, inheriting
  the daemon's CORS hardening from PR #34):
  - `POST /research/living-knowledge/delete` (soft-delete expression)
  - `POST /research/living-knowledge/restore` (move from _trash/ back)
  - `POST /queues-restore` (rewrite queue JSON files from snapshot)
- **New module helpers** in `agent/research/expression.py`:
  `soft_delete_expression`, `restore_expression`, `trash_dir`.

### Added — research-review browser surface (#38; audit Fix 1)

- New daemon route at `/research/review` mirroring `research review --cli`
  1:1 with a browser-friendly UI. 4 routes total:
  - `GET /research/review` — HTML page
  - `GET /research/review/data` — JSON with `pending` + `recently_accepted` + `recently_rejected`
  - `POST /research/review/accept` — builds frozen MechanismCard, transitions proposal to accepted, upserts entity mentions
  - `POST /research/review/reject` — transitions proposal to rejected
- UI shows pending proposals as expandable cards (paper title +
  one-sentence + verdict badge + confidence). Expanding reveals the
  full extraction (mechanism / invariant / prediction / failure_mode +
  Layer-1 deepening + extractor reasoning + source excerpt + entity
  mentions input).
- Entity mentions normalize on accept: lowercase + strip + drop empty.
- CLI and browser surface share the same on-disk proposal store —
  writes via either surface are visible to the other.

### Added — invest dashboard browser view (#39; audit Fix 8)

- New daemon route at `/invest/dashboard` rendering the
  `InvestmentDashboardSummary` as a one-glance read. 2 routes:
  - `GET /invest/dashboard` — HTML page
  - `GET /invest/dashboard/data?window=N` — JSON rollup (window clamped to [1, 365])
- 3 stat cards (cost-of-living coverage with bar, options PnL with
  sign, thesis correct rate), options strategy breakdown table,
  mega-trend sleeve allocation bars (concentrated sleeves >40%
  highlighted in amber), system-health-flags list with severity
  colors + inline rationale for each of the 5 flags.
- **Advisory-only** pill in the header. The anti-goal (no broker
  integration, no trade execution) is unchanged.

### Tests

- 34 new tests across the three PRs:
  - `tests/test_living_knowledge_ui.py` — +9 (delete + restore + queues-restore + their CORS regression)
  - `tests/test_research_expression.py` — +5 (soft_delete + restore unit tests)
  - `tests/test_research_review_ui.py` — +13 (new file)
  - `tests/test_invest_dashboard_ui.py` — +7 (new file)
- Full suite: **722 passed**, 1 deselected (pre-existing Anthropic
  API quota failure, unrelated). Engineering principles (Laws 1-9)
  all green.

### Honest gap flagged (out of scope)

The browser extension's `popup.html` and `newtab.html` reference
`lib/api.js` and `lib/card.js` that don't exist in the repo. The
`FounderLoopUI` global the JS modules expect is therefore undefined —
the dynamic tank widget is pre-existing-broken. The static
tank-percentage legend added in #37 works regardless. Worth a
separate investigation.

## [0.9.0] — Living Knowledge UI: spatial hierarchy + chat-assist

Browser UI for Layer 4 + Layer 5 of the research vertical. The founder_loop
daemon now serves a new route `/research/living-knowledge` (alongside the
existing `/onboard` / `/review` / `/queues` chat surfaces) that renders the
latest compression as a navigable 3-level tree, with chat-assist for two
moments where conversation actually beats a form: brainstorming expression
content, and crystallizing what an expression revealed.

- **Daemon routes** (`agent/founder_loop/server.py`):
  - `GET /research/living-knowledge` — serves the SPA HTML
  - `GET /research/living-knowledge/data` — JSON: `{ compression, expressions[] }`
  - `POST /research/living-knowledge/express` — record_expression
  - `POST /research/living-knowledge/reveal` — reveal_expression (close the loop)
  - `POST /research/living-knowledge/chat` — single-turn brainstorm or interview
- **UI** (`agent/founder_loop/static/research-living-knowledge.html`): vanilla
  HTML/CSS/JS, no external assets, no new deps. Same dark-mode aesthetic as
  `onboard.html`. Spatial tree (L0 row → L1 region under selected L0 → L2
  cards under selected L1), sidebar with detail + expressions tabs, three
  modals (express, reveal, expression detail).
- **Chat-assist** (single-turn, stateless):
  - *Brainstorm* — given an L0/L1/L2 node + modality, suggests 3 ways to
    instantiate the principle in that modality. Pre-fills nothing; just
    surfaces angles.
  - *Interview* — given the expression's content and modality, asks one
    probing question, then crystallizes the user's observation into a
    `reveals` string for the feedback loop.
  - Both fall back to a deterministic templated reply when
    `ANTHROPIC_API_KEY` is unset (so the UI is always functional).
- **Security**: new routes inherit the daemon's CORS hardening (PR #34).
  Cross-origin browser requests are rejected before reaching the handlers.
  Tests pin both the `attacker.com` origin reject and the cross-site POST
  reject specifically for the new routes.
- **Tests**: 16 new daemon-UI tests in `tests/test_living_knowledge_ui.py`
  spinning up the real daemon on a random port and exercising each route via
  urllib. Tests pin: HTML served, data endpoint returns the compression,
  express round-trip, reveal closes the loop, chat brainstorm/interview both
  phases (probe + crystallize), modality validation, and the CORS regression.
- **Total tests**: 687 pass, up from 672. No regressions.

**Still deferred** (consistent with TRUE-E3's E1/E2 designations):
- VR/embodied walk-through of the hierarchy
- Interactive parameter dashboards for mechanism simulation
- Multimodal rendering — content stays text; `tool_hint` names the renderer
  the user pipes it through (Tone.js, p5.js, Isaac Sim, etc.)

## [0.8.0] — Living-knowledge MVP: compression + expression + feedback loop

PR #35. The research vertical's Three-Layer Research OS (ingest →
synthesize → brief) gets two new layers that close the
compression → expression → refine loop from the TRUE-E3 framework:

- **Layer 4 — Compression.** `agent/research/compress.py` builds a
  3-level hierarchy from a synthesis run: Level 0 (3–5 core nodes),
  Level 1 (≤30 cluster nodes), Level 2 (all accepted cards). Frozen
  Pydantic, atomic disk writes under
  `~/.neuro_os_research/compressions/`. CLI: `neuro-os research
  compress [--from <synth-id>] [--list] [--show <id>] [--json]`.
- **Layer 5 — Expression + feedback.** `agent/research/expression.py`
  records that a compressed node was instantiated in one of 7
  modalities (visual / musical / physical / organizational / game /
  biological / narrative), then a separate `--reveal` step attaches
  the insight that the expression surfaced, optionally pointing at a
  node to refine. Content is text only (prompt / code / pseudocode /
  markdown); a `tool_hint` field names the renderer. neuro-os is the
  schema-keeper; rendering plugs in externally (Tone.js, p5.js,
  markdown, etc.). CLI: `neuro-os research express ...` (record /
  `--list` / `--show` / `--reveal`).

**Deliberately deferred** (heavy lifts with no near-term Phase-1
paper payoff): E1 embodied/VR (3d-force-graph-vr, Isaac Sim) and E2
interactive parameter dashboards (Streamlit wiring).

35 new tests; full suite 671 pass (1 deselected: a pre-existing
Anthropic-API-quota failure unrelated to this slice). `ruff` clean.
Engineering principles (Laws 1–9) all green; Law 5 satisfied — every
new export is a frozen Pydantic model.

End-to-end demo (run against `TRUE-E3-Living-Knowledge-Framework.md`
as the seed corpus): 4 MechanismCards → 4 clusters → 3-level
compression → narrative expression of the feedback-closure principle
→ reveal recorded against the source L0 node. The loop is closed on
disk; the next synthesis cycle can incorporate the reveal as a
refinement signal.

## [0.7.0] — Five compounding mechanisms + Paul-week unblockers

Eight PRs (#18 through #25) shipped in one delivery cycle. The
four-vertical substrate gains five compounding mechanisms layered on
top, plus Plan A native ingestion (no gbrain required), plus a
4-feature Paul-week bundle (auto-emission, share-note CLI, daily
anchors, `Priority.time_window`). **523 tests pass, 12 skipped**
(was 471 before this cycle).

### Added — five compounding mechanisms

- **Lane 1 — Corpus ingestion** (PRs #18, #23):
  - `agent/research/gbrain_adapter.py` (Plan B): reads `gbrain export`
    JSON via injectable `call_gbrain` callable, validates each entity
    through frozen `GbrainEntity`, translates to `MechanismCardProposal`
    with conservative skip policy.
  - `agent/research/ingest.py` (Plan A): walks `.txt` / `.md` / `.pdf`
    files via pure-Python `pypdf`. One Anthropic Haiku call per source
    OR regex heuristic fallback when no API key. Sha256 dedup against
    pending proposals. YAML front-matter parsing.
  - `agent/research/ingest_router.py`: `--prefer {auto,gbrain,local}`
    picks per invocation; auto-detects via `gbrain --version` probe.
  - `agent/research/proposals.py`: on-disk `MechanismCardProposal` queue
    with atomic writes + status-dir invariant.
  - CLI: `research ingest [--from-gbrain | --prefer local]`,
    `research review --cli`.
- **Lane 2 — Skillify (catalog evolution)** (PRs #22, #24):
  - `agent/skillify/` package: `OverrideEvent` + `SkillProposal` frozen
    schemas; `extract_pattern` (bucket → threshold-gate → most-frequent
    user_action with recency tie-break); `run_extraction` skips
    already-proposed buckets.
  - `loop urge --override-of <mode> --override-vertical <v>` CLI flags
    write both the `UrgeEvent` AND a skillify `OverrideEvent` in one
    command (the auto-emission flag is load-bearing — without it, the
    override log stays empty).
  - CLI: `skillify {log-override, extract, proposals, review --cli}`.
  - **Law 7 honored**: `mutable_paths=[]` for all verticals stays `[]`.
    Acceptance moves a `SkillProposal` from `pending/` to `accepted/`;
    the catalog change is a separate human-authored commit.
- **Lane 3 — Cross-modal Belief OS** (PR #21):
  - `agent/cross_modal.py`: `CrossModalEval` frozen schema +
    `run_cross_modal_check` (K-scorer fan-out) + `make_default_scorers`
    (3-pair Haiku/Sonnet/Opus wiring) + `make_fixture_scorers` for
    deterministic tests.
  - `agent/investment/config.py::run_cross_modal_bias_check` persists
    `(BiasCheck, CrossModalEval)` pair under same id; low-confidence
    prefix on disagreement above `DISAGREEMENT_WARNING_THRESHOLD`
    (0.34 — any 1-of-3 minority trips it).
- **Lane 4 — Cross-vertical entity propagation** (PR #20):
  - `Entity` frozen schema in `agent/cross_vertical.py` with the same
    default-PRIVATE invariant as `VerticalNote`; new `EntityKind`
    literal (person / company / topic / mechanism / other).
  - `upsert_entity` (append-only timeline), `share_entity`
    (broadens visibility for ALL prior + future rows of the slug),
    `read_entity` (returns latest visible), `list_entities`.
  - `MechanismCardProposal` + `MechanismCard` carry
    `entity_mentions: List[str]`. The `research review --cli` accept
    prompt asks the user for entity slugs; each is upserted as a
    research-private entity.
  - Storage uses `row_kind: "entity"` discriminator to avoid clash
    with `Entity.kind`; kept on existing
    `~/.neuro_os/cross_vertical.jsonl` store.
  - CLI: `research entity-list`, `research entity-read --slug <s>`.
- **Lane 5 — Daily dashboard** (PR #19):
  - `agent/research/dashboard.py`: pure-aggregation rollup over
    `registry.jsonl` + `ingestion_runs.jsonl` + `proposals/*` +
    `mechanism_cards/*`. Frozen `DashboardSummary`.
  - Outputs: compound-curve trend (today / 7-day-avg / window-avg /
    trend), drift-mode histogram, **`drift_modes_never_fired`**
    (catalog candidates), CE stick-rate, ingestion totals, action
    queue.
  - CLI: `research dashboard [--window N] [--json]`. Text rendering
    has ASCII histogram bars; JSON output round-trips through
    `DashboardSummary.model_validate_json`.

### Added — Paul-week feature bundle (PR #24)

- `cross-vertical {share-note, query}` CLI subtree — thin surface
  around the existing `share_note()` and `query()` functions.
- `loop anchor --kind {faith, relational}` CLI + `agent/founder_loop/anchors.py`
  module: typed daily log with `count_anchors_per_day()` for "5/7
  days hit" rendering.
- `Priority.time_window: Optional[str]` field with regex-validated
  `HH:MM-HH:MM` pattern. Annotation only (no tick behavior change);
  back-compat default `None`.

### Added — docs

- `docs/plans/{research-graphrag-sensor, gbrain-as-upstream-sensor,
  40-day-trial-dashboard}.md` (design docs for the lanes; kept for
  archeological value).
- `docs/paul-week-may-11.md` — runbook with the exact CLI commands
  per daily block of Paul's first real-user week (May 11–17, 2026).

### Changed

- `pyproject.toml`: added `pypdf>=4.0` runtime dep (pure-Python, MIT,
  ~600 KB; no compiled deps).
- `agent/cli.py`: `research ingest` extended with `--prefer`,
  `--source-dir`, `--no-llm`; `loop urge` extended with `--override-of`,
  `--override-vertical`; new top-level `cross-vertical` and `skillify`
  subtrees; new `loop anchor` subcommand.
- `docs/roadmap.md`: refactored to v0.7 SHIPPED list; deferred
  follow-ups (parallel scorers / text-norm clustering / gbrain MCP
  live wiring / anchors-in-NightlySummary) filed under LATER with
  explicit "why deferred" reasons.

### Boundary contract honored across all eight PRs

- **Law 1**: every new schema (Entity, OverrideEvent, SkillProposal,
  CrossModalEval, ScorerVerdict, Anchor, GbrainEntity, RawSource,
  MechanismCardProposal, IngestionRun, DashboardSummary) is frozen
  Pydantic with bounded fields; validation at every boundary.
- **Law 5**: every public function returns frozen models or lists of
  them; no dicts cross the public API.
- **Law 7**: no auto-mutation of any catalog. All five new write
  paths (`research ingest`, `skillify extract`, `upsert_entity`,
  `loop urge --override-of`, `loop anchor`) require explicit user
  CLI input. Skillify acceptance does NOT mutate the catalog.
- **Cross-vertical privacy**: `mutable_paths=[]` invariant unchanged.
  All new cross-vertical reads (`read_entity`, `list_entities`,
  `cross-vertical query`) honor visibility allowlists.

## [0.4.0] — Belief OS as a primitive

Reframes Belief OS from a standalone Streamlit demo into a **capability
that other products in the wjlgatech ecosystem consume**. The Streamlit
tab is preserved as a reference implementation and QA harness; the
load-bearing surface is now the typed Python API in
``agent/belief_os.py``.

### Added
- **Public consumption API** (``agent/belief_os.py``): a ``BeliefOS``
  class plus stateless ``classify_belief()`` / ``check_decision_text()``
  module-level functions. Typed Pydantic results
  (``ClassificationResult``, ``DecisionCheckResult``, ``IngestResult``,
  ``BeliefRecord``). Exported constants ``KNOWN_PRIMITIVES``,
  ``FAILURE_MODE_PRIMITIVES``, ``SOUND_REASONING_PRIMITIVES`` so
  consumers can build dropdowns / dashboards / approval gates without
  reading internals.
- **``BeliefOS.check_decision()``** — the Founder-OS pattern. Returns
  ``flag_for_review=True`` iff the classified primitive is in the
  failure-mode set (default: ``survivorship_bias`` and
  ``falsifiability``). Per-instance override via constructor.
- **``BeliefOS.ingest()``** — the persistent-belief-graph pattern.
  Wraps the L1 closed loop and returns ``IngestResult`` with
  ``merge_status``, ``contradicts_prior``, and the persisted
  ``ontology_path`` so consumers (money-os, research-os) can build
  per-user belief graphs that survive across sessions.
- **``BeliefOS.query()``** — read the user's current beliefs. Returns
  typed ``BeliefRecord`` lists, optionally filtered by primitive.
- **Multi-consumer example** (``examples/07_belief_os_consumer.py``):
  shows the call shape for company-os Founder OS, money-os, and a
  hypothetical research-os, plus the stateless one-off pattern. None
  of the consumers know about ontologies, golden cases, or priority
  rules.
- **20 new tests** (``tests/test_belief_os_api.py``) pinning the
  return-shape contracts that downstream products depend on. Includes
  no-leakage-between-instances coverage so two consumers with
  different failure-mode sets can coexist in one process.

### Changed
- Streamlit Belief OS tab now framed as a **reference implementation**,
  not the product. Tab caption, About section, and Belief-OS panel
  copy updated to point consumers at ``from agent.belief_os import …``.

## [0.3.0] — v1.2 LLM upgrade

### Added
- **LLM-backed extractor** (``agent/llm_extractors.py``): pluggable
  Anthropic Haiku 4.5 classifier with structured Pydantic output, a
  4096+ token system prompt with explicit acceptance criteria + 20
  worked few-shot examples, and ``cache_control: ephemeral`` so
  repeat classifications cost ~10% of the first call.
- **LLM toggle on `personal_epistemic_v1`** (``enable_llm()`` /
  ``disable_llm()`` / ``set_llm_fn()``). When enabled, the extractor
  tries the LLM first and falls back to keyword routing only on
  ``unknown`` or error. Default OFF — every existing test stays
  deterministic and offline.
- **9 LLM tests** (``tests/test_personal_epistemic_llm.py``) — all
  mocked, no live API calls. Covers the fallback chain, error
  handling, system-prompt contract (all seven labels enumerated,
  worked examples present, clears the 4096-token caching threshold),
  and ``messages.parse()`` wiring with cache_control.
- **UI toggle**: "Use Claude Haiku LLM" in the Belief OS tab. Disabled
  when ``ANTHROPIC_API_KEY`` is unset; surfaces confidence + reasoning
  + cache hit/write counts when active.
- **`pyproject.toml` `[llm]` extra** for the optional `anthropic` dep.

### Changed
- ``run_pipeline`` now propagates ``extract_mechanism``'s evidence
  dict into ``knowledge['extraction_evidence']`` so callers can audit
  which path (offline-keyword / llm-anthropic / llm-error) produced
  the mechanism.

## [0.2.0] — 2026-05-02

### Added
- **Closed-loop self-modification** (`agent/self_modification.py`):
  observe → propose → sandbox-apply → validate → promote-or-revert.
  Logs every mutation with patch + rollback patch + validator summary
  to `versions/version_registry.jsonl`.
- **Pluggable Domain abstraction** (`agent/domains.py`): `Domain`
  bundles ontology, golden cases, extractor, validators, and
  `mutable_paths` allowlist. Two domains shipped: `neuroscience_v1`
  (read-only) and `neuro_os_self_v1` (mutable: `priority_rules.json`).
- **Structured patch operations** (`agent/patches.py`): `Patch`
  dataclass + `ALLOWED_OPS` registry. Two ops:
  `append_priority_rule`, `remove_priority_rule`. Every op returns its
  inverse for one-step rollback. Path allowlist is enforced per-call.
- **Mutable priority rules** (`agent/data/priority_rules.json`): cue
  routing extracted from Python source so the meta-loop can mutate it
  without rewriting code.
- **Ontology auto-merge with learn-back**: accepted refinements mutate
  the ontology in place; subsequent extractions see the updated state.
  Updated ontology is persisted to disk when `ontology_path` is given.
- **Golden-case gate**: every accepted refinement is validated against
  golden classification accuracy before merge; regressions roll back.
- **Real evidence-strength heuristic** (`classify_evidence_strength`):
  detects year, author (`Foo et al.`), DOI, URL, and arXiv ids.
  Replaces the prior length-based label.
- **End-user API** (`agent/api.py`): `process_text` (single doc, no
  side effects) and `ingest_documents` (batch through full loop).
- **CLI** (`agent/cli.py`, `python -m agent`): `extract`, `ingest`,
  `evolve`, `build-ontology`, `self-modify` subcommands.
- **Examples** (`examples/`): four runnable scripts demonstrating
  extraction, learn-back, self-repair, and custom domain registration.
- **`pyproject.toml`** with `neuro-os` console script entry point.
- **39 tests** (was 12; previously broken). Coverage includes the
  full self-modification loop, allowlist enforcement, golden-gate
  rollback on regression, evidence heuristic edge cases, CLI
  subcommands, and the end-to-end learn-back flow.

### Changed
- **`run_pipeline`** now exists. Returns `{knowledge,
  true_validation, decision}` with TRUE-fielded knowledge synthesis.
  Fixes the prior `ImportError: cannot import name 'run_pipeline'`
  that broke `self_evolving_loop` on import.
- **`evaluate_update_dict`** enforces `REQUIRED_FIELDS` and raises
  `ValueError` on missing fields. REJECT is now reachable: `tests_pass=False`
  or `rollback_available=False` short-circuits to REJECT regardless
  of TRUE scores. Per-dimension scoring now depends on actual content
  (no hardcoded constants).
- **`check_extraction_consistency`** inspects `main_claim`,
  `core_mechanism`, `evidence_quotes`, and `evidence.text` rather than
  only `evidence.text`. Uses `primitive_consistency_checker` for
  negation detection against the ontology definition.
- **`primitive_feedback`** persists to `memory/primitive_feedback.jsonl`
  with lazy load on first use.
- **`version_registry`** persists to `versions/version_registry.jsonl`
  with auto-write on every `append_version` and a configurable path
  (`set_registry_path`) for tests.
- **`sandbox_runner.run_validation`** now runs validators in a fresh
  Python subprocess (real package machinery) instead of returning a
  hardcoded `True`. Default validator imports every loop-relevant
  module in `agent/`.

### Fixed
- `_first_sentence` honours common scientific abbreviations
  (`et al.`, `e.g.`, etc.) so a citation prefix is no longer mistaken
  for a sentence boundary.
- Eliminated the over-aggressive `relations` REFINE gate that fired
  on any extraction not mentioning every related primitive in one
  sentence. Replaced with an opt-in `required_relations` field; the
  `relations` field is now informational only.
- `_build_knowledge` now sets `main_claim` / `core_mechanism` from
  the document's first sentence instead of the canonical ontology
  definition (which made consistency checks self-comparing).

## [0.1.0] — initial skeleton
- Initial prototype skeleton modules (ingestion, ontology, evaluator,
  feedback, sandbox, registry).
