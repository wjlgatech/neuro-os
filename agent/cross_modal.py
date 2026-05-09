"""
Cross-modal evaluation (Lane 3).

Runs the SAME decision text through K independent scorers (typically
3 different LLMs with different failure modes — Garry Tan's pattern:
"Opus catches precision errors, GPT catches missing context, DeepSeek
catches generic-reading"). Returns a typed ``CrossModalEval`` with
per-scorer verdicts, a disagreement score, and a consensus verdict.

The point of fanning out: one model has a single failure surface;
three models with different failure surfaces converge on truth.
Disagreement above a threshold is a STRONGER signal than any single
model's flag — it means the decision text is genuinely ambiguous,
which is exactly when human review is most useful.

## Cost discipline

This module is the SHAPE — it accepts injectable scorer callables.
The production wiring (3 live Anthropic calls in parallel, with
Sonnet+Haiku+Opus typically) lives in a follow-up commit. v0 ships:
* the abstraction (CrossModalEval schema + run_cross_modal_check)
* a fixture-injection helper (make_fixture_scorers) for tests
* a default-scorer factory (make_default_scorers) that wires K calls
  to the existing single-model ``check_decision_text``

The fixture pattern mirrors Lane 1 (gbrain_adapter): tests inject
deterministic scorers; production wiring is interchangeable.
"""
from __future__ import annotations

from typing import Callable, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# A scorer takes the decision text and returns a triple:
#   (flag: bool, primitive: Optional[str], reason: Optional[str])
# Where ``primitive`` is the named failure-mode the scorer matched
# (e.g. "narrative_following", "social_proof_following"), and ``reason``
# is a short human-readable explanation. Both can be None if the
# scorer didn't flag anything.
ScorerResult = tuple[bool, Optional[str], Optional[str]]
Scorer = Callable[[str], ScorerResult]


# Disagreement above this fraction → the consensus verdict carries an
# explicit "low_confidence" warning. 0.34 means: any time at least 1 of
# 3 scorers disagrees with the others, the user is warned.
DISAGREEMENT_WARNING_THRESHOLD = 0.34


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


ConsensusVerdict = Literal[
    "no_flag_unanimous",      # K-of-K say no flag
    "no_flag_majority",       # majority say no flag, minority flags
    "flag_majority",          # majority flags, minority says no flag
    "flag_unanimous",          # K-of-K flag
    "tied",                    # exact tie (only meaningful with even K)
]


class ScorerVerdict(BaseModel):
    """One scorer's vote on a single decision."""

    model_config = ConfigDict(frozen=True)

    scorer_label: str = Field(
        min_length=1,
        max_length=64,
        description="Short label identifying the scorer (e.g. "
                    "'haiku-4-5', 'sonnet-4-6', 'opus-4-7').",
    )
    flagged: bool
    primitive: Optional[str] = Field(default=None, max_length=64)
    reason: Optional[str] = Field(default=None, max_length=600)


class CrossModalEval(BaseModel):
    """Result of fanning out one decision through K scorers.

    Frozen — the eval is an immutable record of what each scorer said
    at evaluation time. Subsequent re-checks produce new CrossModalEval
    rows; the original is never mutated.
    """

    model_config = ConfigDict(frozen=True)

    decision_text_excerpt: str = Field(
        min_length=1,
        max_length=600,
        description="First N chars of the decision text being evaluated.",
    )
    verdicts: List[ScorerVerdict] = Field(
        min_length=1,
        max_length=10,
        description="One per scorer, in invocation order.",
    )

    # Aggregates (computed by run_cross_modal_check; pinned here as
    # fields so consumers don't have to re-compute):
    flag_count: int = Field(ge=0, description="Number of scorers that flagged.")
    total_count: int = Field(ge=1, description="K — the number of scorers.")
    disagreement_score: float = Field(
        ge=0.0, le=1.0,
        description="0.0 = unanimous; 1.0 = max possible disagreement. "
                    "Computed as min(flag_count, total_count - flag_count) / "
                    "(total_count / 2).",
    )
    consensus_verdict: ConsensusVerdict
    consensus_flagged: bool = Field(
        description="True iff the majority flagged. For tied verdicts this "
                    "is False (conservative — ambiguous decisions should "
                    "default to NOT blocking the user)."
    )
    low_confidence_warning: bool = Field(
        description="True iff disagreement_score >= "
                    "DISAGREEMENT_WARNING_THRESHOLD. The downstream caller "
                    "should surface this to the user — disagreement is a "
                    "stronger 'pause and look' signal than any single flag."
    )


# ---------------------------------------------------------------------------
# The fan-out
# ---------------------------------------------------------------------------


def run_cross_modal_check(
    decision_text: str,
    *,
    scorers: List[tuple[str, Scorer]],
) -> CrossModalEval:
    """Run all ``scorers`` against ``decision_text`` and return a
    typed CrossModalEval.

    ``scorers`` is a list of ``(label, callable)`` tuples. The labels
    show up in the per-scorer verdicts so the user can see WHICH model
    flagged or didn't. v0 runs them sequentially; parallel execution
    is a follow-up (the abstraction allows it without changing this
    contract).
    """
    if not scorers:
        raise ValueError("run_cross_modal_check: at least one scorer required")

    verdicts: List[ScorerVerdict] = []
    for label, scorer in scorers:
        flagged, primitive, reason = scorer(decision_text)
        verdicts.append(ScorerVerdict(
            scorer_label=label,
            flagged=bool(flagged),
            primitive=primitive,
            reason=reason,
        ))

    flag_count = sum(1 for v in verdicts if v.flagged)
    total = len(verdicts)
    disagreement_score = _disagreement(flag_count, total)
    consensus_verdict = _consensus_verdict(flag_count, total)
    consensus_flagged = (flag_count > total - flag_count)
    low_confidence = disagreement_score >= DISAGREEMENT_WARNING_THRESHOLD

    return CrossModalEval(
        decision_text_excerpt=decision_text[:600],
        verdicts=verdicts,
        flag_count=flag_count,
        total_count=total,
        disagreement_score=disagreement_score,
        consensus_verdict=consensus_verdict,
        consensus_flagged=consensus_flagged,
        low_confidence_warning=low_confidence,
    )


def _disagreement(flag_count: int, total: int) -> float:
    """Disagreement = the fraction of scorers in the MINORITY camp,
    normalized by ``total/2`` so a 50/50 split scores 1.0."""
    if total <= 1:
        return 0.0
    minority = min(flag_count, total - flag_count)
    return min(minority / (total / 2), 1.0)


def _consensus_verdict(flag_count: int, total: int) -> ConsensusVerdict:
    no_flag = total - flag_count
    if flag_count == total:
        return "flag_unanimous"
    if no_flag == total:
        return "no_flag_unanimous"
    if flag_count == no_flag:
        return "tied"
    if flag_count > no_flag:
        return "flag_majority"
    return "no_flag_majority"


# ---------------------------------------------------------------------------
# Scorer factories
# ---------------------------------------------------------------------------


def make_default_scorers(
    *,
    use_llm: bool = False,
    api_key: Optional[str] = None,
) -> List[tuple[str, Scorer]]:
    """Build the default 3-scorer panel (Haiku / Sonnet / Opus).

    With ``use_llm=False`` (default) all 3 scorers fall back to the
    same heuristic primitive matcher; the panel will agree on
    everything (disagreement_score=0.0). That is intentionally
    deterministic for tests/CI; the value of cross-modal arrives only
    once ``use_llm=True`` and the scorers DO have different failure
    modes.

    Production: ``use_llm=True`` calls 3 different Anthropic models
    via the existing ``check_decision_text``; the per-call cost is
    Haiku-cheap × 3 (≈ $0.003 / decision today).
    """
    from agent.belief_os import check_decision_text

    def _make(label: str, model: str) -> tuple[str, Scorer]:
        def _score(text: str) -> ScorerResult:
            result = check_decision_text(
                text, use_llm=use_llm, llm_model=model, api_key=api_key,
            )
            primitive = getattr(result, "classification", None)
            primitive_name: Optional[str] = None
            if primitive is not None:
                primitive_name = getattr(primitive, "primitive", None)
            return (
                bool(result.flag_for_review),
                primitive_name,
                result.flag_reason,
            )
        return (label, _score)

    return [
        _make("haiku-4-5", "claude-haiku-4-5"),
        _make("sonnet-4-6", "claude-sonnet-4-6"),
        _make("opus-4-7", "claude-opus-4-7"),
    ]


def make_fixture_scorers(
    fixed_results: List[ScorerResult],
    *,
    labels: Optional[List[str]] = None,
) -> List[tuple[str, Scorer]]:
    """Test helper: build K scorers each returning a pre-canned result.

    Useful for pinning every consensus / disagreement code path
    deterministically without needing the LLM or even the heuristic
    matcher.
    """
    if labels is None:
        labels = [f"fixture-{i}" for i in range(len(fixed_results))]
    if len(labels) != len(fixed_results):
        raise ValueError(
            f"labels and fixed_results must be same length "
            f"({len(labels)} vs {len(fixed_results)})"
        )

    def _make(result: ScorerResult) -> Scorer:
        def _score(_text: str) -> ScorerResult:
            return result
        return _score

    return [(label, _make(r)) for label, r in zip(labels, fixed_results)]


__all__ = [
    "DISAGREEMENT_WARNING_THRESHOLD",
    "ConsensusVerdict",
    "ScorerVerdict",
    "CrossModalEval",
    "Scorer",
    "ScorerResult",
    "run_cross_modal_check",
    "make_default_scorers",
    "make_fixture_scorers",
]
