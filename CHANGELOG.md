# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic
Versioning](https://semver.org/spec/v2.0.0.html).

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
