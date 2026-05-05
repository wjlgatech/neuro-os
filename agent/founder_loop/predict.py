"""
``predict.py`` — forecast next-hour state.

Mirrors ``agent/llm_extractors.py:make_anthropic_extractor`` with three
differences:

1. **Schema.** Returns a ``ForecastedState`` (next-hour distraction +
   deep work + urge type + underlying need + confidence + reasoning),
   not a ``PrimitiveClassification``.
2. **System prompt.** Names the underlying-need vocabulary so the model
   can route an entertainment urge to a *cause* (fatigue, novelty
   hunger, social, frustration, decision fatigue, embodied, etc.) —
   this is what makes sublimation work downstream.
3. **Backwards-compat label.** Carries an optional
   ``predicted_main_failure_mode`` string so UAT scenarios #1–#3 (which
   were written against the original brute-force vocabulary) still pin
   down the right routing.

Graceful degradation: any exception (missing API key, rate limit,
parse error) returns a deterministic fallback forecast with
``confidence='low'`` so the loop never crashes. The fallback uses the
recent trajectory averages — a baseline that's conservative but never
silently wrong.

Test injection: ``set_predict_fn(fn)`` replaces the LLM-backed forecaster
with a test stub. Used by every UAT fixture.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Literal, Optional

from pydantic import BaseModel, Field

from agent.founder_loop.state import (
    ForecastedState,
    FounderState,
)


# Internal predictor function. ``set_predict_fn`` replaces this for
# tests. ``None`` means "use the LLM-backed default" (which itself
# falls back to the trajectory baseline if no API key is set).
_predict_fn: Optional[Callable[[FounderState, Optional[str]], ForecastedState]] = None


# ---------------------------------------------------------------------------
# Public test-hook
# ---------------------------------------------------------------------------


def set_predict_fn(
    fn: Optional[Callable[[FounderState, Optional[str]], ForecastedState]],
) -> None:
    """Inject a custom predictor (used by UAT fixtures + unit tests)."""
    global _predict_fn
    _predict_fn = fn


def reset_predict_fn() -> None:
    """Drop any injected predictor; subsequent calls use the LLM/fallback."""
    global _predict_fn
    _predict_fn = None


# ---------------------------------------------------------------------------
# Trajectory baseline (no LLM required)
# ---------------------------------------------------------------------------


def trajectory_baseline(state: FounderState, intent: Optional[str] = None) -> ForecastedState:
    """Deterministic forecast from the rolling 7-day averages.

    Used when the LLM path is disabled or has errored. Predicts that the
    next hour will look like the 7-day average — the simplest defensible
    null model. ``predicted_underlying_need='none'`` because the
    baseline cannot actually diagnose; sublimation falls back to
    catalog-only when the predictor lands on 'none'.
    """
    distraction = state.distraction_7d_avg
    deep_work = state.deep_work_7d_avg
    if distraction is None:
        distraction = state.distraction_minutes_last_hour
    if deep_work is None:
        deep_work = state.deep_work_minutes_last_hour
    return ForecastedState(
        predicted_distraction_min=min(60.0, max(0.0, float(distraction))),
        predicted_deep_work_min=min(60.0, max(0.0, float(deep_work))),
        predicted_urge="none",
        predicted_underlying_need="none",
        predicted_main_failure_mode=None,
        confidence="low",
        reasoning="Trajectory baseline (rolling 7-day mean); no LLM available.",
    )


# ---------------------------------------------------------------------------
# LLM-backed predictor
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """You are the next-hour forecaster for founder_loop, a personal control loop that helps a founder sustain deep work without brute-force suppression.

Your job: read the current observed state of the founder + their stated intent + recent trajectory, and predict the *next hour*.

You produce four predictions:

1. ``predicted_distraction_min`` (0-60): minutes the founder will spend distracted in the next hour.
2. ``predicted_deep_work_min`` (0-60): minutes of focused deep work.
3. ``predicted_urge`` (one of: ``none``, ``entertainment``, ``escape``, ``novelty``): the urge most likely to fire.
4. ``predicted_underlying_need`` (one of: ``none``, ``fatigue``, ``novelty_hunger``, ``social``, ``frustration``, ``decision_fatigue``, ``embodied_hunger``, ``embodied_eye_strain``, ``earned_reward``, ``post_reward_fatigue``): the *underlying need* powering the urge. This is the load-bearing field — sublimation depends on naming the need correctly.

The philosophy: distraction is rarely a discipline failure. It is usually a counterfeit expression of a legitimate underlying need (the body wants rest; the mind wants real novelty; the social brain wants reciprocal contact; the stuck task wants to be externalized). Your job is to name the legitimate need so the loop can offer a constructive expression of it.

When predicting the underlying need, weigh:

* **fatigue**: low sleep_last_night_hours, deep work declining hour-over-hour, late afternoon
* **novelty_hunger**: high deep_work, low distraction, but rising context_switches — the user is grinding without real stimulation
* **social**: long last_outbound_message_age_h, weekend, low engagement
* **frustration**: flat output for 60+ min on a known-hard task
* **decision_fatigue**: many priorities, conflicting context, late afternoon
* **embodied_hunger**: time_since_last_meal_min > 240
* **embodied_eye_strain**: hours_continuous_screen > 4
* **earned_reward**: priority just evidenced, tank near full
* **post_reward_fatigue**: just consumed reward, residual urge is tiredness
* **none**: prediction is for a normal productive hour — no urge expected

Confidence: ``high`` only when at least two signals converge. ``low`` when the state is ambiguous.

Reasoning: one sentence, ≤ 240 chars, naming the most load-bearing signal.

You also output a backwards-compatible ``predicted_main_failure_mode`` (string) for legacy assertions. Use one of:
* ``youtube_drift`` — entertainment urge driven by fatigue or social need
* ``research_rabbit_hole`` — novelty-hunger urge dressed as work
* ``delusional_intent_capture`` — too-ambitious intent, decision fatigue likely
* ``low_energy_doomscroll`` — fatigue-driven scroll
* ``none`` — no failure mode predicted

OUTPUT FORMAT — REQUIRED:
A single JSON object matching the schema. No preamble.
"""


def _build_prediction_model():
    """Pydantic model used for ``client.messages.parse`` structured output."""
    UnderlyingNeedLabel = Literal[
        "none",
        "fatigue",
        "novelty_hunger",
        "social",
        "frustration",
        "decision_fatigue",
        "embodied_hunger",
        "embodied_eye_strain",
        "earned_reward",
        "post_reward_fatigue",
    ]
    UrgeLabel = Literal["none", "entertainment", "escape", "novelty"]
    Conf = Literal["low", "medium", "high"]

    class PredictionLLMOut(BaseModel):
        predicted_distraction_min: float = Field(ge=0.0, le=60.0)
        predicted_deep_work_min: float = Field(ge=0.0, le=60.0)
        predicted_urge: UrgeLabel
        predicted_underlying_need: UnderlyingNeedLabel
        predicted_main_failure_mode: Optional[str] = None
        confidence: Conf
        reasoning: str = Field(max_length=400)

    return PredictionLLMOut


def make_anthropic_predictor(
    *,
    model: str = "claude-haiku-4-5",
    api_key: Optional[str] = None,
    enable_caching: bool = True,
) -> Callable[[FounderState, Optional[str]], ForecastedState]:
    """Build an LLM-backed predictor.

    Returns a callable ``(state, intent) -> ForecastedState``. Any
    error (missing key, rate limit, parse) falls back to
    ``trajectory_baseline``.
    """
    try:
        import anthropic  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "anthropic is required for the LLM predictor. "
            'Install with: pip install -e ".[llm]"'
        ) from exc

    PredictionLLMOut = _build_prediction_model()

    import anthropic as _anthropic
    client = _anthropic.Anthropic(api_key=api_key) if api_key else _anthropic.Anthropic()

    if enable_caching:
        system_blocks = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        system_blocks = [{"type": "text", "text": SYSTEM_PROMPT}]

    def _predict(state: FounderState, intent: Optional[str]) -> ForecastedState:
        user_msg = (
            "Current observed state:\n"
            f"  timestamp: {state.timestamp.isoformat()}\n"
            f"  distraction_minutes_last_hour: {state.distraction_minutes_last_hour}\n"
            f"  deep_work_minutes_last_hour: {state.deep_work_minutes_last_hour}\n"
            f"  context_switches_last_hour: {state.context_switches_last_hour}\n"
            f"  sleep_last_night_hours: {state.sleep_last_night_hours}\n"
            f"  time_since_last_meal_min: {state.time_since_last_meal_min}\n"
            f"  hours_continuous_screen: {state.hours_continuous_screen}\n"
            f"  last_outbound_message_age_h: {state.last_outbound_message_age_h}\n"
            f"  distraction_7d_avg: {state.distraction_7d_avg}\n"
            f"  deep_work_7d_avg: {state.deep_work_7d_avg}\n"
            f"  day_kind: {state.day_kind}\n"
            f"  last_intent: {state.last_intent or '(none)'}\n"
            f"  user-stated intent for this hour: {intent or state.last_intent or '(none)'}\n\n"
            "Predict the next hour."
        )
        try:
            response = client.messages.parse(
                model=model,
                max_tokens=400,
                system=system_blocks,
                messages=[{"role": "user", "content": user_msg}],
                output_format=PredictionLLMOut,
            )
            parsed: PredictionLLMOut = response.parsed_output  # type: ignore[assignment]
            return ForecastedState(
                predicted_distraction_min=parsed.predicted_distraction_min,
                predicted_deep_work_min=parsed.predicted_deep_work_min,
                predicted_urge=parsed.predicted_urge,
                predicted_underlying_need=parsed.predicted_underlying_need,
                predicted_main_failure_mode=parsed.predicted_main_failure_mode,
                confidence=parsed.confidence,
                reasoning=parsed.reasoning,
            )
        except Exception:
            return trajectory_baseline(state, intent)

    return _predict


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def predict_next_hour(
    state: FounderState,
    intent: Optional[str] = None,
    *,
    use_llm: bool = False,
    llm_model: str = "claude-haiku-4-5",
    api_key: Optional[str] = None,
) -> ForecastedState:
    """Forecast the next hour.

    Routing:
    1. If a test predictor is injected via ``set_predict_fn``, use that.
    2. Else if ``use_llm=True``, build the LLM-backed predictor (with
       a one-shot cache) and call it.
    3. Else fall back to the trajectory baseline.
    """
    if _predict_fn is not None:
        return _predict_fn(state, intent)
    if use_llm:
        try:
            predictor = make_anthropic_predictor(
                model=llm_model, api_key=api_key, enable_caching=True
            )
            return predictor(state, intent)
        except Exception:
            return trajectory_baseline(state, intent)
    return trajectory_baseline(state, intent)


__all__ = [
    "predict_next_hour",
    "trajectory_baseline",
    "make_anthropic_predictor",
    "set_predict_fn",
    "reset_predict_fn",
    "SYSTEM_PROMPT",
]
