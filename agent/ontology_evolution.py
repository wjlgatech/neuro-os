"""
Ontology Evolution.

Decides what to do with extractions that disagree with the current
ontology. Two entry points:

* ``evolve_from_extraction(pipeline_result, ontology)`` — the high-level
  contract used by the self-evolving loop. Accepts the rich pipeline
  result (``{knowledge, true_validation}``) and returns one of
  ``NO_ACTION``, ``PROPOSE_REFINEMENT``, or ``ESCALATE_REVIEW``.

* ``generate_refinement_from_consistency(knowledge, ontology)`` — a
  lower-level helper that builds a structured refinement proposal for a
  contradicting extraction.

Refinement proposals carry a ``source_quote`` derived from the
extraction's evidence so that downstream evaluation can score evidence
quality.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from agent.ingestion_pipeline import classify_evidence_strength
from agent.ontology_consistency import check_extraction_consistency


def _first_quote(knowledge: Dict[str, Any]) -> str:
    quotes = knowledge.get("evidence_quotes") or []
    if quotes:
        return str(quotes[0])
    if isinstance(knowledge.get("evidence"), dict):
        text = knowledge["evidence"].get("text")
        if text:
            return str(text)
    if knowledge.get("source_quote"):
        return str(knowledge["source_quote"])
    return ""


def _proposal_template(mechanism: str, claim: str, source_quote: str) -> Dict[str, Any]:
    return {
        "primitive_name": mechanism,
        "trigger": "ontology_contradiction",
        "proposed_change": (
            f"Refine the definition of {mechanism} to reconcile the new claim: "
            f"{claim or '(no claim text supplied)'}"
        ),
        "experience_probe": (
            f"Observe a real situation where {mechanism} predicts behavior."
        ),
        "experiment_design": (
            f"Run a controlled comparison where {mechanism} is the operative "
            "variable; predict the outcome before observing it."
        ),
        "failure_condition": (
            f"If outcome does not depend on {mechanism}, the refinement is rejected."
        ),
        "one_sentence_definition": claim or f"Refined definition of {mechanism}.",
        "felt_sense_bridge": f"Notice the felt sense that maps to {mechanism}.",
        "immediate_use_case": f"Apply {mechanism} reasoning to one decision today.",
        "repeat_protocol": "Repeat the probe across at least 3 independent contexts.",
        "measurement": "Score outcome quality on a 0-1 rubric.",
        "refinement_signal": "If predictions miss, refine the priors.",
        "version_delta": "Refinement triggered by contradiction.",
        "transfer_domains": ["brain", "AI", "life"],
        "transform_formats": ["sentence", "diagram", "code"],
        "source_quote": source_quote,
        "source_type": "extraction",
        "evidence_strength": classify_evidence_strength(source_quote),
        "contradictions_or_limits": (
            "Contradicts current ontology definition; refinement is provisional."
        ),
        "changed_files": [],
        "tests_pass": True,
        "rollback_available": True,
    }


def generate_refinement_from_consistency(
    knowledge: Dict[str, Any], ontology: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Generate a refinement proposal from an inconsistent extraction.

    Returns ``None`` if the extraction's mechanism is not in the ontology
    (no primitive to refine).
    """
    mechanism = knowledge.get("mechanism")
    if not mechanism or mechanism not in ontology.get("primitives", {}):
        return None
    claim = (
        knowledge.get("main_claim")
        or knowledge.get("core_mechanism")
        or knowledge.get("one_sentence_definition")
        or ""
    )
    source_quote = _first_quote(knowledge)
    return _proposal_template(mechanism, str(claim), str(source_quote))


def evolve_from_extraction(
    pipeline_result: Dict[str, Any], ontology: Dict[str, Any]
) -> Dict[str, Any]:
    """Decide what action to take based on a pipeline result.

    Parameters
    ----------
    pipeline_result : dict
        ``{knowledge, true_validation}`` as returned by ``run_pipeline``.
    ontology : dict
        Current ontology.

    Returns
    -------
    dict
        ``{action, reason, proposal}`` where ``action`` is one of
        ``NO_ACTION``, ``PROPOSE_REFINEMENT``, ``ESCALATE_REVIEW``, and
        ``proposal`` is the refinement dict (or ``None``).
    """
    knowledge = pipeline_result.get("knowledge", {}) or {}
    true_validation = pipeline_result.get("true_validation", {}) or {}
    true_score = float(true_validation.get("scores", {}).get("TRUE", 0.0))

    consistency = check_extraction_consistency(knowledge, ontology)
    decision = consistency.get("decision")

    if decision == "PASS":
        return {
            "action": "NO_ACTION",
            "reason": "consistent with ontology",
            "consistency": consistency,
            "proposal": None,
        }

    if decision == "REJECT" and "contradiction" in consistency.get("reason", "").lower():
        proposal = generate_refinement_from_consistency(knowledge, ontology)
        action = "PROPOSE_REFINEMENT" if true_score >= 0.75 else "ESCALATE_REVIEW"
        return {
            "action": action,
            "reason": consistency["reason"],
            "consistency": consistency,
            "proposal": proposal,
        }

    if decision == "REFINE":
        proposal = generate_refinement_from_consistency(knowledge, ontology)
        return {
            "action": "PROPOSE_REFINEMENT",
            "reason": consistency.get("reason", "missing required relations"),
            "consistency": consistency,
            "proposal": proposal,
        }

    return {
        "action": "NO_ACTION",
        "reason": consistency.get("reason", "rejected"),
        "consistency": consistency,
        "proposal": None,
    }


__all__ = ["generate_refinement_from_consistency", "evolve_from_extraction"]
