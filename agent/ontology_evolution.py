"""Ontology evolution from validated contradictions.

Research basis:
- Truth maintenance / belief revision: contradictions should expose causes and
  trigger controlled knowledge-base revision.
- Ontology evolution: inconsistency can be handled by repair, multi-version
  reasoning, or reasoning under inconsistency.

Neuro-OS policy:
- Contradictions DO NOT directly overwrite primitives.
- Contradictions generate primitive refinement proposals.
- Refinement proposals must pass primitive_evolution_evaluator before becoming
  accepted feedback or ontology updates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Literal

try:
    from agent.ontology_consistency import check_extraction_consistency
except ImportError:  # pragma: no cover
    from ontology_consistency import check_extraction_consistency

EvolutionAction = Literal["NO_ACTION", "PROPOSE_REFINEMENT", "ESCALATE_REVIEW"]


@dataclass
class OntologyRefinementProposal:
    primitive_name: str
    trigger: str
    contradiction_reason: str
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
    no_new_regressions: bool
    true_before: float
    true_after: float
    metadata: Dict[str, Any]


def _safe_text(value: Any, fallback: str = "UNKNOWN") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def generate_refinement_from_consistency(
    extracted: Dict[str, Any],
    consistency_report: Dict[str, Any],
    true_before: float = 0.0,
    true_after: float = 0.0,
) -> Dict[str, Any]:
    """Convert a contradiction/consistency failure into a primitive update proposal."""
    mechanism = _safe_text(extracted.get("mechanism"), "unknown")
    findings = consistency_report.get("contradiction_findings", [])
    failed = consistency_report.get("failed_constraints", [])
    warnings = consistency_report.get("warnings", [])

    reason_parts: List[str] = []
    if findings:
        reason_parts.extend([_safe_text(f.get("reason")) for f in findings])
    if failed:
        reason_parts.extend(failed)
    if warnings:
        reason_parts.extend(warnings)
    reason = "; ".join(reason_parts) if reason_parts else "Ontology consistency review required."

    proposed_change = (
        f"Refine {mechanism} to resolve ontology consistency issue: {reason}. "
        "Add explicit scope conditions instead of silently accepting both claims."
    )

    proposal = OntologyRefinementProposal(
        primitive_name=mechanism,
        trigger="ontology_contradiction" if findings else "ontology_consistency_gap",
        contradiction_reason=reason,
        proposed_change=proposed_change,
        experience_probe="Observe a concrete case where the conflicting claims would predict different behavior.",
        experiment_design="Design an A/B or counterexample test that distinguishes the conflicting mechanism claims.",
        failure_condition="If both claims make identical predictions, the contradiction weakens and should be re-scoped rather than rejected.",
        one_sentence_definition=_safe_text(extracted.get("core_mechanism")),
        felt_sense_bridge=_safe_text(extracted.get("connection_to_human_thinking")),
        immediate_use_case="Use the refined primitive to decide whether the new extraction should be ACCEPT, REFINE, or REJECT.",
        repeat_protocol="Run the conflicting claims across at least three source examples and compare decisions.",
        measurement="Count contradictions resolved without lowering TRUE score or creating new regressions.",
        refinement_signal="If contradictions repeat, split the primitive scope by domain, timescale, or mechanism level.",
        version_delta=f"Adds contradiction-triggered refinement for {mechanism}.",
        transfer_domains=["brain", "AI", "personal practice"],
        transform_formats=["sentence", "experiment", "graph", "practice"],
        source_quote=_safe_text(extracted.get("evidence_quotes", [""])[0] if extracted.get("evidence_quotes") else extracted.get("main_claim")),
        source_type=_safe_text(extracted.get("source_type"), "unknown"),
        evidence_strength="medium" if findings else "weak",
        contradictions_or_limits=reason,
        changed_files=[f"primitives/{mechanism}.md", "parsed/ontology.json"],
        tests_pass=False,
        rollback_available=True,
        no_new_regressions=False,
        true_before=true_before,
        true_after=true_after,
        metadata={"consistency_report": consistency_report, "extracted": extracted},
    )
    return asdict(proposal)


def evolve_from_extraction(
    pipeline_result: Dict[str, Any],
    ontology: Dict[str, Any],
    strict: bool = False,
) -> Dict[str, Any]:
    """Run consistency check and return an ontology-evolution action."""
    extracted = pipeline_result.get("knowledge", {})
    true_scores = pipeline_result.get("true_validation", {}).get("scores", {})
    consistency = check_extraction_consistency(extracted, ontology, strict=strict)

    if consistency["decision"] == "PASS":
        return {
            "action": "NO_ACTION",
            "reason": "Extraction is ontology-consistent.",
            "consistency": consistency,
            "proposal": None,
        }

    proposal = generate_refinement_from_consistency(
        extracted,
        consistency,
        true_before=float(true_scores.get("TRUE", 0.0)),
        true_after=float(true_scores.get("TRUE", 0.0)),
    )

    action: EvolutionAction = "ESCALATE_REVIEW" if consistency["decision"] == "REJECT" else "PROPOSE_REFINEMENT"
    return {
        "action": action,
        "reason": "Contradiction or graph constraint failure produced a refinement proposal.",
        "consistency": consistency,
        "proposal": proposal,
    }


if __name__ == "__main__":
    import json

    ontology = {"primitives": {"attention": {"definition": "Attention gates signals.", "relations": []}}}
    pipeline_result = {
        "knowledge": {
            "mechanism": "attention",
            "core_mechanism": "Attention does not gate signals.",
            "main_claim": "Attention does not gate signals.",
            "connection_to_human_thinking": "Focus changes which signal feels dominant.",
            "evidence_quotes": ["Attention does not gate signals."],
            "source_type": "paper",
        },
        "true_validation": {"scores": {"TRUE": 0.8}},
    }
    print(json.dumps(evolve_from_extraction(pipeline_result, ontology), indent=2))
