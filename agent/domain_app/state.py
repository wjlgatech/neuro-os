"""
Base Pydantic schemas every vertical extends.

Three design choices:

1. **Inheritance, not generics.** Each vertical extends
   ``DailyContractBase`` to add its own priority shape. We avoided
   ``Generic[T]`` because Pydantic's runtime semantics get fiddly
   under generics, and the class hierarchy here is shallow (depth=2)
   so it's not worth the complexity.

2. **Frozen base + mutable extra.** All schema bases are
   ``model_config = ConfigDict(frozen=True)`` so callers can't mutate
   a value after construction (Law 5). Per-vertical schemas can
   relax this if they need mutability, but ``ConstructiveExpression``
   and ``ControlAction`` are explicitly frozen even there — they're
   the audit trail.

3. **Open ``extra: Dict[str, Any]`` field on ``NightlySummary``.**
   Each vertical surfaces 4 first-class metrics in the typed slots
   (``mae``, ``honor_rate``, ``primary_resource_used``,
   ``primary_success_rate``) and stuffs vertical-specific metrics
   into ``extra``. This is the **anti-metric-overload** mechanism
   from the PRD critique — verticals can't overflow the dashboard
   with 10 metrics.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared vocabularies
# ---------------------------------------------------------------------------


Confidence = Literal["low", "medium", "high"]
"""Borrowed from founder_loop. Reused by investment per Phase 0 critique
(don't introduce a parallel 0-1 float scale)."""


ControlOp = Literal[
    "continue",
    "propose_constructive_expression",
    "unlock_resource",
    "notify_resource_used",
    "force_intent_capture",
    "shorten_current_task",
    "swap_priority",
    "rest",
    "escalate_to_human",
    "replan",
    "block_target",
]
"""Substrate-level ops. Verticals MAY add their own ops via the
DomainConfig; the base set covers the universal pattern."""


ContractViolationType = Literal[
    "threshold_violation",
    "budget_violation",
    "block_target_not_authorized",
    "evidence_unverified",
]


# ---------------------------------------------------------------------------
# Contract (yesterday-self's signature)
# ---------------------------------------------------------------------------


class DailyContractBase(BaseModel):
    """Base shape every vertical's contract extends.

    Verticals replace ``priorities: list[<theirShape>]`` with their
    own typed priority list (research: ResearchThesis,
    investment: PositionThesis, startup: StartupHypothesis). The
    name ``priorities`` stays — the substrate's policy and reward
    ledger reference this attribute by name.
    """

    model_config = ConfigDict(frozen=True)

    date: str = Field(description="ISO YYYY-MM-DD the contract is valid for.")
    primary_resource_budget: int = Field(
        ge=0,
        description=(
            "Quantified daily budget for the vertical's resource of "
            "interest. founder_loop: entertainment minutes. research: "
            "papers-to-read. investment: position-changes. startup: "
            "thesis-pivots. Substrate doesn't know the unit; only the "
            "vertical does."
        ),
    )
    threshold_pct: int = Field(default=90, ge=50, le=100)
    signed_at: datetime
    notes: Optional[str] = Field(default=None, max_length=1000)

    # Verticals OVERRIDE this with their typed priority shape.
    priorities: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Vertical-specific priority list. Each vertical extends "
            "this class and overrides the type."
        ),
    )


class ContractCheck(BaseModel):
    """The contract-honor verdict on a single ControlAction.

    Same shape across all verticals. Identical to founder_loop's
    ContractCheck (pulled into substrate for reuse).
    """

    model_config = ConfigDict(frozen=True)

    honored: bool
    violation_type: Optional[ContractViolationType] = None
    notes: Optional[str] = Field(default=None, max_length=400)


# ---------------------------------------------------------------------------
# Tank
# ---------------------------------------------------------------------------


class TankStateBase(BaseModel):
    """Generic tank state. Same shape across verticals.

    ``percent`` is always 0-100. ``status`` is one of three positions
    that drive the policy hierarchy:
    * ``below_threshold`` — earned credits don't yet unlock the
      resource. Drift events route to sublimation.
    * ``threshold_within_budget`` — earned, budget remaining. Resource
      may be consumed honestly.
    * ``threshold_over_budget`` — earned but daily budget exhausted;
      further consumption debits at the abuse-tax rate.
    """

    model_config = ConfigDict(frozen=True)

    percent: float = Field(ge=0.0, le=100.0)
    credits_today: float = Field(ge=0.0)
    debits_today: float = Field(ge=0.0)
    threshold: int = Field(ge=50, le=100)
    budget_remaining: int = Field(
        ge=0,
        description="Units of the vertical's primary resource left for today.",
    )
    status: Literal[
        "below_threshold",
        "threshold_within_budget",
        "threshold_over_budget",
    ]


# ---------------------------------------------------------------------------
# Sublimation primitives
# ---------------------------------------------------------------------------


class ConstructiveExpressionBase(BaseModel):
    """A concrete alternative the substrate can propose when an urge
    fires pre-threshold. Verticals provide their own catalog of
    these via the ``DomainConfig``.

    Shape is identical to founder_loop's ConstructiveExpression
    (pulled into substrate). Verticals MAY subclass to add fields
    like ``research.references_papers`` but should not change the
    base fields.
    """

    model_config = ConfigDict(frozen=True)

    action: str = Field(min_length=1, max_length=120)
    duration_min: int = Field(ge=1, le=240)
    tank_credit_pct: float
    references: List[str] = Field(default_factory=list, max_length=10)
    then_reassess_at: Optional[datetime] = None


class DiagnosisBase(BaseModel):
    """The substrate's diagnosis shape.

    The ``underlying_need`` field is a STRING, not an enum, because
    each vertical has its own catalog. The substrate enforces (via
    ``DiagnosisCatalogProtocol``) that the value comes from the
    vertical's catalog.

    Constraint: ``options`` must have ≥1 entry. Enforced at
    construction time (Law 1).
    """

    model_config = ConfigDict(frozen=True)

    underlying_need: str = Field(
        min_length=1,
        description=(
            "Vertical-specific failure mode label. e.g. founder_loop: "
            "'fatigue'; research: 'paper_collector'; investment: "
            "'narrative_following'; startup: 'idea_chaos'."
        ),
    )
    confidence: Confidence
    reasoning: str = Field(max_length=400)
    options: List[ConstructiveExpressionBase] = Field(min_length=1, max_length=5)


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------


class ControlActionBase(BaseModel):
    """The substrate's ControlAction. Frozen, audit-carrying.

    Verticals MAY use this directly or subclass to add fields.
    """

    model_config = ConfigDict(frozen=True)

    op: ControlOp
    rationale: str = Field(min_length=1, max_length=600)
    payload: Dict[str, Any] = Field(default_factory=dict)
    auto_applied: bool = False
    inverse_op: Optional[ControlOp] = None
    tank_delta: float = 0.0
    contract_check: ContractCheck
    diagnosis: Optional[DiagnosisBase] = None


# ---------------------------------------------------------------------------
# Nightly summary
# ---------------------------------------------------------------------------


class NightlySummaryBase(BaseModel):
    """End-of-day rollup, 4 first-class metrics + extras.

    Per the Phase 0 PRD critique: each vertical surfaces exactly 4
    headline numbers via the typed slots. Vertical-specific metrics
    go into ``extra`` (so the dashboard isn't cluttered with 10
    metrics).

    The 4 first-class slots:
    * ``primary_metric_today`` — vertical's main quality measure
      (founder_loop: prediction MAE; research: mechanism-extraction
      rate; investment: calibration error; startup: strategic
      continuity).
    * ``honor_rate_today`` — fraction of decisions that honored the
      morning contract. Universal across verticals.
    * ``primary_resource_used_today`` — units of the vertical's
      primary resource consumed.
    * ``primary_success_rate_today`` — fraction of vertical's
      proposals that "stuck" (weren't overridden by violation).
    """

    model_config = ConfigDict(frozen=True)

    date: str
    vertical: str = Field(
        description=(
            "Which vertical produced this summary. One of: 'founder_loop', "
            "'research', 'investment', 'startup'."
        ),
    )
    primary_metric_today: Optional[float] = Field(default=None, ge=0.0)
    primary_metric_label: str = Field(
        description="Human-readable name of primary_metric_today (e.g. 'MAE')."
    )
    honor_rate_today: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    primary_resource_used_today: float = Field(default=0.0, ge=0.0)
    primary_resource_label: str = Field(
        description="Unit of primary_resource_used_today (e.g. 'minutes')."
    )
    primary_success_rate_today: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    goldens_failed: List[str] = Field(default_factory=list)
    action: Literal[
        "update_contract",
        "rebuild_predictor",
        "rebuild_diagnosis_catalog",
        "no_action",
    ] = Field(default="no_action")
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Vertical-specific metrics that don't fit the 4 first-class "
            "slots. Keep small — anti-metric-overload from PRD critique."
        ),
    )
