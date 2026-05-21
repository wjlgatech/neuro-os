"""
Research-vertical Pydantic schemas.

The substrate's ``DailyContractBase`` carries a generic
``priorities: List[Dict]``; we override that here with a typed
``ResearchPriority`` list. The substrate's tank/ledger code reads
``priorities`` by attribute name, so subclassing works cleanly.

Four user-facing primitives:

* **MechanismCard** — one per paper read. Captures mechanism /
  invariant / prediction / failure mode. The unit of "iteration" on a
  thesis is a card revision OR a PredictionLog entry citing the thesis.
* **AssumptionMap** — explicit list of assumptions a paper rests on.
  ≥3 assumptions/paper is the SMART target from the PRD.
* **PredictionLog** — a falsifiable prediction extracted from a paper,
  with a verification timestamp set to "+90 days" by default.
* **ResearchThesis** — the load-bearing question the researcher
  commits to for 40 days. Single-thesis enforcement: changing it
  requires a ``kill_event`` row.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from agent.domain_app.state import DailyContractBase


# Research-specific evidence vocabulary. Picked tighter than founder_loop's
# (no "commit_pushed" etc. — research evidence is paper- or experiment-shaped).
EVIDENCE_TYPE = Literal[
    "paper_read",        # mechanism card produced
    "experiment_run",    # falsifiable test executed
    "prediction_logged", # falsifiable prediction filed
    "contradiction_resolved",  # two prior cards reconciled
    "thesis_iterated",   # mechanism-card revision OR prediction citing thesis
    "transfer_observed", # cross-domain abstraction borrowed
]


# Verdict on a paper / proposal — used by Layer 2 synthesis to filter
# clusters (e.g. only cluster `foundational` + `useful`; route `skip` to
# the dashboard's "anti-survey-mode" counter). Optional — the extractor
# leaves None when it can't tell; the user fills it at /research-review.
VERDICT = Literal["foundational", "useful", "misleading", "skip"]


# Source pipeline tier. Lifted from piece 2's three-tier source pipeline:
# `seed` = foundational anchors (cite-of-cites); `frontier` = recent edge
# (last 12-18mo); `lateral` = adjacent-field papers using the same
# mechanism on a different problem. Optional on RawSource so users who
# don't classify their corpus stay supported.
SOURCE_TIER = Literal["seed", "frontier", "lateral"]


class FrameworkAxisNote(BaseModel):
    """One axis-aligned note on a mechanism. The user's framework axes
    are user-supplied (see ``agent.research.framework``); a card may
    speak to zero, one, or several of them. Generic — the substrate
    does NOT know what an axis means; it just round-trips the (name,
    note) pair so Layer 2 synthesis and Layer 3 briefs can preserve
    framework alignment across the pipeline.

    Examples (not hard-coded — user-supplied):
      * axis_name="Observation",    note="provides on-device sensor stream..."
      * axis_name="Moat",           note="data network effect via..."
      * axis_name="founder ritual", note="protects deep-work blocks via..."
    """

    model_config = ConfigDict(frozen=True)

    axis_name: str = Field(min_length=1, max_length=80)
    note: str = Field(min_length=1, max_length=400)


class MechanismCard(BaseModel):
    """One per paper. The 4-field card from the PRD's Transformation #1.

    Frozen — once you've extracted a mechanism card, you log
    *revisions* as new versions, you don't mutate the original. That
    keeps the audit trail honest.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    ts: datetime
    paper_title: str = Field(min_length=1, max_length=400)
    paper_source: str = Field(
        min_length=1,
        max_length=400,
        description="DOI / URL / arXiv id / human-readable cite. "
                    "Required for evidence_strength scoring.",
    )
    mechanism: str = Field(
        min_length=1,
        max_length=600,
        description="What CAUSAL STRUCTURE generates the paper's behavior?",
    )
    invariant: str = Field(
        min_length=1,
        max_length=400,
        description="What stays the same across the cases the paper covers?",
    )
    prediction: str = Field(
        min_length=1,
        max_length=400,
        description="A falsifiable consequence of the mechanism.",
    )
    failure_mode: str = Field(
        min_length=1,
        max_length=400,
        description="A condition under which the mechanism breaks.",
    )
    thesis_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="The ResearchThesis.id this card iterates on, if any. "
                    "Cards without a thesis_id count toward the "
                    "'topic_hopper' failure-mode signal.",
    )
    revision_of: Optional[str] = Field(
        default=None,
        max_length=64,
        description="If this is a revision of an earlier card, the prior "
                    "card's id. Iterations on a thesis are counted by "
                    "summing revisions.",
    )
    entity_mentions: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Lane-4 entity propagation: slugs (kebab-case) of "
                    "Entity rows that this card mentions. On card "
                    "acceptance, each slug is upsert_entity'd into the "
                    "cross-vertical store (default-PRIVATE to research "
                    "until the user explicitly shares).",
    )

    # Layer-1 deepening (Three-Layer Research OS — extraction fields).
    # All optional so existing accepted cards round-trip unchanged.
    first_principle: Optional[str] = Field(
        default=None,
        max_length=400,
        description="The deepest, most general truth the mechanism rests "
                    "on. Often unstated in the paper itself; transferable "
                    "BEYOND the paper's domain. Distinct from `mechanism` "
                    "(causal story) and `invariant` (load-bearing relation).",
    )
    anti_pattern: Optional[str] = Field(
        default=None,
        max_length=400,
        description="The way the mechanism is commonly misunderstood or "
                    "misapplied. The version that looks right but isn't. "
                    "Knowing this is often more valuable than knowing the "
                    "mechanism itself.",
    )
    transferability_test: Optional[str] = Field(
        default=None,
        max_length=400,
        description="One concrete domain (inside or outside the paper's "
                    "field) where this mechanism would also apply. If "
                    "blank, the mechanism may be a local optimization "
                    "rather than a first principle.",
    )
    verdict: Optional[VERDICT] = Field(
        default=None,
        description="Reader's judgment: foundational (load-bearing idea), "
                    "useful (toolbox entry), misleading (looks right, "
                    "isn't), skip (not worth re-reading). Used by Layer-2 "
                    "synthesis to filter and by the dashboard's "
                    "anti-survey-mode counter.",
    )
    one_sentence_compression: Optional[str] = Field(
        default=None,
        max_length=280,
        description="Tweet-length distillation. If the reader can't "
                    "produce one, they probably don't understand the "
                    "paper yet. Compression forces understanding.",
    )
    framework_alignment: List[FrameworkAxisNote] = Field(
        default_factory=list,
        max_length=10,
        description="Per-axis notes against the user's framework "
                    "(see agent.research.framework). The substrate does "
                    "not interpret the axis names; it just preserves them.",
    )


class AssumptionMap(BaseModel):
    """≥3 assumptions per paper (PRD SMART actionable #4)."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    ts: datetime
    mechanism_card_id: str = Field(min_length=1, max_length=64)
    assumptions: List[str] = Field(
        min_length=1,
        max_length=20,
        description="Hidden / unstated assumptions the paper rests on.",
    )
    invalidation_conditions: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Conditions under which each assumption would fail.",
    )


class PredictionLog(BaseModel):
    """A falsifiable prediction filed against a thesis or paper.

    PRD SMART #3 target: 60 predictions by Day 40.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    ts: datetime
    thesis_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="The thesis this prediction supports/tests.",
    )
    mechanism_card_id: Optional[str] = Field(
        default=None,
        max_length=64,
    )
    prediction: str = Field(
        min_length=1,
        max_length=600,
        description="What the researcher predicts will be observed.",
    )
    verification_at: datetime = Field(
        description="When the prediction can be checked. Default +90 days "
                    "from filing if not specified by caller.",
    )
    outcome: Optional[Literal["correct", "incorrect", "unresolved"]] = None
    outcome_notes: Optional[str] = Field(default=None, max_length=600)


class ResearchThesis(BaseModel):
    """The load-bearing question the researcher commits to.

    Single-thesis enforcement: ``status='active'`` means the
    researcher is iterating on this; changing the active thesis
    requires explicitly killing the prior one (``status='killed'``)
    with a ``kill_reason``. The substrate's tank logic charges an
    abuse-tax for >2 kills/40d (anti-novelty-addiction guard from
    PRD's first-principles foundation).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=400)
    question: str = Field(
        min_length=10,
        max_length=600,
        description="The thesis as a precise question. e.g. 'How do "
                    "stable world models emerge through recursive "
                    "memory and prediction loops?'",
    )
    signed_at: datetime
    status: Literal["active", "killed", "graduated"] = "active"
    kill_reason: Optional[str] = Field(default=None, max_length=600)


class ResearchPriority(BaseModel):
    """One priority on the daily research contract.

    Verticals override DailyContractBase.priorities with a typed
    list of these. Each priority is bound to the active thesis
    (single-thesis enforcement) — priorities that don't reference a
    thesis_id count as topic-hopper drift.
    """

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, max_length=200)
    evidence_type: EVIDENCE_TYPE
    evidence_target: str = Field(min_length=1, max_length=200)
    weight: int = Field(ge=1, le=3)
    thesis_id: str = Field(
        min_length=1,
        max_length=64,
        description="Required: the active thesis this priority advances. "
                    "Substrate enforces that priorities tie to a thesis.",
    )
    status: Literal["pending", "in_progress", "evidenced", "abandoned"] = "pending"
    evidenced_at: Optional[datetime] = None


class ResearchContract(DailyContractBase):
    """Research's daily contract. Overrides ``priorities`` with the
    typed list. ``primary_resource_budget`` here counts maximum
    papers-to-read per day (default 1, per the PRD's Mechanism
    Extraction SMART #1)."""

    priorities: List[ResearchPriority] = Field(min_length=1, max_length=5)
    active_thesis_id: str = Field(
        min_length=1,
        max_length=64,
        description="The single load-bearing thesis for the 40-day window.",
    )


# ---------------------------------------------------------------------------
# Ingestion-pipeline schemas (Lane 1: Plan B / gbrain adapter).
#
# These three schemas pin the L0–L1 ingestion contract: a corpus comes in,
# proposed mechanism cards land in a review queue, the human decides what
# becomes a real `MechanismCard`. The queue is on disk under
# ~/.neuro_os_research/proposals/{pending,accepted,rejected}/.
# ---------------------------------------------------------------------------


EXTRACTION_METHOD = Literal["llm-anthropic", "gbrain-mcp", "fallback-heuristic"]


class RawSource(BaseModel):
    """One ingestible source file. v0 is text-only; PDFs / videos must
    be pre-converted to .txt or .md by the user (or by gbrain upstream)."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1, max_length=128)
    path: Path
    title: str = Field(min_length=1, max_length=400)
    author: str = Field(min_length=1, max_length=200)
    publish_date: Optional[str] = Field(
        default=None,
        max_length=32,
        description="ISO-8601 date string; kept as str so frozen=True works "
                    "across pickle/JSON round-trips uniformly.",
    )
    source_url: Optional[str] = Field(default=None, max_length=2000)
    topic_tags: List[str] = Field(default_factory=list, max_length=20)
    word_count: int = Field(ge=0)
    sha256: str = Field(
        min_length=64,
        max_length=64,
        description="Hex digest of the file body. Used to detect re-ingestion "
                    "of an unchanged source.",
    )
    tier: Optional[SOURCE_TIER] = Field(
        default=None,
        description="Source-pipeline tier annotation. `seed` = foundational "
                    "anchor; `frontier` = recent edge (last 12-18mo); "
                    "`lateral` = adjacent-field paper using the same "
                    "mechanism on a different problem. Optional; left None "
                    "means the user hasn't classified the corpus.",
    )


class MechanismCardProposal(BaseModel):
    """A `MechanismCard`-shaped object that hasn't been accepted yet.

    Mirrors `MechanismCard` field-for-field plus provenance + extraction
    metadata. Lives in `proposals/{pending,accepted,rejected}/<id>.json`.
    Acceptance writes a `MechanismCard` to `mechanism_cards/<id>.json`
    via the existing `write_mechanism_card(...)` and moves the proposal
    file to `accepted/`.

    Frozen — once a proposal exists, it does not mutate; user edits
    happen via a new proposal that supersedes it.
    """

    model_config = ConfigDict(frozen=True)

    proposal_id: str = Field(min_length=1, max_length=128)
    proposed_at: datetime
    status: Literal["pending", "accepted", "rejected", "edited"] = "pending"

    # Candidate card payload — same shape as MechanismCard:
    paper_title: str = Field(min_length=1, max_length=400)
    paper_source: str = Field(min_length=1, max_length=2000)
    mechanism: str = Field(min_length=1, max_length=600)
    invariant: str = Field(min_length=1, max_length=400)
    prediction: str = Field(min_length=1, max_length=400)
    failure_mode: str = Field(min_length=1, max_length=400)
    thesis_id: Optional[str] = Field(default=None, max_length=64)

    # Provenance — every claim traces back to an excerpt (Law 2 prompt-time
    # enforcement; pinned here as a typed field so the audit trail is real):
    source_id: str = Field(min_length=1, max_length=128)
    source_excerpt: str = Field(
        min_length=1,
        max_length=1000,
        description="The exact text the extractor pulled this proposal from.",
    )
    line_range: Optional[Tuple[int, int]] = None

    # Extraction metadata:
    extraction_method: EXTRACTION_METHOD
    extraction_model: Optional[str] = Field(default=None, max_length=128)
    confidence: Literal["low", "medium", "high"] = "low"
    reasoning: str = Field(
        min_length=1,
        max_length=1000,
        description="One paragraph: why the extractor thinks this is a real "
                    "mechanism (not just a description).",
    )
    entity_mentions: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Lane-4 entity propagation: candidate slugs the user "
                    "may bind to this proposal at /research-review accept "
                    "time. Empty in the v0 adapter (extractor is conservative "
                    "and lets the user name entities manually).",
    )

    # Layer-1 deepening — mirror of MechanismCard fields. All optional so
    # the extractor can omit any field it isn't confident about; the user
    # can fill them in at /research-review before acceptance.
    first_principle: Optional[str] = Field(default=None, max_length=400)
    anti_pattern: Optional[str] = Field(default=None, max_length=400)
    transferability_test: Optional[str] = Field(default=None, max_length=400)
    verdict: Optional[VERDICT] = None
    one_sentence_compression: Optional[str] = Field(default=None, max_length=280)
    framework_alignment: List[FrameworkAxisNote] = Field(
        default_factory=list,
        max_length=10,
    )
    source_tier: Optional[SOURCE_TIER] = Field(
        default=None,
        description="Tier carried over from the originating RawSource so "
                    "the dashboard can show tier balance without re-reading "
                    "the source pipeline. Optional; None means unclassified.",
    )


class IngestionRun(BaseModel):
    """Audit row for one ``research ingest`` invocation.

    Appended to ``~/.neuro_os_research/ingestion_runs.jsonl`` so the
    user can later answer ``research dashboard``-style questions like
    "how many sources did I ingest in the last 40 days, and how many
    of them produced accepted cards?" (Lane 5 reads this file.)
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1, max_length=128)
    started_at: datetime
    finished_at: datetime
    sources_scanned: int = Field(ge=0)
    sources_skipped_unchanged: int = Field(ge=0)
    proposals_emitted: int = Field(ge=0)
    # Count of proposals the LLM produced that we DID NOT write because an
    # existing pending/accepted proposal already had the same mechanism+
    # invariant hash. Defaults to 0 for backwards-compat with older log rows.
    proposals_skipped_duplicate: int = Field(default=0, ge=0)
    extraction_method: EXTRACTION_METHOD
    cost_usd_estimate: float = Field(ge=0.0)


# ---------------------------------------------------------------------------
# gbrain-MCP boundary schemas (Plan B).
#
# These pin the gbrain MCP response shape so any drift in gbrain's API
# becomes an explicit ValidationError instead of silent data corruption.
# ---------------------------------------------------------------------------


class GbrainEntity(BaseModel):
    """A single entity returned by gbrain's MCP query.

    Field names mirror gbrain's response shape; if gbrain ever changes
    its API, this schema is the single break-point — Pydantic will raise
    in CI before any production data is touched.
    """

    model_config = ConfigDict(frozen=True)

    slug: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=400)
    page_kind: Literal["claim", "person", "company", "topic", "note", "other"]
    body_excerpt: str = Field(min_length=1, max_length=2000)
    typed_relationships: List[str] = Field(default_factory=list, max_length=50)
    backlinks: int = Field(ge=0, default=0)
    confidence_hint: Optional[Literal["low", "medium", "high"]] = None


class GbrainQuerySpec(BaseModel):
    """The MCP query the adapter issues. Pinned to keep the call site
    auditable: every gbrain call is shaped by one of these."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(min_length=1, max_length=400)
    page_kinds: List[str] = Field(default_factory=lambda: ["claim"], max_length=10)
    limit: int = Field(ge=1, le=200, default=25)
    since: Optional[datetime] = None
    typed_relationships: List[str] = Field(default_factory=list, max_length=20)
