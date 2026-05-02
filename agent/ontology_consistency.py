"""
Ontology Consistency Checker.

Evaluates whether an extracted piece of knowledge is consistent with the
existing ontology. Three checks:

1. **Existence:** the proposed mechanism must exist in the ontology.
2. **Contradiction:** the extracted claim must not negate the ontology
   definition (uses ``primitive_consistency_checker.detect_pair_contradiction``).
3. **Relations:** required relations from the ontology should be touched
   by the extracted knowledge; missing relations downgrade ``PASS`` to
   ``REFINE``.

The check inspects ``main_claim``, ``core_mechanism``, ``evidence_quotes``
and ``evidence.text``, so it works with both the rich pipeline output and
the minimal ``extract_mechanism`` output.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from agent.primitive_consistency_checker import (
    PrimitiveClaim,
    detect_pair_contradiction,
)


def _gather_claim_texts(knowledge: Dict[str, Any]) -> List[str]:
    """Collect every text field that could carry a claim or contradiction."""
    fields: List[str] = []
    for key in ("main_claim", "core_mechanism", "one_sentence_definition", "proposed_change"):
        value = knowledge.get(key)
        if isinstance(value, str) and value.strip():
            fields.append(value.strip())
    quotes = knowledge.get("evidence_quotes")
    if isinstance(quotes, Iterable) and not isinstance(quotes, (str, bytes)):
        for q in quotes:
            if isinstance(q, str) and q.strip():
                fields.append(q.strip())
    evidence = knowledge.get("evidence")
    if isinstance(evidence, dict):
        text = evidence.get("text")
        if isinstance(text, str) and text.strip():
            fields.append(text.strip())
    return fields


def _has_contradiction(mechanism: str, claim_text: str, definition: str) -> bool:
    """Return True if ``claim_text`` contradicts the ontology ``definition``."""
    if not definition or not claim_text:
        return False
    a = PrimitiveClaim(primitive_name=mechanism, claim=definition)
    b = PrimitiveClaim(primitive_name=f"{mechanism}_extracted", claim=claim_text)
    finding = detect_pair_contradiction(a, b)
    return finding is not None and finding.severity == "high"


def check_extraction_consistency(
    knowledge: Dict[str, Any], ontology: Dict[str, Any]
) -> Dict[str, str]:
    """Check consistency of an extracted mechanism against the ontology.

    Returns ``{decision, reason}`` where ``decision`` is ``PASS``, ``REFINE``
    or ``REJECT``.
    """
    mechanism = knowledge.get("mechanism")
    primitives = ontology.get("primitives", {})
    if not mechanism or mechanism == "unknown":
        return {"decision": "REJECT", "reason": "unknown mechanism"}
    if mechanism not in primitives:
        return {
            "decision": "REJECT",
            "reason": f"mechanism '{mechanism}' not in ontology",
        }

    primitive = primitives.get(mechanism, {}) or {}
    definition = primitive.get("definition") or ""
    claim_texts = _gather_claim_texts(knowledge)

    for claim_text in claim_texts:
        if _has_contradiction(mechanism, claim_text, definition):
            return {
                "decision": "REJECT",
                "reason": "contradiction with ontology definition",
            }

    # ``required_relations`` (separate from the informational ``relations``
    # field) is treated as a hard contract: every named relation must be
    # mentioned in the extracted claims for the check to PASS. When unset,
    # the relations field is informational only and does not gate.
    required_relations = primitive.get("required_relations", []) or []
    if required_relations:
        joined = " ".join(claim_texts).lower()
        missing = [
            rel
            for rel in required_relations
            if rel.replace("_", " ") not in joined and rel not in joined
        ]
        if missing:
            return {
                "decision": "REFINE",
                "reason": f"missing required relations: {', '.join(missing)}",
            }

    return {"decision": "PASS", "reason": "consistent"}


__all__ = ["check_extraction_consistency"]
