"""
Primitive Evolution Evaluator.

Scores proposed updates to neuroscience primitives along the TRUE axes
plus an explicit evidence dimension, and returns one of ``ACCEPT``,
``REFINE``, or ``REJECT`` together with the per-dimension scores.

Contract
--------
* Updates **must** include every required field listed in
  ``REQUIRED_FIELDS``. Missing any of them raises ``ValueError`` — the
  evaluator refuses to score incomplete proposals.

* If ``tests_pass`` is False or ``rollback_available`` is False, the
  decision is ``REJECT`` regardless of TRUE scores. Untestable or
  irreversible changes are never accepted.

* If every per-dimension score is at least ``ACCEPT_THRESHOLD`` (0.75),
  the decision is ``ACCEPT``. If at least one score reaches
  ``REFINE_THRESHOLD`` (0.5), the decision is ``REFINE``. Otherwise it
  is ``REJECT``.
"""
from __future__ import annotations

from typing import Any, Dict

REQUIRED_FIELDS: tuple[str, ...] = (
    "primitive_name",
    "proposed_change",
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
)

ACCEPT_THRESHOLD = 0.75
REFINE_THRESHOLD = 0.5


def _validate_required(update: Dict[str, Any]) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in update]
    if missing:
        raise ValueError(
            f"Update is missing required fields: {', '.join(missing)}"
        )


def _is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def score_experience(update: Dict[str, Any]) -> float:
    filled = sum(
        1
        for f in ("experience_probe", "experiment_design", "failure_condition")
        if _is_filled(update.get(f))
    )
    return round(filled / 3, 3)


def score_understanding_use(update: Dict[str, Any]) -> float:
    filled = sum(
        1
        for f in ("one_sentence_definition", "felt_sense_bridge", "immediate_use_case", "proposed_change")
        if _is_filled(update.get(f))
    )
    return round(filled / 4, 3)


def score_repeat_refine(update: Dict[str, Any]) -> float:
    filled = sum(
        1
        for f in ("repeat_protocol", "measurement", "refinement_signal", "version_delta")
        if _is_filled(update.get(f))
    )
    return round(filled / 4, 3)


def score_transfer_transform(update: Dict[str, Any]) -> float:
    domains = update.get("transfer_domains") or []
    formats = update.get("transform_formats") or []
    domain_score = 1.0 if len(domains) >= 2 else (0.5 if len(domains) == 1 else 0.0)
    format_score = 1.0 if len(formats) >= 3 else (0.5 if len(formats) >= 1 else 0.0)
    return round((domain_score + format_score) / 2, 3)


def score_evidence(update: Dict[str, Any]) -> float:
    if not _is_filled(update.get("source_quote")):
        return 0.0
    if not _is_filled(update.get("source_type")):
        return 0.0
    strength = (update.get("evidence_strength") or "").strip().lower()
    if strength == "strong":
        return 1.0
    if strength == "moderate":
        return 0.7
    if strength == "weak":
        return 0.3
    return 0.5


def evaluate_update_dict(update: Dict[str, Any]) -> Dict[str, Any]:
    """Score a primitive update and return the decision plus per-axis scores."""
    _validate_required(update)

    scores = {
        "E": score_experience(update),
        "U": score_understanding_use(update),
        "R": score_repeat_refine(update),
        "T": score_transfer_transform(update),
        "Evidence": score_evidence(update),
    }

    if not bool(update.get("tests_pass")):
        return {"decision": "REJECT", "scores": scores, "reason": "tests did not pass"}
    if not bool(update.get("rollback_available")):
        return {
            "decision": "REJECT",
            "scores": scores,
            "reason": "no rollback available",
        }

    if all(value >= ACCEPT_THRESHOLD for value in scores.values()):
        decision = "ACCEPT"
        reason = "all dimensions meet acceptance threshold"
    elif any(value >= REFINE_THRESHOLD for value in scores.values()):
        decision = "REFINE"
        reason = "some dimensions are borderline"
    else:
        decision = "REJECT"
        reason = "all dimensions below refine threshold"

    return {"decision": decision, "scores": scores, "reason": reason}


__all__ = [
    "REQUIRED_FIELDS",
    "ACCEPT_THRESHOLD",
    "REFINE_THRESHOLD",
    "evaluate_update_dict",
    "score_experience",
    "score_understanding_use",
    "score_repeat_refine",
    "score_transfer_transform",
    "score_evidence",
]
