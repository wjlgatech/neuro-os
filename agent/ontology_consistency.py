"""Ontology consistency checks for Neuro-OS extraction.

This module enforces lightweight graph constraints after extraction:
- known mechanisms must exist in ontology
- canonical relations can be required for accepted primitives
- contradictions across primitive claims trigger REFINE/REJECT gates

It is deliberately conservative: it flags review conditions rather than pretending
to prove neuroscience truth automatically.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Literal, Set, Tuple

try:
    from agent.primitive_consistency_checker import PrimitiveClaim, check_primitive_consistency
except ImportError:  # pragma: no cover
    from primitive_consistency_checker import PrimitiveClaim, check_primitive_consistency

ConsistencyDecision = Literal["PASS", "REFINE", "REJECT"]

CANONICAL_REQUIRED_RELATIONS: Dict[str, Set[Tuple[str, str]]] = {
    "predictive_processing": {
        ("USES", "attention"),
        ("IMPLEMENTED_BY", "hebbian_learning"),
        ("BIASED_BY", "reinforcement_learning"),
        ("ORGANIZED_ACROSS", "hierarchical_abstraction"),
    },
    "hebbian_learning": {
        ("GENERALIZED_BY", "reinforcement_learning"),
    },
    "reinforcement_learning": {
        ("SCALED_BY", "hierarchical_abstraction"),
    },
}


@dataclass
class OntologyConsistencyReport:
    decision: ConsistencyDecision
    mechanism: str
    failed_constraints: List[str]
    warnings: List[str]
    relation_count: int
    contradiction_findings: List[Dict[str, Any]]


def _ontology_primitives(ontology: Dict[str, Any]) -> Dict[str, Any]:
    return ontology.get("primitives", {}) if ontology else {}


def _relations_for(ontology: Dict[str, Any], mechanism: str) -> Set[Tuple[str, str]]:
    primitive = _ontology_primitives(ontology).get(mechanism, {})
    relations = primitive.get("relations", [])
    out: Set[Tuple[str, str]] = set()
    for relation in relations:
        rel = str(relation.get("relation", "")).strip()
        target = str(relation.get("target", "")).strip()
        if rel and target:
            out.add((rel, target))
    return out


def _claims_for_mechanism(ontology: Dict[str, Any], mechanism: str, extracted: Dict[str, Any]) -> List[PrimitiveClaim]:
    claims: List[PrimitiveClaim] = []
    primitive = _ontology_primitives(ontology).get(mechanism, {})
    definition = primitive.get("definition")
    if definition:
        claims.append(PrimitiveClaim(mechanism, definition, source="ontology"))
    for field in ["core_mechanism", "main_claim", "connection_to_ai", "connection_to_human_thinking"]:
        value = extracted.get(field)
        if value and str(value).upper() != "UNKNOWN":
            claims.append(PrimitiveClaim(mechanism, str(value), source="extraction", metadata={"field": field}))
    return claims


def check_extraction_consistency(extracted: Dict[str, Any], ontology: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
    """Check extracted knowledge against ontology graph and primitive claims.

    Args:
        extracted: `knowledge` dict from ingestion_pipeline.run_pipeline.
        ontology: ontology dict from ontology_builder/load_ontology.
        strict: if True, missing canonical relations cause REJECT instead of REFINE.
    """
    mechanism = extracted.get("mechanism", "unknown")
    failed: List[str] = []
    warnings: List[str] = []
    primitives = _ontology_primitives(ontology)

    if mechanism == "unknown":
        return asdict(OntologyConsistencyReport("REJECT", mechanism, ["unknown mechanism cannot be ontology-consistent"], [], 0, []))

    if mechanism not in primitives:
        return asdict(OntologyConsistencyReport("REJECT", mechanism, [f"mechanism not found in ontology: {mechanism}"], [], 0, []))

    relation_set = _relations_for(ontology, mechanism)
    required = CANONICAL_REQUIRED_RELATIONS.get(mechanism, set())
    missing_required = sorted(required.difference(relation_set))
    for rel, target in missing_required:
        failed.append(f"missing required relation: {mechanism} --{rel}--> {target}")

    # Internal contradiction check: ontology definition vs extraction claims.
    claims = _claims_for_mechanism(ontology, mechanism, extracted)
    contradiction_report = check_primitive_consistency(claims)
    findings = contradiction_report.get("findings", [])
    high_findings = [f for f in findings if f.get("severity") == "high"]
    if high_findings:
        failed.append("high-severity contradiction between extraction and ontology definition")
    elif findings:
        warnings.append("scope review recommended between extraction and ontology definition")

    if high_findings:
        decision: ConsistencyDecision = "REJECT"
    elif failed and strict:
        decision = "REJECT"
    elif failed or warnings:
        decision = "REFINE"
    else:
        decision = "PASS"

    return asdict(OntologyConsistencyReport(decision, mechanism, failed, warnings, len(relation_set), findings))


def apply_consistency_gate(pipeline_result: Dict[str, Any], ontology: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
    """Attach ontology consistency to a pipeline result and update decision if needed."""
    extracted = pipeline_result.get("knowledge", {})
    consistency = check_extraction_consistency(extracted, ontology, strict=strict)
    output = {**pipeline_result, "ontology_consistency": consistency}

    if consistency["decision"] == "REJECT":
        output["decision"] = "REJECT"
    elif consistency["decision"] == "REFINE" and output.get("decision") == "ACCEPT":
        output["decision"] = "REFINE"
    return output


if __name__ == "__main__":
    import json

    demo_ontology = {
        "primitives": {
            "attention": {"definition": "Attention gates signals.", "relations": []},
        }
    }
    demo = {"mechanism": "attention", "core_mechanism": "Attention does not gate signals."}
    print(json.dumps(check_extraction_consistency(demo, demo_ontology), indent=2))
