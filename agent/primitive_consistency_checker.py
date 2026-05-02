"""Primitive consistency checker for Neuro-OS.

Detects possible contradictions across accepted primitives.

This is intentionally conservative: it flags contradictions for review rather
than declaring final truth. The goal is coherence control, not automated dogma.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Literal, Tuple

Severity = Literal["low", "medium", "high"]

NEGATION_PAIRS: List[Tuple[str, str]] = [
    ("requires", "does not require"),
    ("needs", "does not need"),
    ("depends on", "does not depend on"),
    ("increases", "decreases"),
    ("strengthens", "weakens"),
    ("selects", "does not select"),
    ("gates", "does not gate"),
    ("updates", "does not update"),
    ("predicts", "does not predict"),
    ("minimizes", "does not minimize"),
    ("error signal", "no error signal"),
    ("reward", "no reward"),
]

ABSOLUTE_MARKERS = ["always", "never", "only", "all", "none", "cannot", "must"]


@dataclass
class PrimitiveClaim:
    primitive_name: str
    claim: str
    source: str = "unknown"
    evidence_strength: str = "unknown"
    metadata: Dict[str, Any] | None = None


@dataclass
class ConsistencyFinding:
    status: str
    severity: Severity
    primitive_a: str
    primitive_b: str
    claim_a: str
    claim_b: str
    reason: str
    recommendation: str


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _has_absolute_language(text: str) -> bool:
    lowered = normalize(text)
    return any(marker in lowered.split() for marker in ABSOLUTE_MARKERS)


def _shared_keywords(a: str, b: str) -> List[str]:
    stop = {
        "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "by",
        "is", "are", "be", "as", "from", "that", "this", "it", "its", "can", "into",
    }
    aw = {w.strip(".,;:()[]") for w in normalize(a).split() if len(w) > 3 and w not in stop}
    bw = {w.strip(".,;:()[]") for w in normalize(b).split() if len(w) > 3 and w not in stop}
    return sorted(aw.intersection(bw))


def detect_pair_contradiction(a: PrimitiveClaim, b: PrimitiveClaim) -> ConsistencyFinding | None:
    claim_a = normalize(a.claim)
    claim_b = normalize(b.claim)
    shared = _shared_keywords(claim_a, claim_b)

    if not shared:
        return None

    for positive, negative in NEGATION_PAIRS:
        positive = normalize(positive)
        negative = normalize(negative)
        if positive in claim_a and negative in claim_b:
            return ConsistencyFinding(
                status="CONTRADICTION_REVIEW_REQUIRED",
                severity="high",
                primitive_a=a.primitive_name,
                primitive_b=b.primitive_name,
                claim_a=a.claim,
                claim_b=b.claim,
                reason=f"Opposing mechanism language detected: '{positive}' vs '{negative}' with shared terms {shared}.",
                recommendation="Do not merge both claims as-is. Add scope conditions, reconcile mechanisms, or mark one claim as rejected.",
            )
        if negative in claim_a and positive in claim_b:
            return ConsistencyFinding(
                status="CONTRADICTION_REVIEW_REQUIRED",
                severity="high",
                primitive_a=a.primitive_name,
                primitive_b=b.primitive_name,
                claim_a=a.claim,
                claim_b=b.claim,
                reason=f"Opposing mechanism language detected: '{negative}' vs '{positive}' with shared terms {shared}.",
                recommendation="Do not merge both claims as-is. Add scope conditions, reconcile mechanisms, or mark one claim as rejected.",
            )

    if _has_absolute_language(claim_a) and _has_absolute_language(claim_b) and len(shared) >= 3:
        return ConsistencyFinding(
            status="SCOPE_REVIEW_REQUIRED",
            severity="medium",
            primitive_a=a.primitive_name,
            primitive_b=b.primitive_name,
            claim_a=a.claim,
            claim_b=b.claim,
            reason=f"Both claims use absolute language and overlap on {shared}. They may need scope boundaries.",
            recommendation="Add conditions such as domain, timescale, mechanism level, or experimental context.",
        )

    return None


def check_primitive_consistency(claims: Iterable[PrimitiveClaim]) -> Dict[str, Any]:
    claim_list = list(claims)
    findings: List[ConsistencyFinding] = []

    for i in range(len(claim_list)):
        for j in range(i + 1, len(claim_list)):
            finding = detect_pair_contradiction(claim_list[i], claim_list[j])
            if finding:
                findings.append(finding)

    return {
        "status": "PASS" if not findings else "REVIEW_REQUIRED",
        "claim_count": len(claim_list),
        "finding_count": len(findings),
        "findings": [asdict(f) for f in findings],
    }


def claims_from_primitive_feedback(records: Iterable[Dict[str, Any]]) -> List[PrimitiveClaim]:
    claims: List[PrimitiveClaim] = []
    for record in records:
        update = record.get("update", {})
        primitive_name = update.get("primitive_name", "unknown")
        for field in ["one_sentence_definition", "proposed_change", "contradictions_or_limits"]:
            claim = update.get(field)
            if claim:
                claims.append(
                    PrimitiveClaim(
                        primitive_name=primitive_name,
                        claim=claim,
                        source=update.get("source_type", "unknown"),
                        evidence_strength=update.get("evidence_strength", "unknown"),
                        metadata={"field": field},
                    )
                )
    return claims


def check_feedback_consistency(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    return check_primitive_consistency(claims_from_primitive_feedback(records))


if __name__ == "__main__":
    import json

    demo = [
        PrimitiveClaim("attention", "Attention gates which signals control processing."),
        PrimitiveClaim("attention_alt", "Attention does not gate which signals control processing."),
    ]
    print(json.dumps(check_primitive_consistency(demo), indent=2))
