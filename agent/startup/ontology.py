"""
Startup-vertical Pydantic schemas.

Four primitives:

* **StartupHypothesis** — the single load-bearing thesis the founder
  commits to for 40 days. Single-thesis enforcement: changing
  requires explicit kill_event with reason. Penalty (abuse-tax) when
  >3 changes in 40 days (borrowed from founder_loop's contract
  pattern; anti-novelty-addiction guard).
* **Bottleneck** — explicit type enum (distribution / product / ops /
  founder_capacity); each must answer "what constraint does this
  remove?"
* **AudienceSignal** — every audience interaction structured as
  evidence + objection + resonance + repeated-pain. Carries a
  ``social_channel`` enum (v0 = manual paste).
* **StartupContract** — daily contract; primary_resource_budget here
  counts max thesis-pivots per day (default 0, hard upper bound 1).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from agent.domain_app.state import DailyContractBase


# Startup-specific evidence vocabulary. Designed for the founder loop:
# every priority must be a hypothesis-validation, audience-listening,
# constraint-discovery, or trust-compounding action.
EVIDENCE_TYPE = Literal[
    "hypothesis_validated",        # one experimental result on the active thesis
    "audience_signal_captured",    # AudienceSignal row filed
    "bottleneck_resolved",         # one constraint removed (Bottleneck.resolved=True)
    "trust_interaction",           # repeat-engagement event with a real human
    "kill_event_logged",           # idea/feature killed, reason logged
    "narrative_pinned",            # consistent positioning paragraph signed
]


SocialChannel = Literal[
    "twitter", "linkedin", "blog", "email", "in_person",
    "discord", "podcast", "substack", "manual_paste",
]
"""Where an AudienceSignal came from. v0 = manual paste; v1 wires
API integrations for the listed sources."""


BottleneckType = Literal[
    "distribution",       # can't reach people
    "product",            # can reach but can't deliver value
    "ops",                # can deliver but can't scale
    "founder_capacity",   # founder is the bottleneck
]


class StartupHypothesis(BaseModel):
    """The single load-bearing thesis. Frozen.

    Changing the active hypothesis requires explicit kill: a new
    hypothesis row with ``status='killed'``, a ``kill_reason``, and
    a ``parent_hypothesis_id``. The substrate's tank applies an
    abuse-tax for >3 kills/40d (anti-idea-chaos guard from PRD).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=400)
    hypothesis: str = Field(
        min_length=10,
        max_length=2000,
        description="The thesis as a falsifiable claim. e.g. 'Solo "
                    "founders building AI agents will pay $X/mo for "
                    "calm + coherence on top of cognitive overload.'",
    )
    target_segment: str = Field(
        min_length=1,
        max_length=400,
        description="The specific human-shaped audience this is FOR.",
    )
    falsification_signal: str = Field(
        min_length=1,
        max_length=600,
        description="What evidence would force this hypothesis to die?",
    )
    expected_kpi_effect: str = Field(
        min_length=1,
        max_length=400,
        description="If true, what KPI moves and by how much in 90 days?",
    )
    signed_at: datetime
    status: Literal["active", "killed", "graduated"] = "active"
    kill_reason: Optional[str] = Field(default=None, max_length=600)
    parent_hypothesis_id: Optional[str] = Field(default=None, max_length=64)


class Bottleneck(BaseModel):
    """One bottleneck per week (PRD SMART #3).

    Required answer to "what constraint does this remove?" — every
    feature/initiative the founder considers MUST tie to a bottleneck.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    ts: datetime
    name: str = Field(min_length=1, max_length=200)
    bottleneck_type: BottleneckType
    evidence: List[str] = Field(
        min_length=1,
        max_length=20,
        description="Why is this the load-bearing constraint right now?",
    )
    proposed_unblock: str = Field(
        min_length=1,
        max_length=600,
        description="What action removes this bottleneck?",
    )
    deadline: Optional[datetime] = Field(
        default=None,
        description="When the unblock attempt should be evaluated.",
    )
    resolved: bool = False
    resolution_evidence: Optional[str] = Field(default=None, max_length=600)


class AudienceSignal(BaseModel):
    """One interaction-derived signal. PRD SMART #2 target: 120
    audience signals over 40 days (3/day average)."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    ts: datetime
    social_channel: SocialChannel
    raw_text: str = Field(
        min_length=1,
        max_length=2000,
        description="The literal text/observation the founder captured.",
    )
    interpreted_kind: Literal[
        "objection", "resonance", "confusion", "repeat_pain", "endorsement",
    ]
    person_id: Optional[str] = Field(
        default=None,
        max_length=80,
        description="A handle/name the founder uses to track unique people. "
                    "Repeat-engagement (same person_id on multiple signals) "
                    "is the trust_density signal.",
    )
    hypothesis_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="The active hypothesis this signal touches.",
    )


class StartupPriority(BaseModel):
    """One priority on the daily startup contract."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, max_length=200)
    evidence_type: EVIDENCE_TYPE
    evidence_target: str = Field(min_length=1, max_length=200)
    weight: int = Field(ge=1, le=3)
    hypothesis_id: str = Field(
        min_length=1,
        max_length=64,
        description="Required: the active hypothesis this priority "
                    "advances. Single-thesis enforcement: priorities "
                    "without a hypothesis_id are rejected.",
    )
    status: Literal["pending", "in_progress", "evidenced", "abandoned"] = "pending"
    evidenced_at: Optional[datetime] = None


class StartupContract(DailyContractBase):
    """Startup's daily contract. ``primary_resource_budget`` here counts
    max thesis-pivots/day (default 0; hard cap 1). Default-zero
    enforces the 40-day continuity bet."""

    priorities: List[StartupPriority] = Field(min_length=1, max_length=5)
    active_hypothesis_id: str = Field(
        min_length=1,
        max_length=64,
        description="The single load-bearing hypothesis.",
    )
