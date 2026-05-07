"""
``evaluate.py`` — reconcile predicted-vs-actual + Belief OS gate.

Two responsibilities:

1. **Reconcile predicted-vs-actual** for the MAE research bet. Given the
   most recent registry row's forecast and the current ``FounderState``,
   compute the absolute error on distraction_minutes and deep_work_minutes.

2. **Belief OS gate.** When the user's ``last_intent`` invokes a
   reasoning failure mode (``survivorship_bias``, ``falsifiability``),
   surface that finding so policy can route to ``escalate_to_human``.
   This is the explicit hand-off from neuro-os Belief OS into the
   founder_loop policy — the wiring that the UAT scenario #4 verifies.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from agent.founder_loop.state import FounderState, ForecastedState


class IntentFlag(BaseModel):
    """Belief-OS-flagged intent finding."""

    flagged: bool
    mechanism: Optional[str] = Field(
        default=None,
        description=(
            "The reasoning primitive Belief OS classified the intent as "
            "(e.g. 'survivorship_bias'). None when unflagged."
        ),
    )
    reason: Optional[str] = Field(default=None, max_length=600)


class HourlyError(BaseModel):
    """Predicted-vs-actual error for one hourly tick."""

    distraction_abs_error: float = Field(ge=0.0)
    deep_work_abs_error: float = Field(ge=0.0)
    underlying_need_match: Optional[bool] = Field(
        default=None,
        description=(
            "True iff the predicted underlying_need matched the "
            "underlying need surfaced by sublimate.diagnose() at the "
            "next tick. None when no comparison is available "
            "(predicted=='none' and no urge fired)."
        ),
    )


def hourly_error(
    forecasted: ForecastedState, observed: FounderState
) -> HourlyError:
    """Pure-function reconciliation. Inputs are typed, outputs are typed."""
    distraction_err = abs(
        forecasted.predicted_distraction_min
        - observed.distraction_minutes_last_hour
    )
    deep_work_err = abs(
        forecasted.predicted_deep_work_min
        - observed.deep_work_minutes_last_hour
    )
    return HourlyError(
        distraction_abs_error=distraction_err,
        deep_work_abs_error=deep_work_err,
    )


def evaluate_intent(
    intent: Optional[str],
    *,
    use_llm: bool = False,
    llm_model: str = "claude-haiku-4-5",
    api_key: Optional[str] = None,
) -> IntentFlag:
    """Run the user's stated intent through Belief OS.

    Returns ``IntentFlag(flagged=True, mechanism=..., reason=...)`` iff
    the intent invokes a reasoning failure mode (default:
    ``survivorship_bias``, ``falsifiability``). Otherwise unflagged.

    LLM is OFF by default (deterministic keyword fallback). UAT scenario
    #4 uses a fixture-controlled mocked classification, so it doesn't
    need a real LLM call.
    """
    if not intent or not intent.strip():
        return IntentFlag(flagged=False)

    # Lazy import — keeps tests that don't need Belief OS fast.
    from agent.belief_os import check_decision_text

    decision = check_decision_text(
        intent,
        use_llm=use_llm,
        llm_model=llm_model,
        api_key=api_key,
    )
    return IntentFlag(
        flagged=decision.flag_for_review,
        mechanism=decision.classification.mechanism if decision.flag_for_review else None,
        reason=decision.flag_reason,
    )


__all__ = ["IntentFlag", "HourlyError", "hourly_error", "evaluate_intent"]
