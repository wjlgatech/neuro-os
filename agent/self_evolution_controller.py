"""Self-evolution controller for Neuro-OS TRUE.

This module implements a safe OEC loop:
Observe -> Evaluate -> Control -> Validate.

It does not blindly rewrite the system. It proposes changes and validates them
against golden cases. A change is beneficial only if it improves objective
metrics without regressing TRUE acceptance quality.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Callable, Dict, Iterable, List, Optional

try:
    from ingestion_pipeline import run_pipeline
except ImportError:
    from .ingestion_pipeline import run_pipeline

try:
    from .patches import Patch
except ImportError:
    from agent.patches import Patch  # pragma: no cover


GoldenCase = Dict[str, str]
PipelineFn = Callable[[str], Dict[str, Any]]


GOLDEN_CASES: List[GoldenCase] = [
    {"text": "Dopamine neurons encode reward prediction error signals.", "expected_mechanism": "reinforcement_learning"},
    {"text": "Predictive coding minimizes sensory prediction error across cortical hierarchy.", "expected_mechanism": "predictive_processing"},
    {"text": "Neurons that fire together wire together through Hebbian synaptic plasticity.", "expected_mechanism": "hebbian_learning"},
    {"text": "Attention uses query key value gating to route relevant signals.", "expected_mechanism": "attention"},
    {"text": "The cortex builds hierarchy by compressing details into abstraction levels.", "expected_mechanism": "hierarchical_abstraction"},
]


@dataclass
class Observation:
    case_text: str
    expected_mechanism: str
    actual_mechanism: str
    decision: str
    true_score: float
    failed_dimensions: List[str]
    raw: Dict[str, Any]


@dataclass
class EvaluationReport:
    total: int
    correct: int
    accuracy: float
    accept_rate: float
    avg_true_score: float
    errors: List[Dict[str, str]]
    failed_dimension_counts: Dict[str, int]


@dataclass
class ControlProposal:
    change_id: str
    reason: str
    target_layer: str
    action: str
    risk: str
    patch: Optional[Patch] = None


@dataclass
class ValidationReport:
    before: EvaluationReport
    after: EvaluationReport
    beneficial: bool
    reason: str


def observe(cases: Iterable[GoldenCase], pipeline_fn: Optional[PipelineFn] = None) -> List[Observation]:
    """Run cases through the pipeline and capture structured observations."""
    if pipeline_fn is None:
        pipeline_fn = lambda text: run_pipeline(text)

    observations: List[Observation] = []
    for case in cases:
        result = pipeline_fn(case["text"])
        validation = result.get("true_validation", {})
        scores = validation.get("scores", {})
        observations.append(
            Observation(
                case_text=case["text"],
                expected_mechanism=case["expected_mechanism"],
                actual_mechanism=result.get("knowledge", {}).get("mechanism", "unknown"),
                decision=result.get("decision", "UNKNOWN"),
                true_score=float(scores.get("TRUE", 0.0)),
                failed_dimensions=list(validation.get("failed_dimensions", [])),
                raw=result,
            )
        )
    return observations


def evaluate_observations(observations: Iterable[Observation]) -> EvaluationReport:
    """Evaluate observations with explicit criteria."""
    obs = list(observations)
    total = len(obs)
    correct = sum(o.actual_mechanism == o.expected_mechanism for o in obs)
    accepted = sum(o.decision == "ACCEPT" for o in obs)
    avg_true = sum(o.true_score for o in obs) / total if total else 0.0

    errors = [
        {
            "text": o.case_text,
            "expected": o.expected_mechanism,
            "actual": o.actual_mechanism,
            "decision": o.decision,
        }
        for o in obs
        if o.actual_mechanism != o.expected_mechanism
    ]

    failed_counts: Dict[str, int] = {}
    for o in obs:
        for dim in o.failed_dimensions:
            failed_counts[dim] = failed_counts.get(dim, 0) + 1

    return EvaluationReport(
        total=total,
        correct=correct,
        accuracy=round(correct / total, 3) if total else 0.0,
        accept_rate=round(accepted / total, 3) if total else 0.0,
        avg_true_score=round(avg_true, 3),
        errors=errors,
        failed_dimension_counts=failed_counts,
    )


def propose_controls(report: EvaluationReport) -> List[ControlProposal]:
    """Convert observed failures into precise, bounded control proposals."""
    proposals: List[ControlProposal] = []

    for error in report.errors:
        text = error["text"].lower()
        if "reward prediction error" in text and error["actual"] == "predictive_processing":
            proposals.append(
                ControlProposal(
                    change_id="prioritize_reward_prediction_error",
                    reason="Reward prediction error is a reinforcement-learning cue, but generic prediction-error matching captured it first.",
                    target_layer="offline_extractor_rule_order",
                    action="Check dopamine/reward/TD-error cues before generic prediction-error cues.",
                    risk="May over-classify generic reward language as reinforcement learning.",
                    patch=Patch(
                        op="append_priority_rule",
                        payload={
                            "cue": "reward prediction error",
                            "mechanism": "reinforcement_learning",
                        },
                        target_path="agent/data/priority_rules.json",
                        description="ensure RL priority cue is present",
                    ),
                )
            )
        elif error["actual"] == "unknown":
            proposals.append(
                ControlProposal(
                    change_id="expand_keyword_coverage",
                    reason="Known golden mechanism was classified as unknown.",
                    target_layer="offline_extractor_keywords",
                    action=f"Add bounded cues for expected mechanism: {error['expected']}.",
                    risk="Keyword expansion can increase false positives.",
                )
            )

    for dimension, count in report.failed_dimension_counts.items():
        if count > 0:
            proposals.append(
                ControlProposal(
                    change_id=f"strengthen_{dimension}",
                    reason=f"{dimension} failed in {count} cases.",
                    target_layer="TRUE_extraction_schema_or_prompt",
                    action=f"Require more concrete evidence for {dimension} fields before acceptance.",
                    risk="May increase REFINE decisions and reduce accept rate.",
                )
            )

    seen = set()
    unique: List[ControlProposal] = []
    for proposal in proposals:
        if proposal.change_id not in seen:
            seen.add(proposal.change_id)
            unique.append(proposal)
    return unique


def validate_change(before: EvaluationReport, after: EvaluationReport) -> ValidationReport:
    """Validate whether a proposed change is beneficial."""
    accuracy_improved = after.accuracy > before.accuracy
    accuracy_same = after.accuracy == before.accuracy
    true_not_worse = after.avg_true_score >= before.avg_true_score
    accept_not_worse = after.accept_rate >= before.accept_rate

    beneficial = (
        (accuracy_improved and true_not_worse)
        or (accuracy_same and true_not_worse and accept_not_worse and len(after.errors) <= len(before.errors))
    )

    if beneficial:
        reason = "accepted: accuracy/TRUE metrics improved or stayed stable without new regressions"
    else:
        reason = "rejected: change did not improve accuracy or regressed TRUE/acceptance metrics"

    return ValidationReport(before=before, after=after, beneficial=beneficial, reason=reason)


def run_self_evolution(cases: Optional[List[GoldenCase]] = None, pipeline_fn: Optional[PipelineFn] = None) -> Dict[str, Any]:
    """Full OEC loop without unsafe auto-mutation."""
    cases = cases or GOLDEN_CASES
    observations = observe(cases, pipeline_fn=pipeline_fn)
    report = evaluate_observations(observations)
    proposals = propose_controls(report)

    status = "STABLE" if report.accuracy == 1.0 and not report.failed_dimension_counts else "CONTROL_PROPOSED"
    return {
        "status": status,
        "observation_count": len(observations),
        "evaluation": asdict(report),
        "control_proposals": [asdict(p) for p in proposals],
        "observations": [asdict(o) for o in observations],
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_self_evolution(), indent=2))
