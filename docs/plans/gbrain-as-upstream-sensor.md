---
status: parked
parent: infra
reason: "Plan B alternative to research-graphrag-sensor (Plan A). Both parked while Phase-1 paper is the active focus. Un-parks when Paul picks one of the two."
---

# Plan — gbrain as upstream sensor (Plan B for NEXT #2)

> **Status:** design doc only. No code shipped. Pairs with [`research-graphrag-sensor.md`](research-graphrag-sensor.md) (Plan A — build the ingestion sensor natively in Python).
>
> **One-line summary:** instead of building L0–L1 corpus ingestion ourselves, treat [garrytan/gbrain](https://github.com/garrytan/gbrain) as a first-class upstream sensor. Neuro-os reads gbrain's already-extracted entities over MCP and translates them into `MechanismCardProposal` rows. Plan A becomes the fallback when gbrain isn't installed.

## Context — why a Plan B exists

[Plan A](research-graphrag-sensor.md) is 5 days of native work to build:
- a markdown/transcript loader with sha256 dedup,
- an LLM extractor that produces `MechanismCardProposal` candidates,
- a review chat surface and accept/reject pipeline.

While Plan A was being scoped, the user pointed at [gbrain](https://github.com/garrytan/gbrain) — Garry Tan's personal-knowledge OS (14k stars, MIT, v0.30.2, very active). gbrain already does **everything in Plan A's L0–L1 layer at production quality:**

| Plan A scope (build) | gbrain shipped |
|---|---|
| Markdown / transcript loader (sha256 dedup) | `gbrain import ~/notes/`, sources federation, `db_tracked` / `db_only` storage tiering |
| Vector + keyword retrieval (RRF) | hybrid search built-in; **P@5 = 49.1%, R@5 = 97.9%** on a 240-page corpus |
| LLM extraction with provenance | Claude Haiku for multi-query expansion + Claude Opus for synthesis; nightly "dream cycle" enrichment in 9 phases |
| Typed entity graph | zero-LLM auto-extraction of `attended` / `works_at` / `invested_in` / `founded` / `advises` |
| Background job durability | Minions (Postgres-native job queue, deterministic, $0 tokens) |
| MCP server for Claude Code / Cursor | `gbrain serve` (stdio) or `gbrain serve --http --port 3131` |
| Multi-source federated brain | `gbrain sources add --url https://...` with auto-managed clones |
| Voice / Twilio ingestion | shipped recipe — phone calls answer with full brain context |

Plan A would re-implement a thin imitation of the first three rows. Plan B treats gbrain as the upstream and keeps neuro-os focused on the **regulatory loop** (drift catalogs, calibration, contract, cross-vertical privacy) — which gbrain has zero of and isn't trying to build.

## The reframe — neuro-os = regulator, gbrain = sensor

```
┌─────────────────────────────────────────────────────────────────┐
│   gbrain (upstream — knowledge substrate, optional dependency)  │
│                                                                  │
│   markdown / transcripts / tweets / emails ──► entity graph     │
│   (sha256 dedup, vector + keyword retrieval, dream-cycle enrich)│
│                                                                  │
│   Exposes: 30+ MCP tools                                        │
│   Optimizes: retrieval P@k, R@k, MRR, nDCG@k                    │
└────────────────────────┬────────────────────────────────────────┘
                         │ MCP (stdio or HTTP, local only)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│   neuro-os adapter (NEW — agent/research/gbrain_adapter.py)     │
│                                                                  │
│   gbrain entities ──► MechanismCardProposal candidates          │
│   (translation only — no extraction; we trust gbrain's L0–L2)   │
└────────────────────────┬────────────────────────────────────────┘
                         │ writes to ~/.neuro_os_research/proposals/pending/
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│   neuro-os research vertical (UNCHANGED from Plan A)            │
│                                                                  │
│   /research-review chat surface (Law 7 — human accept/reject)   │
│   ► accepted MechanismCard ► cross_vertical share ► invest/etc. │
│   ► drift detection on the 6 named modes                        │
│   ► nightly calibration (40-day continuity, mechanism stick-rate│
│                                                                  │
│   Optimizes: decision-calibration quality, NOT retrieval volume │
└─────────────────────────────────────────────────────────────────┘
```

**Boundary contract:** gbrain owns L0 (raw input) + L1 (parsed corpus) + L2 (atomic claims, entity graph) + L8 (retrieval). neuro-os owns L3+ (catalogs of named drift modes), L7 (constructive expressions), L9 (calibration / 40-day continuity), and the cross-vertical privacy layer.

The two sides communicate through **one schema** (`MechanismCardProposal`) and **one transport** (gbrain MCP). Both are intentionally small; if gbrain ever stops, the adapter is replaceable in <1 day with another extraction engine.

## Goal

> *User installs gbrain (one command), drops a corpus into gbrain, runs `neuro-os research ingest --from-gbrain` → adapter pulls candidate entities → emits `MechanismCardProposal` rows → user reviews in `/research-review` → accepted cards flow into the existing 4-vertical loop end-to-end.*

Two days of work. One new adapter file (~250 lines). One new CLI flag (`--from-gbrain`). Plan A's review surface, queue, accept pipeline, and walkthrough remain unchanged and become the fallback when gbrain is absent.

## Architecture — file tree (delta against Plan A)

```
agent/research/
├── ontology.py                     # SAME as Plan A — adds MechanismCardProposal
├── proposals.py                    # SAME as Plan A — queue read/write
├── ingest.py                       # SAME as Plan A — local-extraction Plan A path
├── gbrain_adapter.py               # NEW (Plan B): gbrain MCP client → MechanismCardProposal
└── ingest_router.py                # NEW (Plan B): chooses adapter at runtime

agent/cli.py                        # MODIFY: add `research ingest --from-gbrain`

tests/
├── test_research_gbrain_adapter.py # NEW: contract tests against a recorded gbrain export
└── fixtures/research/gbrain_export.json    # NEW: deterministic gbrain MCP-response fixture

examples/
└── 10_research_to_invest_yang.py   # SAME as Plan A — works with EITHER adapter
```

The walkthrough, review surface, accept pipeline, schemas, and queue layout are **identical to Plan A**. Plan B replaces only the extraction step.

## The runtime decision — Plan A or Plan B per invocation

```
neuro-os research ingest --source-dir <dir>     # Plan A explicit (LLM extraction)
neuro-os research ingest --from-gbrain          # Plan B explicit (gbrain MCP)
neuro-os research ingest                        # Auto: prefer gbrain if `gbrain --version`
                                                #       succeeds; else fall back to Plan A
```

`agent/research/ingest_router.py` is a 30-line dispatcher. It probes for gbrain presence:

```python
def detect_extraction_method(prefer: Literal["auto", "gbrain", "local"]) -> str:
    """Return 'gbrain-mcp' if gbrain is installed and prefer in {auto, gbrain},
    else 'llm-anthropic'. Raise if prefer='gbrain' but gbrain not present."""
```

Detection: subprocess `gbrain --version` with a 1-second timeout. Cached per-invocation; never makes a network call. No gbrain-process startup happens on the path that doesn't need it.

## Schemas — frozen Pydantic (gbrain-specific delta)

Plan A's `RawSource`, `MechanismCardProposal`, `IngestionRun` are unchanged. Plan B adds two intentionally-thin types that pin the gbrain MCP boundary.

### `GbrainEntity` (new)

The shape we expect back from gbrain's MCP tools. Frozen Pydantic so any drift in gbrain's response shape becomes an explicit ValidationError instead of silent data corruption.

```python
class GbrainEntity(BaseModel):
    """A single entity the gbrain knowledge graph has extracted.
    Field names mirror gbrain's MCP response shape; if gbrain
    changes its API, this schema is the single break-point."""
    model_config = ConfigDict(frozen=True)

    slug: str                       # gbrain's stable ID
    title: str
    page_kind: Literal["claim", "person", "company", "topic", "note", "other"]
    body_excerpt: str               # ≤ 1000 chars; the body field gbrain returns
    typed_relationships: List[str]  # gbrain's auto-link types (works_at / attended / ...)
    backlinks: int
    confidence_hint: Optional[Literal["low", "medium", "high"]] = None
```

### `GbrainQuerySpec` (new)

The MCP query the adapter issues. Pinned to keep the call site auditable.

```python
class GbrainQuerySpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    # What to ask gbrain for. v0 reuses gbrain's hybrid search.
    query: str                      # natural-language question
    page_kinds: List[str] = ["claim"]
    limit: int = 25
    since: Optional[datetime] = None  # incremental ingestion (last_run_at)
    typed_relationships: List[str] = []  # filter, e.g. ["invested_in"]
```

## The adapter — `agent/research/gbrain_adapter.py`

Three small functions. Each is replaceable independently.

### Stage 1 — call gbrain MCP

```python
def fetch_entities(spec: GbrainQuerySpec) -> List[GbrainEntity]:
    """Open a stdio MCP client to `gbrain serve`, issue the query,
    parse responses through GbrainEntity (Pydantic validation).
    No retries; no network — gbrain runs locally only."""
```

Implementation note: use the official `mcp` Python client (already a transitive dep of the broader Anthropic SDK ecosystem). One process spawn per `research ingest` invocation; the gbrain MCP server is short-lived for our purposes. We DO NOT keep a long-running gbrain process from inside neuro-os — that's gbrain's own daemon's responsibility.

### Stage 2 — translate gbrain entity → proposal

```python
def translate(entity: GbrainEntity, *, source_query: str) -> Optional[MechanismCardProposal]:
    """One gbrain entity → at most one MechanismCardProposal.
    Returns None if the entity doesn't have enough structure to fill
    `mechanism` + `invariant` + `prediction` + `failure_mode`.
    Logs a one-line skip reason for the audit trail."""
```

The translation policy is **conservative**: we'd rather skip a borderline entity than emit a low-quality proposal. Reasons to skip:
- `page_kind != "claim"` (people/companies/topics aren't mechanisms)
- body excerpt < 100 chars (too thin to support 4 fields)
- no falsifiable prediction visible in the body excerpt → emit with `confidence: low` and let `/research-review` decide
- `typed_relationships` are all reference-style (`mentions`, `cites`) with no causal verbs

When we DO translate:
- `mechanism` ← gbrain `body_excerpt`, normalized to ≤ 500 chars
- `invariant` ← extracted from the gbrain entity's first typed_relationship of kind `causes` / `requires` / `entails`, fall back to title-cased subject of body_excerpt
- `prediction` ← we send a small Haiku call with the body_excerpt asking for the falsifiable prediction (Plan B is NOT zero-LLM; gbrain just does the heavy lifting upstream)
- `failure_mode` ← same Haiku call, second field
- `source_id` ← `f"gbrain:{entity.slug}"`
- `source_excerpt` ← `entity.body_excerpt`
- `extraction_method` ← `"gbrain-mcp"` (NEW literal added to `MechanismCardProposal.extraction_method`)
- `extraction_model` ← `"claude-haiku-4-5-20251001"` (the small completion call in this stage)
- `confidence` ← carried through from `GbrainEntity.confidence_hint` if present, else `"low"`

**Cost discipline:** Stage 2 uses ONLY Haiku for the per-entity completion (≤ $0.01/entity at current pricing). We never invoke gbrain's own Opus enrichment pipeline from this adapter — that's a user-facing gbrain command (`gbrain dream`), separately opt-in.

### Stage 3 — write to queue

Identical to Plan A. The proposal lands in `~/.neuro_os_research/proposals/pending/`, the existing review surface picks it up. Plan A's accept pipeline already moves it to `accepted/` and writes the `MechanismCard`.

## Fallback strategy — Plan A is the safety net

The whole point of writing Plan A first and Plan B as the optimization is that **Plan A always works** even when gbrain is absent. Concretely:

| Scenario | What happens |
|---|---|
| gbrain installed, `--from-gbrain` flag | Plan B path; ≤ $0.01/entity |
| gbrain installed, no flag (auto) | Plan B path; same cost |
| gbrain NOT installed, `--from-gbrain` | Hard error: "gbrain not detected. Install via `bun install -g github:garrytan/gbrain` or omit --from-gbrain to use the local extractor." |
| gbrain NOT installed, no flag (auto) | Plan A path; standard Anthropic extraction cost |
| gbrain installed but its daemon hung | Plan B fails fast (1s timeout on probe) → fall back to Plan A and warn |

This means the research vertical's existence does not depend on the user installing a TypeScript/Bun toolchain. gbrain is opt-in, not required. The `MechanismCardProposal` schema is the single contract; the extractor underneath is interchangeable.

## Privacy / Law 7 / safety

Five gates. The first three are inherited from Plan A; the last two are new because of the process boundary.

1. **Law 1 (no raw ingestion):** every gbrain MCP response goes through `GbrainEntity.model_validate(...)`. Malformed responses raise immediately, never reach disk.
2. **Law 5 (deterministic outputs):** `translate()` returns `Optional[MechanismCardProposal]` — a Pydantic model — never a dict.
3. **Law 7 (human-in-loop):** the adapter writes ONLY to `proposals/pending/`. Acceptance still requires `/research-review`. No auto-accept path exists.
4. **No outbound network from the adapter.** gbrain runs on `127.0.0.1` (its own daemon's invariant). The adapter speaks stdio MCP to a local process. We never carry gbrain content over the wire.
5. **Cross-vertical privacy holds.** A `MechanismCard` derived from gbrain is still default-PRIVATE to research. Cross-vertical sharing requires explicit `share_with=[...]`. The privacy regression test in `tests/test_cross_vertical_e2e.py` covers this case unchanged.

## Implementation order — 2 days

| Day | Deliverable | Test gate |
|---|---|---|
| 1 | `GbrainEntity`, `GbrainQuerySpec`, `extraction_method` literal updated. `gbrain_adapter.fetch_entities` + `translate()`. `tests/test_research_gbrain_adapter.py` against `tests/fixtures/research/gbrain_export.json`. | Schema gate (frozen, round-trip); translate-skip cases logged; gbrain-not-found path raises a typed error. |
| 2 | `ingest_router.detect_extraction_method`. CLI: `research ingest --from-gbrain`. Auto-detect path. Update `examples/10_research_to_invest_yang.py` to print which adapter was used. | Router gate (auto / explicit / hard-fail); `examples/10_*.py` runs end-to-end with both adapters in CI (gbrain mocked via fixture). |

Everything else — review surface, accept pipeline, walkthrough, cross-vertical share, nightly — is Plan A's deliverable and is unchanged.

### Gate priority

| Gate | Day | If this fails |
|---|---|---|
| **gbrain MCP contract** | 1 | Stop. If gbrain's response shape doesn't fit `GbrainEntity`, the adapter is empty. |
| **Translation quality** | 1 | Stop. If translate's accept-rate on the fixture is < 60%, gbrain isn't producing structure we can use; fall back to Plan A and revisit. |
| **Router determinism** | 2 | Stop. If `detect_extraction_method` is flaky across invocations, users will get inconsistent behavior. |

## What this does NOT do (explicit cuts)

- **No fork of gbrain.** We depend on the upstream as-is and pin a known-good version range in our docs (not in `pyproject.toml` — gbrain is a separate Bun runtime).
- **No re-implementation of gbrain features.** Vector retrieval, dream-cycle, voice, federated sources are all gbrain's job. We never call them from neuro-os; the user runs them via gbrain's own CLI.
- **No long-running gbrain daemon owned by neuro-os.** Each `research ingest` spawns a short-lived MCP client; gbrain's own daemon (if the user runs one) is independent.
- **No automatic cross-vertical sharing.** Same as Plan A — explicit `share_with=[...]` only.
- **No catalog mutation.** `mutable_paths` for the research vertical stays `[]`.
- **No multi-vertical adapter in this PR.** Founder/invest/startup adapters are LATER (see below).

## Test gates summary

| Test | Gates |
|---|---|
| `tests/test_research_gbrain_adapter.py` (~12 tests) | `GbrainEntity` round-trip; translate-skip reasons logged; translate-success produces frozen `MechanismCardProposal`; cost-discipline assertion (no Opus call paths) |
| `tests/test_research_ingest_router.py` (~6 tests) | Auto-detect when gbrain absent → returns `"llm-anthropic"`; auto-detect when gbrain present → returns `"gbrain-mcp"`; explicit `--from-gbrain` raises typed error if absent; 1-second timeout enforced |
| Existing `tests/test_engineering_principles.py` | Law 1 + Law 5 walk the new code paths |
| Existing `tests/test_cross_vertical_e2e.py` | Privacy holds end-to-end on gbrain-sourced cards |

## Risks (named honestly)

1. **Single-author upstream.** gbrain is one person's production brain. If Garry stops, we're stranded. **Mitigation:** the adapter contract is small (one schema, one transport); a swap-out to any other extraction engine is <1 day.
2. **Bun / TypeScript barrier.** Most neuro-os users won't have Bun installed. **Mitigation:** opt-in only; Plan A always works.
3. **gbrain MCP API drift.** gbrain is at v0.30.2 with no public LTS commitment. A breaking change in MCP tool names will break the adapter. **Mitigation:** the `GbrainEntity` schema makes drift loud (ValidationError in CI); pin a known-good gbrain version in docs and bump deliberately.
4. **Cost surface.** Even Plan B costs ~$0.01/entity in Haiku for prediction/failure_mode extraction. **Mitigation:** add a `--no-haiku` flag that emits proposals with `prediction = ""` and `failure_mode = ""` so the user fills them in `/research-review` manually — zero token cost.
5. **Identity confusion.** "Is neuro-os a memory system?" → no, it's a regulator that can read from a memory. **Mitigation:** add a one-paragraph clarification to `docs/what-is-this.md` when Plan B ships, citing the boundary diagram in this doc.
6. **Process boundary debugging.** Two daemons (gbrain + neuro-os) is more failure surface than one. **Mitigation:** `research ingest --from-gbrain --debug` prints the raw MCP request/response so the user can `grep` the issue. The adapter logs every skip reason and every ValidationError to `~/.neuro_os_research/ingestion_runs.jsonl` for audit.

## The 4-vertical extension (LATER, deferred)

If Plan B ships and the research adapter's translate-rate is healthy on real corpora, the same pattern extends to the other three verticals. Listed here so the design is on record; **none of these are in scope for this PR or the immediately following one** — we wait until research validates the boundary.

| Vertical | What gbrain provides | What the adapter emits | Drift modes detected |
|---|---|---|---|
| **Founder Loop** | Meeting transcripts (Circleback / Twilio voice ingestion) | enriched `UrgeLog` entries with extracted context | `frustration`, `decision_fatigue`, `social` |
| **Investment** | Twitter/X feed ingestion (gbrain's `gbrain sources add` for X) | `NarrativeFollowingSignal` rows | `narrative_following`, `social_proof_following`, `emotional` |
| **Startup** | Founder meeting transcripts | `BroadcastingSignal`, `FeatureCreepSignal` | `broadcasting`, `vision_intoxicated`, `feature_creep` |

Each is ~2 days at the same shape: one adapter file, one frozen-Pydantic schema, one CLI flag. Total deferred scope: ~6 days, validated lazily by whether the research adapter pays off.

## Closing the loop — what success looks like

The day this graduates to SHIPPED is the day this sequence runs:

1. User: `bun install -g github:garrytan/gbrain && gbrain init && gbrain import ~/yang_transcripts/`.
2. User: `neuro-os research ingest --from-gbrain` → adapter pulls 30 entities → emits 8 proposals (translate skipped 22 as non-claims or thin).
3. User reviews in `/research-review` over ~10 minutes. Accepts 5, rejects 2, edits 1.
4. Researcher shares 2 cards with investment via `cross_vertical.write_note(share_with=["investment"])`.
5. Investor files `PositionThesis` citing them. Belief OS bias-checks.
6. 40 days later, the research vertical's nightly shows continuity score 1.0 and the investment vertical's calibration error has dropped — same outcome as Plan A's success metric, but with gbrain doing the corpus heavy lifting.

The user has a single `gbrain` corpus that compounds (gbrain's strength) AND a calibrated 4-vertical loop on top of it (neuro-os's strength). Neither tool tries to do both jobs.

## Comparison — Plan A vs Plan B (cheat sheet)

| Dimension | Plan A (native) | Plan B (gbrain adapter) |
|---|---|---|
| New code | ~800 LOC | ~250 LOC |
| Days | 5 | 2 |
| Hard dependencies | Anthropic SDK only | Anthropic SDK + gbrain CLI (opt-in) |
| Corpus formats | `.txt`, `.md`, `.vtt`, `.srt` | everything gbrain ingests (PDF, audio, video, GitHub repos, tweets, voice) |
| Retrieval quality | local LLM extraction only | benefits from gbrain's hybrid (P@5=49%, R@5=98%) |
| Cost per entity | full LLM extraction (~$0.05) | Haiku-only translation (~$0.01) |
| Cross-vertical extensibility | per-vertical from-scratch | shared adapter pattern across all 4 verticals |
| User runtime requirements | Python only | Python + Bun (for gbrain) |
| Failure mode if upstream stops | n/a (no upstream) | adapter swap-out to another engine, <1 day |

**Recommendation:** ship Plan A first if no gbrain user exists yet; otherwise ship Plan B and keep Plan A as the fallback. Both can coexist forever — the runtime router decides per invocation.

## What this design DOES NOT decide

- Whether to ship Plan A first OR Plan B first OR both in one PR. That's a sequencing call best made with the user; this doc only argues that **both should ship eventually** and they share enough surface that doing them together is cheaper than doing them apart.
- Whether to extend to the other three verticals. Listed in "4-vertical extension" as LATER; revisit after the research adapter has 30+ days of usage data.
- The exact gbrain MCP tool names to call. The 30+ tool surface is documented in gbrain's source; the adapter's `fetch_entities` reads the actual tool catalog at install time and validates against `GbrainEntity` shape, rather than hardcoding tool names that may rename in gbrain's next release.
