# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic
Versioning](https://semver.org/spec/v2.0.0.html).

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
