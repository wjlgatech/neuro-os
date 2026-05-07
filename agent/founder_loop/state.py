"""
``founder_loop`` typed schemas.

All Pydantic models for the loop live here so every other module imports
from one place. The schemas encode the philosophy ("reward economy +
sublimation, not suppression") into types: there is no way to construct a
``ControlAction`` with op ``unlock_entertainment`` without also producing
a ``TankState`` that says the user has earned it, and there is no way to
construct a ``Diagnosis`` that doesn't name an underlying need from the
fixed vocabulary. Type errors here = philosophy errors.

Schema groups:

* **Observed state**: ``FounderState`` — what workflowx (or its fixture)
  reports. No vibe-only fields; every attribute corresponds to a real
  measurement.
* **Forecast**: ``ForecastedState`` — what ``predict.py`` returns. Names
  the underlying urge AND the underlying need, not just a "drift" score.
* **Contract layer**: ``Priority``, ``Contract`` — the Ulysses pact.
  Yesterday-self signs; today-self is bound by it. Evidence vocabulary is
  a fixed enum so today-self can't self-deceive at 3pm.
* **Reward economy**: ``TankState`` — the productivity tank. Pure-function
  reduce over the registry.
* **Sublimation**: ``Diagnosis``, ``ConstructiveExpression`` — the engine
  that names the underlying need behind an urge and proposes a
  constructive expression.
* **Action**: ``ControlAction`` — the discrete decision the loop emits,
  always carrying a ``contract_check`` so the audit trail is closed.
* **Result**: ``TickResult``, ``NightlySummary`` — what consumers see.

This module has no I/O and no LLM imports. It is safe to import from
anywhere.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Vocabularies — fixed enums. Extending these is a deliberate ontology
# change, not a one-off addition.
# ---------------------------------------------------------------------------

EvidenceType = Literal[
    "commit_pushed",
    "pr_opened",
    "pr_merged",
    "doc_published",
    "count_reached",
    "human_signoff",
    "artifact_uploaded",
]

PriorityStatus = Literal["pending", "in_progress", "evidenced", "abandoned"]

UnderlyingNeed = Literal[
    "fatigue",
    "novelty_hunger",
    "social",
    "frustration",
    "decision_fatigue",
    "embodied_hunger",
    "embodied_eye_strain",
    "earned_reward",
    "post_reward_fatigue",
    "none",
]

UrgeType = Literal["none", "entertainment", "escape", "novelty"]

Confidence = Literal["low", "medium", "high"]

ControlOp = Literal[
    "continue",
    "unlock_entertainment",
    "propose_constructive_expression",
    "notify_ration_used",
    "force_intent_capture",
    "start_25min_sprint",
    "shorten_current_task",
    "swap_priority",
    "rest",
    "escalate_to_human",
    "replan",
    "block_url",
]

# Ops that may be applied without a human in the loop, once trust is
# established. Block ops never auto-apply — they always require explicit
# user pre-authorization via the contract.
AUTO_APPLY_DEFAULT: set = {"continue"}
AUTO_APPLY_GRADUATABLE: set = {
    "propose_constructive_expression",
    "force_intent_capture",
    "start_25min_sprint",
}

TankStatus = Literal["below_threshold", "threshold_within_ration", "threshold_over_ration"]

ContractViolationType = Literal[
    "threshold_violation",  # consumed entertainment with tank < threshold
    "ration_violation",  # consumed entertainment beyond morning-allotted minutes
    "block_target_not_authorized",  # block_url for a target not in pre_authorized_blocks
    "evidence_unverified",  # priority marked done without evidence_type satisfied
]


# ---------------------------------------------------------------------------
# Observed state
# ---------------------------------------------------------------------------


class FounderState(BaseModel):
    """A single hourly observation of the user.

    Every field corresponds to something the WorkflowxAdapter can
    actually measure. Vibe-only fields (``energy_level``, ``momentum``,
    ``spiritual_alignment``) are deliberately absent — they would let
    self-deception leak in through the type system.
    """

    timestamp: datetime = Field(description="UTC timestamp of this observation.")

    # Recent activity (last hour rolling window).
    distraction_minutes_last_hour: float = Field(ge=0.0, le=60.0)
    deep_work_minutes_last_hour: float = Field(ge=0.0, le=60.0)
    context_switches_last_hour: int = Field(ge=0)

    # Embodied signals — the body has needs the conscious mind doesn't
    # always notice. Default ``None`` means the sensor isn't reporting,
    # not that the value is zero.
    sleep_last_night_hours: Optional[float] = Field(default=None, ge=0.0, le=14.0)
    time_since_last_meal_min: Optional[int] = Field(default=None, ge=0)
    hours_continuous_screen: Optional[float] = Field(default=None, ge=0.0)

    # Social signal (Scenario D — Sunday loneliness).
    last_outbound_message_age_h: Optional[float] = Field(default=None, ge=0.0)

    # 7-day trajectory (rolling means; computed by observe.py).
    distraction_7d_avg: Optional[float] = Field(default=None, ge=0.0)
    deep_work_7d_avg: Optional[float] = Field(default=None, ge=0.0)

    # Memory: what the user said they were doing. Free-text but bounded.
    last_intent: Optional[str] = Field(default=None, max_length=2000)

    # Day-shape: rest day, work day, ship day. Drives policy negative
    # cases (#7).
    day_kind: Literal["work", "rest", "ship", "unspecified"] = Field(default="unspecified")


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------


class ForecastedState(BaseModel):
    """``predict.py`` output: what the next hour likely looks like.

    The two ``predicted_*`` distraction/deep-work fields drive the MAE
    research bet. The ``predicted_urge`` and ``predicted_underlying_need``
    fields drive sublimation. The four together are what makes the
    predictor useful — predicting drift without naming the underlying
    need would re-create the brute-force model the philosophy rejects.
    """

    predicted_distraction_min: float = Field(ge=0.0, le=60.0)
    predicted_deep_work_min: float = Field(ge=0.0, le=60.0)
    predicted_urge: UrgeType
    predicted_underlying_need: UnderlyingNeed
    predicted_main_failure_mode: Optional[str] = Field(
        default=None,
        description=(
            "Backwards-compat label preserved for UAT scenarios #1-#3 that "
            "name failure modes (youtube_drift, research_rabbit_hole, "
            "delusional_intent_capture). The new sublimation pipeline "
            "drives off ``predicted_underlying_need``; this field is a "
            "consequence of the need + context."
        ),
    )
    confidence: Confidence
    reasoning: str = Field(max_length=400)


# ---------------------------------------------------------------------------
# Contract layer (the Ulysses pact)
# ---------------------------------------------------------------------------


class Priority(BaseModel):
    """A single daily priority, with explicit evidence criterion.

    The evidence_type vocabulary is a fixed enum so today-self at 3pm
    can't redefine "done" to mean whatever they want. ``evidence_target``
    is the concrete proof string (``"neuro-os#142"``,
    ``"2_commits"``, ``"5_pages"``, etc.).
    """

    title: str = Field(min_length=1, max_length=200)
    evidence_type: EvidenceType
    evidence_target: str = Field(min_length=1, max_length=200)
    weight: int = Field(ge=1, le=3, description="1 = small, 2 = medium, 3 = large")
    status: PriorityStatus = Field(default="pending")
    evidenced_at: Optional[datetime] = Field(default=None)
    evidence_proof: Optional[str] = Field(
        default=None,
        description=(
            "When status flips to 'evidenced', this carries the verified "
            "proof string (commit SHA, PR URL, etc.) that satisfied "
            "evidence_type."
        ),
    )


class AbuseTax(BaseModel):
    """How much the tank is debited when the contract is violated.

    Both multipliers default to 2.0 — twice the normal entertainment
    debit rate. The user can dial these per day in the morning ritual.
    """

    threshold_violation_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    ration_violation_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)


class Contract(BaseModel):
    """The pre-committed daily contract — yesterday-self's signature.

    Today-self can override anything in here, but every override is
    logged on the resulting ``ControlAction`` with ``contract_check.honored=False``
    and a ``violation_type``, and the tank debits at the abuse-tax rate.
    Nothing is silently denied.
    """

    date: str = Field(description="ISO date (YYYY-MM-DD) the contract is valid for.")
    priorities: List[Priority] = Field(min_length=1, max_length=10)
    entertainment_ration_min: int = Field(
        ge=0,
        le=480,
        description="Minutes of entertainment unlocked once tank crosses threshold.",
    )
    threshold_pct: int = Field(default=90, ge=50, le=100)
    abuse_tax: AbuseTax = Field(default_factory=AbuseTax)
    pre_authorized_blocks: List[str] = Field(
        default_factory=list,
        description=(
            "URL/domain patterns yesterday-self pre-authorized as "
            "block targets. block_url ops for any other target are "
            "refused (see ContractViolationType.block_target_not_authorized)."
        ),
    )
    signed_at: datetime = Field(description="When yesterday-self signed.")
    notes: Optional[str] = Field(default=None, max_length=1000)


class ContractCheck(BaseModel):
    """The contract-honor verdict on a single ControlAction.

    Every action carries one of these. ``honored=True`` means today-self
    abided by yesterday-self's signature. ``honored=False`` means today-
    self overrode the contract — the action is still performed, but the
    tank takes the abuse-tax debit and the registry row records the
    violation.
    """

    honored: bool
    violation_type: Optional[ContractViolationType] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=400)


# ---------------------------------------------------------------------------
# Reward economy
# ---------------------------------------------------------------------------


class TankState(BaseModel):
    """Productivity tank.

    Pure function over registry rows + today's contract. The status enum
    is what policy.py branches on — there are exactly three positions
    (pre-threshold / earned-and-within-ration / earned-but-over-ration),
    each with a distinct policy response.
    """

    percent: float = Field(ge=0.0, le=100.0)
    credits_today: float = Field(ge=0.0)
    debits_today: float = Field(ge=0.0)
    threshold: int = Field(ge=50, le=100)
    ration_remaining_min: int = Field(
        ge=0,
        description=(
            "Minutes of entertainment ration left. Decreases when "
            "unlock_entertainment fires; never negative (over-ration "
            "consumption is logged as a debit, not a negative remaining)."
        ),
    )
    status: TankStatus


# ---------------------------------------------------------------------------
# Sublimation
# ---------------------------------------------------------------------------


class ConstructiveExpression(BaseModel):
    """A concrete alternative offered when an urge fires pre-threshold.

    Each carries:

    * ``action`` — short imperative phrase (e.g. ``"20_min_nap"``,
      ``"voice_memo_to_friend"``).
    * ``duration_min`` — how long it takes; comparable to the urge's
      time-cost so the trade is honest.
    * ``tank_credit_pct`` — how much the tank gains if accepted. Rest
      and embodied-need actions credit the tank (rest is productive);
      sublimated curiosity/social actions credit the tank a smaller
      amount; refusing to sublimate and consuming raw entertainment is
      a debit.
    * ``references`` — pointers into ``data/queues/*.json`` for
      concrete suggestions ("read [the bookmarked Karpathy post]").
      Without queues populated, these fall back to generic advice.
    * ``then_reassess_at`` — when set, the loop honors a follow-up
      tick at this time (Scenarios E, F).
    """

    action: str = Field(min_length=1, max_length=80)
    duration_min: int = Field(ge=1, le=240)
    tank_credit_pct: float = Field(
        description=(
            "Positive = credits the tank (constructive expression of "
            "the underlying need). Negative = debits (the suppression "
            "fallback that we want to avoid)."
        )
    )
    references: List[str] = Field(default_factory=list, max_length=10)
    then_reassess_at: Optional[datetime] = Field(default=None)


class Diagnosis(BaseModel):
    """The named underlying need + a list of constructive expressions.

    ``options`` is ordered by the diagnosis layer's recommendation —
    options[0] is the strongest fit. The user / approval gate may pick
    any option or refuse all of them.
    """

    underlying_need: UnderlyingNeed
    confidence: Confidence
    reasoning: str = Field(max_length=400)
    options: List[ConstructiveExpression] = Field(min_length=1, max_length=5)


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------


class ControlAction(BaseModel):
    """The single decision a tick emits.

    Always carries a ``contract_check`` (audit trail) and a
    ``tank_delta`` (tank bookkeeping). ``inverse_op`` is the action that
    would undo this one — required for any auto-apply op so reversibility
    is real.
    """

    op: ControlOp
    rationale: str = Field(min_length=1, max_length=600)
    payload: Dict[str, Any] = Field(default_factory=dict)
    auto_applied: bool = Field(default=False)
    inverse_op: Optional[ControlOp] = Field(default=None)
    tank_delta: float = Field(
        default=0.0,
        description=(
            "Effect on tank percent. Positive = credit (priority "
            "evidenced, sublimation accepted, rest taken). Negative "
            "= debit (entertainment consumed, contract violated)."
        ),
    )
    contract_check: ContractCheck
    diagnosis: Optional[Diagnosis] = Field(
        default=None,
        description=(
            "Set when op is propose_constructive_expression or "
            "notify_ration_used (residual diagnosis)."
        ),
    )


# ---------------------------------------------------------------------------
# Tick + nightly results
# ---------------------------------------------------------------------------


class TickResult(BaseModel):
    """What ``loop.tick()`` returns to the caller (Founder OS approval gate)."""

    state: FounderState
    forecasted: ForecastedState
    tank: TankState
    action: ControlAction
    registry_row_id: Optional[str] = Field(
        default=None,
        description="Identifier of the appended registry row. None in dry-run.",
    )


class NightlySummary(BaseModel):
    """End-of-day rollup for the nightly trigger.

    Carries the four V0 daily-report metrics: prediction MAE,
    contract-honor rate, entertainment-usage minutes, and
    sublimation-success rate. The first two are research bets; the
    second two help diagnose whether the loop is actually transmuting
    desire (high success rate, low usage) or just observing it (low
    success rate, regardless of usage).
    """

    date: str
    mae_today: Optional[float] = Field(default=None, ge=0.0)
    mae_7d_ago: Optional[float] = Field(default=None, ge=0.0)
    contract_honor_rate_today: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    contract_honor_rate_7d: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    entertainment_usage_min_today: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Total entertainment minutes consumed today (sum of "
            "unlock_entertainment payload durations across all rows, "
            "honored or not)."
        ),
    )
    sublimation_success_rate_today: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Of propose_constructive_expression ops fired today, "
            "fraction that 'stuck' — i.e. were not followed within the "
            "same day by an unlock_entertainment with "
            "contract_check.honored=False (a threshold/ration "
            "violation). None when no proposals fired today."
        ),
    )
    goldens_failed: List[str] = Field(default_factory=list)
    action: Literal[
        "update_contract",
        "rebuild_predictor",
        "rebuild_sublimation_catalog",
        "no_action",
    ] = Field(default="no_action")
    notes: Optional[str] = Field(default=None, max_length=1000)


__all__ = [
    # vocabularies
    "EvidenceType",
    "PriorityStatus",
    "UnderlyingNeed",
    "UrgeType",
    "Confidence",
    "ControlOp",
    "TankStatus",
    "ContractViolationType",
    "AUTO_APPLY_DEFAULT",
    "AUTO_APPLY_GRADUATABLE",
    # observed
    "FounderState",
    # forecast
    "ForecastedState",
    # contract
    "Priority",
    "AbuseTax",
    "Contract",
    "ContractCheck",
    # reward economy
    "TankState",
    # sublimation
    "ConstructiveExpression",
    "Diagnosis",
    # action
    "ControlAction",
    # results
    "TickResult",
    "NightlySummary",
]
