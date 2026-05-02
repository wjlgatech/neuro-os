"""Primitive evolution evaluator for Neuro-OS.

Evaluates whether a proposed primitive update should be ACCEPTED, REFINE, or
REJECTED using TRUE + evidence + OEC criteria.

This module is intentionally deterministic and schema-like. It does not decide
truth by tone or fluency. It decides by testability, usability, repeatability,
transferability, evidence quality, and controlled change safety.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal

Decision = Literal["ACCEPT", "REFINE", "REJECT"]

REQUIRED_TRUE_FIELDS = [
    "experience_probe",
    "experiment_design",
    "failure_condition",
    "one_sentence_definition",
    "felt_sense_bridge",
    "immediate_use_case",
    "repeat_protocol",
    "measurement",
    "refinement_signal",
    "version_delta",
    "transfer_domains",
    "transform_formats",
    "source_quote",
    "source_type",
    "evidence_strength",
    "contradictions_or_limits",
    "changed_files",
    "tests_pass",
    "rollback_available",
]

STRONG_SOURCE_TYPES = {"paper", "book", "repo", "review", "official_docs"}
REQUIRED_TRANSFER_DOMAINS = {"brain", "AI"}
REQUIRED_TRANSFORM_COUNT = 3


@dataclass
class PrimitiveUpdate:
    primitive_name: str
    proposed_change: str
    experience_probe: str
    experiment_design: str
    failure_condition: str
    one_sentence_definition: str
    felt_sense_bridge: str
    immediate_use_case: str
    repeat_protocol: str
    measurement: str
    refinement_signal: str
    version_delta: str
    transfer_domains: List[str]
    transform_formats: List[str]
    source_quote: str
    source_type: str
    evidence_strength: str
    contradictions_or_limits: str
    changed_files: List[str]
    tests_pass: bool
    rollback_available: bool
    no_new_regressions: bool = True
    true_before: float = 0.0
    true_after: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoreBreakdown:
    E_experienceable_experimentable: float
    U_understandable_usable: float
    R_repeatable_refinable: float
    T_transferable_transformable: float
    evidence_quality: float
    OEC_control: float
    final: float


@dataclass
class PrimitiveEvolutionDecision:
    decision: Decision
    scores: ScoreBreakdown
    failed_criteria: List[str]
    required_refinements: List[str]
    update: Dict[str, Any]


def _known(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().upper() != "UNKNOWN"
    if isinstance(value, list):
        return bool(value) and all(_known(v) for v in value)
    if isinstance(value, bool):
        return value
    return value is not None


def _contains_failure_language(text: str) -> bool:
    lower = text.lower()
    return any(word in lower for word in ["fail", "weaken", "falsify", "reject", "no difference", "regress"])


def score_experience(update: PrimitiveUpdate) -> float:
    score = 0.0
    if _known(update.experience_probe):
        score += 0.3
    if _known(update.experiment_design):
        score += 0.35
    if _known(update.failure_condition) and _contains_failure_language(update.failure_condition):
        score += 0.35
    return round(score, 3)


def score_understanding_use(update: PrimitiveUpdate) -> float:
    score = 0.0
    definition_words = len(update.one_sentence_definition.split())
    if _known(update.one_sentence_definition) and definition_words <= 30:
        score += 0.3
    if _known(update.felt_sense_bridge):
        score += 0.3
    if _known(update.immediate_use_case):
        score += 0.4
    return round(score, 3)


def score_repeat_refine(update: PrimitiveUpdate) -> float:
    score = 0.0
    if _known(update.repeat_protocol):
        score += 0.25
    if _known(update.measurement):
        score += 0.25
    if _known(update.refinement_signal):
        score += 0.25
    if _known(update.version_delta):
        score += 0.25
    return round(score, 3)


def score_transfer_transform(update: PrimitiveUpdate) -> float:
    domains = {d.strip() for d in update.transfer_domains}
    score = 0.0
    if len(domains) >= 2:
        score += 0.3
    if REQUIRED_TRANSFER_DOMAINS.issubset(domains):
        score += 0.25
    if len(update.transform_formats) >= REQUIRED_TRANSFORM_COUNT:
        score += 0.3
    if _known(update.transform_formats):
        score += 0.15
    return round(min(score, 1.0), 3)


def score_evidence(update: PrimitiveUpdate) -> float:
    score = 0.0
    if _known(update.source_quote):
        score += 0.25
    if update.source_type in STRONG_SOURCE_TYPES:
        score += 0.25
    elif _known(update.source_type):
        score += 0.1
    if update.evidence_strength.lower() in {"strong", "high", "multiple_sources"}:
        score += 0.25
    elif _known(update.evidence_strength):
        score += 0.1
    if _known(update.contradictions_or_limits):
        score += 0.25
    return round(min(score, 1.0), 3)


def score_oec_control(update: PrimitiveUpdate) -> float:
    score = 0.0
    if _known(update.changed_files):
        score += 0.2
    if update.tests_pass:
        score += 0.25
    if update.rollback_available:
        score += 0.2
    if update.no_new_regressions:
        score += 0.2
    if update.true_after >= update.true_before:
        score += 0.15
    return round(score, 3)


def score_update(update: PrimitiveUpdate) -> ScoreBreakdown:
    e = score_experience(update)
    u = score_understanding_use(update)
    r = score_repeat_refine(update)
    t = score_transfer_transform(update)
    evidence = score_evidence(update)
    oec = score_oec_control(update)
    final = round((e + u + r + t + evidence + oec) / 6, 3)
    return ScoreBreakdown(e, u, r, t, evidence, oec, final)


def evaluate_primitive_update(update: PrimitiveUpdate) -> PrimitiveEvolutionDecision:
    scores = score_update(update)
    thresholds = {
        "E_experienceable_experimentable": 0.8,
        "U_understandable_usable": 0.8,
        "R_repeatable_refinable": 0.75,
        "T_transferable_transformable": 0.8,
        "evidence_quality": 0.75,
        "OEC_control": 0.85,
    }

    score_dict = asdict(scores)
    failed = [name for name, threshold in thresholds.items() if score_dict[name] < threshold]

    hard_failures: List[str] = []
    if not update.tests_pass:
        hard_failures.append("tests_pass is false")
    if not update.rollback_available:
        hard_failures.append("rollback_available is false")
    if not update.no_new_regressions:
        hard_failures.append("no_new_regressions is false")
    if update.true_after < update.true_before:
        hard_failures.append("TRUE score regressed")

    failed_criteria = failed + hard_failures

    refinements = []
    for criterion in failed:
        if criterion.startswith("E_"):
            refinements.append("Add a concrete experience probe, experiment design, and falsifiable failure condition.")
        elif criterion.startswith("U_"):
            refinements.append("Make the primitive understandable and usable within one immediate real situation.")
        elif criterion.startswith("R_"):
            refinements.append("Add repeat protocol, measurement, refinement signal, and version delta.")
        elif criterion.startswith("T_"):
            refinements.append("Map to brain + AI and transform into at least three formats.")
        elif criterion == "evidence_quality":
            refinements.append("Add stronger source quote, source type, evidence strength, and limitations.")
        elif criterion == "OEC_control":
            refinements.append("Add tests, rollback path, changed files, and no-regression validation.")

    if hard_failures or scores.final < 0.65:
        decision: Decision = "REJECT"
    elif failed_criteria:
        decision = "REFINE"
    else:
        decision = "ACCEPT"

    return PrimitiveEvolutionDecision(
        decision=decision,
        scores=scores,
        failed_criteria=failed_criteria,
        required_refinements=sorted(set(refinements)),
        update=asdict(update),
    )


def evaluate_update_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    missing = [field for field in REQUIRED_TRUE_FIELDS if field not in data]
    if missing:
        raise ValueError(f"Missing required primitive update fields: {missing}")
    update = PrimitiveUpdate(**data)
    return asdict(evaluate_primitive_update(update))


if __name__ == "__main__":
    example = PrimitiveUpdate(
        primitive_name="attention",
        proposed_change="Attention gates which prediction errors influence downstream control.",
        experience_probe="Notice which signal controls your next action during a distraction.",
        experiment_design="Compare recall after focused input versus distracted input.",
        failure_condition="If recall shows no difference, this weakens the claim.",
        one_sentence_definition="Attention selects which signals control processing and suppresses the rest.",
        felt_sense_bridge="Focus feels like one signal getting louder while alternatives get quieter.",
        immediate_use_case="Before a meeting, choose the one signal that should guide your attention.",
        repeat_protocol="Repeat in three meetings and compare recall and action quality.",
        measurement="Recall score and number of action-relevant details captured.",
        refinement_signal="If recall does not improve, refine the attention cue or reject the update.",
        version_delta="Adds falsifiable recall test to attention primitive.",
        transfer_domains=["brain", "AI", "personal practice"],
        transform_formats=["sentence", "diagram", "equation", "practice"],
        source_quote="Attention routes relevant signals while suppressing irrelevant ones.",
        source_type="paper",
        evidence_strength="strong",
        contradictions_or_limits="Attention can be captured by saliency and miss weak but important signals.",
        changed_files=["primitives/attention.md"],
        tests_pass=True,
        rollback_available=True,
        no_new_regressions=True,
        true_before=0.82,
        true_after=0.91,
    )
    import json

    print(json.dumps(asdict(evaluate_primitive_update(example)), indent=2))
