# Plan — Research-vertical GraphRAG-style ingestion sensor + Yang walkthrough

## Context

A user proposal asked to build a 10-layer knowledge base (L0–L9) for an investor's content (Nicholas Yang) using GraphRAG + TypeDB + RDFLib + OpenCog AtomSpace. Eval found the layer model collapses to ~4 layers in practice, and that **80% of L2–L9 already exists** as shipped neuro-os primitives:

| Proposed layer | Already shipped |
|---|---|
| L2 atomic claim | `MechanismCard.{paper_title, paper_source, prediction, failure_mode}` |
| L3 concept primitives | 6 named drift modes per vertical + `MechanismCard.invariant` |
| L4 pattern / anti-pattern | The 6 drift modes per vertical (anti-pattern catalog × 4) |
| L5 mechanism | `MechanismCard.mechanism` (literal field name) |
| L6 first-principle | `MechanismCard.invariant` + 40-day continuity via `thesis_id` |
| L7 operational | `ConstructiveExpressionBase.{action, duration_min, tank_credit_pct}` |
| L8 embodied | The daily ritual (morning contract → drift cards → nightly) |
| L9 evaluation | `NightlySummaryBase` 4-metric rollup + `golden_cases.py` + Belief OS |

What's **actually missing** is L0–L1: the research vertical has no automated corpus ingestion. Users type `MechanismCard`s by hand. So the highest-leverage move is not a parallel KB — it's **one new sensor** that proposes `MechanismCard` candidates from a corpus, gated by a human-approval surface (Law 7).

The investor use case (Nicholas Yang) becomes the inaugural test case for **research → investment cross-vertical hand-off** — already 80% built (PR #11 cross-vertical privacy is exactly this).

## Goal

> *Drop a directory of transcripts/blogs/notes into the system → researcher reviews proposed mechanism cards → accepts a subset → researcher explicitly shares some with investment → investor files position theses citing them → Belief OS bias-checks → 40-day continuity score tracks survival.*

Five days of work. One new sensor, one new chat surface, one walkthrough. Reuses every primitive that's already shipped.

---

## Architecture — file tree

```
agent/research/
├── ingest.py                  # NEW: source ingestion sensor (text in, MechanismCardProposal out)
├── proposals.py               # NEW: queue read/write under ~/.neuro_os_research/proposals/
├── ontology.py                # MODIFY: add MechanismCardProposal (frozen Pydantic)
└── (everything else unchanged)

agent/founder_loop/
└── conversation.py            # MODIFY: add kind="research_review" with system prompt + tools

agent/cli.py                   # MODIFY: add `research ingest` and `research review` subcommands

examples/
└── 10_research_to_invest_yang.py    # NEW: 10-fixture walkthrough

tests/
├── test_research_ingest.py    # NEW: sensor + proposal queue tests
├── test_research_review.py    # NEW: chat surface + accept/reject pipeline
└── e2e/
    └── test_research_yang_e2e.py    # NEW: end-to-end CLI walkthrough

tests/fixtures/research/yang/
├── transcript_01_pricing_power.txt
├── transcript_02_compounding.txt
├── ... (10 synthetic Yang-style transcripts)
└── README.md                  # explains they're synthetic, not real Yang content
```

Five new code files (~800 lines), three modified (~80 lines added each), one walkthrough, one test fixture set.

## Schemas — frozen Pydantic

Pinned by `tests/test_research_ingest.py`:

### `RawSource` (new)

The L0–L1 input. Plain text + provenance. No graph; no entities yet.

```python
class RawSource(BaseModel):
    """A single input file the user wants to extract from. v0 is text-only;
    PDFs / videos must be pre-converted to .txt or .md by the user."""
    model_config = ConfigDict(frozen=True)

    source_id: str                      # short slug, e.g. "yang_2024_pricing_power"
    path: Path                          # absolute path to .txt / .md / .vtt / .srt
    title: str
    author: str
    publish_date: Optional[date] = None
    source_url: Optional[str] = None
    topic_tags: List[str] = []
    word_count: int                     # computed at load time
    sha256: str                         # detect re-ingestion of an unchanged source
```

### `MechanismCardProposal` (new)

A `MechanismCard`-shaped object that hasn't been accepted yet. Same fields as `MechanismCard` plus provenance + extraction metadata. Lives in `proposals/<status>/<proposal_id>.json` until accepted/rejected.

```python
class MechanismCardProposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    proposal_id: str                    # ulid-style; stable across sessions
    proposed_at: datetime
    status: Literal["pending", "accepted", "rejected", "edited"] = "pending"

    # The candidate card (same fields as MechanismCard, all optional until reviewed):
    paper_title: str                    # from RawSource.title
    paper_source: str                   # from RawSource.source_url or path
    mechanism: str                      # ≤ 500 chars
    invariant: str                      # ≤ 200 chars
    prediction: str                     # ≤ 200 chars
    failure_mode: str                   # ≤ 200 chars
    thesis_id: Optional[str] = None     # the user binds this at /research-review time

    # Provenance (Law 1 — every claim traces back to an excerpt):
    source_id: str
    source_excerpt: str                 # ≤ 500 chars; the exact text the LLM extracted from
    line_range: Optional[Tuple[int, int]] = None

    # Extraction metadata:
    extraction_method: Literal["llm-anthropic", "llm-anthropic-graphrag", "fallback-heuristic"]
    extraction_model: Optional[str] = None       # e.g. "claude-haiku-4-5-20251001"
    confidence: Literal["low", "medium", "high"]
    reasoning: str                      # one paragraph; why the LLM thinks this is a mechanism
```

### `IngestionRun` (new)

A summary of one `research ingest --source-dir <dir>` invocation. Logged to `~/.neuro_os_research/ingestion_runs.jsonl` for audit.

```python
class IngestionRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    started_at: datetime
    finished_at: datetime
    sources_scanned: int
    sources_skipped_unchanged: int      # sha256 match on a previously-ingested source
    proposals_emitted: int
    extraction_method: Literal["llm-anthropic", "llm-anthropic-graphrag", "fallback-heuristic"]
    cost_usd_estimate: float            # rough Anthropic spend for this run
```

## The sensor — `agent/research/ingest.py`

A pure-function pipeline. Three stages, each replaceable.

### Stage 1 — load + validate

```python
def load_sources(source_dir: Path) -> List[RawSource]:
    """Walk source_dir for .txt / .md / .vtt / .srt files. Build a
    RawSource for each. Skip unchanged sources (sha256 match) against
    the current proposals queue."""
```

Front-matter (YAML) is honored when present:
```yaml
---
title: "Why pricing power compounds"
author: "Nicholas Yang"
publish_date: 2024-08-12
source_url: "https://youtu.be/xxx"
topic_tags: [pricing-power, compounding]
---
(transcript body)
```

Without front-matter, the filename is parsed as `<author>__<slug>.<ext>` for a sensible default; the user can edit `RawSource.title` later.

### Stage 2 — extract (LLM, structured output)

```python
def extract_mechanisms(
    source: RawSource,
    *,
    llm_fn: Optional[Callable] = None,
    method: Literal["llm-anthropic", "llm-anthropic-graphrag", "fallback-heuristic"] = "llm-anthropic",
) -> List[MechanismCardProposal]:
    """One source → 0..K MechanismCardProposal candidates."""
```

Mirrors `agent/llm_extractors.py::make_anthropic_extractor`:
* `client.messages.parse()` with a Pydantic schema for structured output.
* System prompt is static + cacheable (`cache_control: ephemeral`); the source text is dynamic.
* Falls back to a small heuristic when no API key is set: regex for sentence patterns like *"the mechanism is …"* / *"this works because …"* / *"the failure mode is …"* — produces low-confidence proposals so the user knows the heuristic ran.

System prompt skeleton (cached):

> *You are extracting MechanismCard proposals from a single source document. A MechanismCard is a structured claim with FOUR required fields:*
>
> *• `mechanism` — the causal story (≤ 500 chars). What generates the observed behavior?*
> *• `invariant` — the load-bearing relationship that doesn't change with surface conditions (≤ 200 chars).*
> *• `prediction` — a falsifiable forecast that follows from the mechanism (≤ 200 chars).*
> *• `failure_mode` — the specific condition under which the mechanism breaks (≤ 200 chars).*
>
> *Rules:*
> *• Extract 0–5 candidates per source. Quality over count.*
> *• Every candidate MUST cite a `source_excerpt` of ≤ 500 chars from the input.*
> *• If a passage is descriptive ("Nicholas thinks X") but doesn't name a mechanism, SKIP it. Description is not a mechanism.*
> *• If a passage names a mechanism but no falsifiable prediction follows, mark `confidence: low`.*

This honors **Law 2 (mechanism over description)** — currently aspirational; this prompt is the prompt-time enforcer.

### Stage 3 — write to queue

```python
def write_proposals(proposals: List[MechanismCardProposal], home: Path) -> None:
    """Atomic write to ~/.neuro_os_research/proposals/pending/<proposal_id>.json.
    Status moves the file between subdirectories: pending/ → accepted/ or rejected/."""
```

The on-disk layout:
```
~/.neuro_os_research/
├── mechanism_cards/                 # existing — accepted cards live here
├── proposals/
│   ├── pending/
│   │   └── 01HQ...zzz.json          # one MechanismCardProposal per file
│   ├── accepted/
│   └── rejected/
└── ingestion_runs.jsonl             # one row per ingest invocation
```

Acceptance moves the file from `pending/` to `accepted/` AND writes the corresponding `MechanismCard` to `mechanism_cards/`. Rejection moves to `rejected/` only — no card created. Edit-then-accept records the diff in the proposal's `extraction_method` history (append-only field) so the audit trail survives.

**Why GraphRAG isn't a hard dependency.** The `method="llm-anthropic-graphrag"` branch is a future variant: cluster sources by entity overlap, summarize each community, then extract mechanisms from the community summary instead of from each source independently. v0 ships only `method="llm-anthropic"` (per-source extraction); the GraphRAG variant is a one-day follow-up that the same `MechanismCardProposal` schema absorbs without a refactor.

## The chat surface — `/research-review`

Mirrors the `/queues` and `/catalog-review`-like pattern (`kind="research_review"` in `agent/founder_loop/conversation.py`). The daemon serves it at `http://127.0.0.1:8765/research-review`.

System prompt (cached):

> *You are helping the user review MechanismCardProposal queue items. For each pending proposal, present it cleanly with provenance, ask whether the user wants to ACCEPT, EDIT, or REJECT. If accepted, ask which `thesis_id` to bind it to (default: the user's currently active research thesis). If edited, accept the user's edits then write. If rejected, optionally ask one short reason (≤ 100 chars) for the audit log.*
>
> *Rules:*
> *• Show no more than 3 proposals per turn (avoid overwhelming).*
> *• Always show the source_excerpt verbatim so the user can verify the LLM didn't hallucinate.*
> *• Never auto-accept. Every mutation requires the user to type "accept" or click the button.*
> *• Acceptance writes to `~/.neuro_os_research/mechanism_cards/<id>.json` via the existing `write_mechanism_card(...)` function (Law 7 — human-in-loop truth control).*

Tools the LLM can call:
* `accept_proposal(proposal_id, thesis_id, edits: Optional[dict])`
* `reject_proposal(proposal_id, reason: Optional[str])`
* `list_pending(limit: int = 3)` — for pagination

CLI fallback (no chat / no API key):

```bash
neuro-os research review                # interactive REPL: shows next pending proposal,
                                        # prompts: [a]ccept / [e]dit / [r]eject / [s]kip
neuro-os research review --auto-reject-low-confidence  # bulk-reject confidence=low
```

## The walkthrough — `examples/10_research_to_invest_yang.py`

A scripted, deterministic-mockable end-to-end. Loads 10 fixture transcripts under `tests/fixtures/research/yang/`, runs every stage, prints the result. Mirrors `examples/09_cross_vertical_demo.py` in shape and exit-cleanliness.

### Story arc

1. **Ingest.** Load 10 synthetic Yang-style transcripts (pricing power, compounding, moats, regulatory risk, capital allocation, etc.). Run `ingest()` → 6 `MechanismCardProposal` candidates emitted to `proposals/pending/`.
2. **Review.** Simulate the user reviewing in `/research-review`: accept 4, reject 1 (off-topic), edit 1 (tighten the failure_mode wording). 4 `MechanismCard` rows written to `mechanism_cards/`.
3. **Cross-vertical share.** Researcher decides 2 of the 4 mechanism cards are relevant to a position thesis they're forming on NVDA. Calls `cross_vertical.write_note(source_vertical="research", payload=card.model_dump(), share_with=["investment"])`. The other 2 stay private.
4. **Investment files PositionThesis.** Investor reads the shared notes via `cross_vertical.query(reader="investment", kinds=["mechanism_card"])`, files a `PositionThesis` for NVDA citing the two card IDs in `evidence`. Default-PRIVATE.
5. **Belief OS bias check.** `run_bias_check(thesis=...)` returns a typed `BiasCheck` — flags any biases in the thesis text.
6. **Privacy assertion.** Researcher and startup CANNOT read the position thesis. (Mirrors `tests/test_cross_vertical_e2e.py`.)
7. **Nightly.** Run `research nightly` and `invest nightly`. Both summaries print: research shows `mechanism_cards/day=4`, investment shows `position_edits=1` and `advisory_only=True`.

### What the walkthrough proves

* **The whole 4-vertical strange loop closes on one corpus.** A real test of the substrate, not 4 disconnected demos.
* **Cross-vertical privacy holds end-to-end.** The two unshared cards are invisible to investment.
* **The Construction Law (every claim traces back to a source excerpt) is honored.** Each MechanismCard has a `source_excerpt` field threaded from the proposal.
* **Belief OS integration is not just a stub.** A real bias check fires on a thesis backed by real (synthetic) mechanism cards.

## Privacy / Law 7 / safety

Five gates, each one already pinned by an existing test or pattern:

1. **Law 1 (no raw ingestion):** `RawSource` and `MechanismCardProposal` are frozen Pydantic. No `json.loads(...)` reaches user-visible state without going through one of these.
2. **Law 5 (deterministic outputs):** every public function returns a Pydantic model, not a dict.
3. **Law 7 (human-in-loop):** the sensor writes ONLY to `proposals/pending/`. The mechanism cards directory is only mutated by `accept_proposal()`, which is gated on user input. No auto-accept path exists.
4. **Cross-vertical privacy:** mechanism cards default-PRIVATE to research. Sharing requires explicit `share_with=[...]`. The privacy regression test in `tests/test_cross_vertical_e2e.py` covers this.
5. **Bounded action (Law 5 of `tests/test_founder_loop_safety.py`):** writes are limited to `~/.neuro_os_research/{proposals,mechanism_cards,ingestion_runs.jsonl}`. Anything else raises.

## Implementation order — 5 days

| Day | Deliverable | Test gate |
|---|---|---|
| 1 | `RawSource` + `MechanismCardProposal` + `IngestionRun` schemas in `agent/research/ontology.py`. `agent/research/proposals.py` queue read/write. `tests/test_research_ingest.py` schema tests. | All schemas frozen; Pydantic round-trip; queue write→read returns identical objects. |
| 2 | `agent/research/ingest.py` with `load_sources` + `extract_mechanisms` (LLM + heuristic fallback). CLI: `neuro-os research ingest --source-dir <dir>`. 10 synthetic Yang fixtures. | Mocked-LLM test: ingest 3 fixtures → 3+ proposals in `proposals/pending/`. Heuristic-fallback test: ingest with no API key → low-confidence proposals emitted. |
| 3 | `/research-review` chat surface in `conversation.py`. CLI: `neuro-os research review` interactive REPL. Accept pipeline calls `write_mechanism_card(...)`. | E2E test: accept proposal via REPL → `mechanism_cards/<id>.json` exists, proposal moved to `accepted/`. Reject test: rejection moves to `rejected/`, no card created. |
| 4 | `examples/10_research_to_invest_yang.py` walkthrough. Cross-vertical share + bias check + nightly. `tests/e2e/test_research_yang_e2e.py` (S27) drives the walkthrough as a subprocess. | Walkthrough exits 0; produces the expected 4 cards / 2 shared / 1 thesis / 1 bias check / 2 nightlies. Privacy assertion fires (research+startup can't see the position thesis). |
| 5 | Doc updates: `docs/how-to-use-it.md` adds research-vertical ingestion section; `docs/how-it-works.md` adds the sensor to Box 1. Roadmap entry → SHIPPED. Mirror to `agent/founder_loop/static/`. | `pytest tests/ -q` green. `ruff check` clean. Pre-commit law-gate green. |

### Gate priority

| Gate | Day | If this fails |
|---|---|---|
| **Schema gate** | 1 | Stop. Every later step assumes these schemas. |
| **Extraction gate** | 2 | Stop. If the LLM can't reliably produce 4-field MechanismCardProposals, the rest of the pipeline is empty machinery. |
| **Approval gate** | 3 | Stop. If acceptance writes outside the allowlisted paths or auto-accepts, Law 7 is broken. |
| **Cross-vertical gate** | 4 | Continue, but with a clear error message — the existing privacy test in PR #11 is the actual CI defender; the walkthrough is the user-facing demo of that test. |

## What this does NOT do (explicit cuts)

* **No graph database.** No Neo4j, no TypeDB, no RDFLib, no GraphRAG-the-package as a hard dependency. The `method="llm-anthropic-graphrag"` branch is reserved for v1 if community-summary-driven extraction beats per-source extraction (we'll know after 50+ real sources). `MechanismCardProposal` is the schema lock; the extractor underneath is swappable.
* **No PDF / video / audio ingestion.** v0 reads only text (`.txt`, `.md`, `.vtt`, `.srt`). PDF→text and video→transcript are pre-processing steps the user runs separately. Adding them to the sensor would add three external deps and one error surface for each.
* **No automatic cross-vertical sharing.** The researcher must explicitly call `share_with=["investment"]` per card. Default-private remains the invariant.
* **No catalog mutation.** `mutable_paths` for the research vertical stays `[]` after this work. Mechanism cards are content; they don't reshape the substrate.
* **No multi-thesis ingestion.** Each ingestion run binds proposals to (at most) one active research thesis. Multi-thesis is a v1 problem.
* **Not a replacement for `/queues` for founder_loop.** This is the research-vertical equivalent. Founder_loop's queues stay where they are.

## Test gates summary

| Test | Gates |
|---|---|
| `tests/test_research_ingest.py` (~10 tests) | Law 1, Law 5; queue read/write; sha256 dedup; heuristic fallback emits low-confidence |
| `tests/test_research_review.py` (~6 tests) | Law 7; accept→write_mechanism_card; reject→no card; edit-then-accept; bounded path enforcement |
| `tests/e2e/test_research_yang_e2e.py` (S27) | Walkthrough end-to-end; privacy assertion; nightly numbers correct |
| Existing `tests/test_engineering_principles.py` | Law 1 walks the new code paths and confirms Pydantic at every boundary |
| Existing `tests/test_cross_vertical_e2e.py` | Defends the privacy boundary the walkthrough exercises |

## Two new scenarios for the e2e catalog

| ID | Scenario | Harness |
|---|---|---|
| **S27** | Yang-corpus walkthrough — researcher ingests 10 transcripts, accepts 4 proposals, shares 2 with invest, invest files thesis citing them, Belief OS check fires | CLI subprocess (mirrors S21–S26) |
| **S28** | Privacy regression on the Yang flow — research and startup cannot read the position thesis even after researcher shared 2 mechanism cards | CLI subprocess; reuses `cross_vertical.query` |

## Closing the loop — what success looks like

The day this graduates to SHIPPED is the day this sequence runs end-to-end on a real corpus (not synthetic):

1. User drops 50 transcripts/blogs into `~/.neuro_os_research/sources/`.
2. `neuro-os research ingest --source-dir sources/` returns ~30 proposals (some sources contain multiple mechanisms; some contain none).
3. User reviews in `/research-review` over ~30 minutes. Accepts ~12, rejects ~15, edits ~3.
4. Researcher shares 4 cards with investment.
5. Investor files 2 position theses citing the shared cards. Both default-PRIVATE.
6. 40 days later, the research vertical's nightly shows continuity score 1.0 (researcher stayed on the original thesis), and the investment vertical's nightly shows a calibration error that started at 0.5 and dropped to 0.32 (forecasts started matching outcomes).
7. The user has converted a corpus of someone else's thinking into their own typed, falsifiable, testable mechanism library — and the cross-vertical loop closed on it.

The deeper claim from the eval — *every idea traces back to a source, forward to a principle, tested through an action* — is now demonstrated end-to-end on real data, not asserted in a doc.

---

## Followup if this works

* **GraphRAG variant** (`method="llm-anthropic-graphrag"`): cluster sources by entity overlap, summarize each community, extract mechanisms from the community summary. 1 day. Same `MechanismCardProposal` schema; new extractor.
* **PDF ingestion**: `pypdf2` + a normalize step. 0.5 day.
* **Apply the same sensor to the investment vertical** (extracts `PositionThesis` candidates from a corpus of 10-Ks / earnings calls). 1 day; same schema shape, different system prompt.
* **Apply to startup** (extracts `AudienceSignal` candidates from a corpus of customer-interview transcripts). 1 day.

Each is additive and reuses the schema/queue/review-surface architecture this plan establishes.
