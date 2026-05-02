"""
Neuro-OS TRUE Validation Loop.

Truth is not information. Truth is survivable, usable, repeatable transformation.

Pipeline: source -> typed extraction -> TRUE validation -> ACCEPT / REJECT / REFINE

TRUE:
E = Experienceable + Experimentable
U = Understandable + Usable
R = Repeatable + Refinable
T = Transferable + Transformable
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal

MechanismName = Literal[
    "predictive_processing",
    "hebbian_learning",
    "reinforcement_learning",
    "attention",
    "hierarchical_abstraction",
    "unknown",
]
Decision = Literal["ACCEPT", "REJECT", "REFINE"]


@dataclass
class ExtractedKnowledge:
    title: str
    source_type: str
    source_url: str
    mechanism: MechanismName
    core_mechanism: str
    key_equation: str
    main_claim: str
    experience_probe: str
    experiment_design: str
    felt_sense_bridge: str
    immediate_use: str
    repeat_protocol: str
    refinement_signal: str
    transfer_domains: List[str]
    transform_formats: List[str]
    failure_modes: List[str]
    connection_to_ai: str
    connection_to_human_thinking: str
    confidence: float
    evidence_quotes: List[str] = field(default_factory=list)


REQUIRED_FIELDS = list(ExtractedKnowledge.__dataclass_fields__.keys())

EXTRACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "source_type": {"type": "string", "enum": ["paper", "blog", "repo", "book", "unknown"]},
        "source_url": {"type": "string"},
        "mechanism": {"type": "string", "enum": ["predictive_processing", "hebbian_learning", "reinforcement_learning", "attention", "hierarchical_abstraction", "unknown"]},
        "core_mechanism": {"type": "string"},
        "key_equation": {"type": "string"},
        "main_claim": {"type": "string"},
        "experience_probe": {"type": "string"},
        "experiment_design": {"type": "string"},
        "felt_sense_bridge": {"type": "string"},
        "immediate_use": {"type": "string"},
        "repeat_protocol": {"type": "string"},
        "refinement_signal": {"type": "string"},
        "transfer_domains": {"type": "array", "items": {"type": "string"}},
        "transform_formats": {"type": "array", "items": {"type": "string"}},
        "failure_modes": {"type": "array", "items": {"type": "string"}},
        "connection_to_ai": {"type": "string"},
        "connection_to_human_thinking": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence_quotes": {"type": "array", "items": {"type": "string"}},
    },
    "required": REQUIRED_FIELDS,
}


def validate_extraction(data: Dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    if data["mechanism"] not in EXTRACTION_SCHEMA["properties"]["mechanism"]["enum"]:
        raise ValueError(f"Invalid mechanism: {data['mechanism']}")
    for list_field in ["transfer_domains", "transform_formats", "failure_modes", "evidence_quotes"]:
        if not isinstance(data[list_field], list):
            raise ValueError(f"{list_field} must be a list")
    confidence = float(data["confidence"])
    if confidence < 0 or confidence > 1:
        raise ValueError("confidence must be between 0 and 1")


def _base(source_text: str, source_url: str, mechanism: MechanismName, core: str, equation: str, ai: str, human: str, failures: List[str], confidence: float = 0.72) -> ExtractedKnowledge:
    unknown = mechanism == "unknown"
    title = source_text.strip().split("\n", 1)[0][:90] or "Untitled source"
    return ExtractedKnowledge(
        title=title,
        source_type="unknown",
        source_url=source_url,
        mechanism=mechanism,
        core_mechanism=core,
        key_equation=equation,
        main_claim=core,
        experience_probe="UNKNOWN" if unknown else "Observe one concrete moment in the next 24 hours where this mechanism appears in behavior, body, or environment.",
        experiment_design="UNKNOWN" if unknown else "Run a minimal A/B or simulation test that could make the mechanism visibly succeed or fail.",
        felt_sense_bridge=human,
        immediate_use="UNKNOWN" if unknown else "Apply the mechanism to one live decision, study session, design choice, or debugging task today.",
        repeat_protocol="UNKNOWN" if unknown else "Repeat the observe-test-apply loop at least three times and compare outputs.",
        refinement_signal="UNKNOWN" if unknown else "If prediction, behavior, or output does not improve, revise the mechanism or reject the source claim.",
        transfer_domains=[] if unknown else ["brain", "AI", "personal practice"],
        transform_formats=[] if unknown else ["sentence", "equation", "code", "practice"],
        failure_modes=failures,
        connection_to_ai=ai,
        connection_to_human_thinking=human,
        confidence=0.2 if unknown else confidence,
        evidence_quotes=[source_text.strip()[:240]] if source_text.strip() else [],
    )


def extract_mechanism_offline(source_text: str, source_url: str = "") -> ExtractedKnowledge:
    """Deterministic TRUE-aware fallback for tests and CI.

    Specific cues are checked before generic phrases. For example, "reward prediction error"
    belongs to reinforcement learning, not generic predictive processing.
    """
    text = source_text.lower()
    if any(k in text for k in ["dopamine", "reward", "td error", "reinforcement", "q-learning"]):
        return _base(source_text, source_url, "reinforcement_learning", "Outcomes better than expected reinforce actions; worse outcomes weaken them.", "δ = r + γV(s') - V(s)", "TD learning, Q-learning, reward shaping, policy optimization.", "Motivation rises when expected reward and actual reward create a learning signal.", ["reward hacking", "short-term dopamine capture", "misaligned habit formation"])
    if any(k in text for k in ["prediction error", "free energy", "predictive coding", "surprise"]):
        return _base(source_text, source_url, "predictive_processing", "Predict, compare with reality, and update the internal model from error.", "F ≈ prediction_error + model_complexity", "World models, variational inference, predictive coding networks.", "You feel surprise when reality violates expectation; that felt mismatch drives updating.", ["strong prior ignores evidence", "over-updating to noise", "hallucination under weak correction"])
    if any(k in text for k in ["hebb", "synaptic", "stdp", "fire together", "spike timing"]):
        return _base(source_text, source_url, "hebbian_learning", "Repeated co-activation strengthens future co-activation.", "Δw ∝ x_i y_j", "Local learning rules, associative memory, biologically inspired learning.", "Repeated practice makes the same perception-action path easier to activate.", ["spurious association", "runaway excitation", "overlearning brittle habits"])
    if any(k in text for k in ["attention", "saliency", "query", "key", "value", "gating"]):
        return _base(source_text, source_url, "attention", "Select the signals that control processing and suppress the rest.", "Attention(Q,K,V)=softmax(QK^T/sqrt(d_k))V", "Transformer self-attention and saliency routing.", "Focus feels like one signal becoming louder and other possible actions becoming quieter.", ["attention capture", "missing weak but important signals", "saliency bias"])
    if any(k in text for k in ["hierarchy", "cortex", "abstraction", "column", "levels"]):
        return _base(source_text, source_url, "hierarchical_abstraction", "Compress lower-level details into higher-level reusable models.", "level_n = compress(level_{n-1})", "Deep networks, hierarchical RL, multi-level world models.", "Understanding feels deeper when many details collapse into one reusable principle.", ["wrong abstraction", "premature compression", "loss of detail across levels"])
    return _base(source_text, source_url, "unknown", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", ["insufficient evidence"])


def extract_mechanism_llm(source_text: str, source_url: str = "", model: str = "gpt-4o-mini") -> ExtractedKnowledge:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Install openai package to use --use-llm") from exc
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for --use-llm")
    client = OpenAI()
    prompt = f"""
Extract one core neuroscience mechanism using TRUE.

TRUE fields must be concrete:
E: experience_probe and experiment_design
U: felt_sense_bridge and immediate_use
R: repeat_protocol and refinement_signal
T: transfer_domains and transform_formats

Rules:
- Return only fields in the schema.
- If unsupported by source, write UNKNOWN.
- Prefer causal mechanism over summary.
- Mechanism must be one of the five Neuro-OS primitives or unknown.

Source URL: {source_url or 'UNKNOWN'}
Source text:
{source_text[:12000]}
""".strip()
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": "You are a strict TRUE validation extraction engine. Return JSON only."},
            {"role": "user", "content": prompt},
        ],
        text={"format": {"type": "json_schema", "name": "true_extraction", "strict": True, "schema": EXTRACTION_SCHEMA}},
    )
    data = json.loads(response.output_text)
    validate_extraction(data)
    return ExtractedKnowledge(**data)


def _known(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().upper() != "UNKNOWN"
    if isinstance(value, list):
        return bool(value) and all(_known(v) for v in value)
    return value is not None


def true_validate(knowledge: ExtractedKnowledge) -> Dict[str, Any]:
    e = 0.5 * _known(knowledge.experience_probe) + 0.5 * _known(knowledge.experiment_design)
    u = 0.4 * _known(knowledge.felt_sense_bridge) + 0.4 * _known(knowledge.immediate_use) + 0.2 * (len(knowledge.core_mechanism.split()) <= 18 and _known(knowledge.core_mechanism))
    r = 0.45 * _known(knowledge.repeat_protocol) + 0.45 * _known(knowledge.refinement_signal) + 0.1 * (len(knowledge.failure_modes) >= 2)
    t = 0.35 * (len(knowledge.transfer_domains) >= 2 and _known(knowledge.transfer_domains)) + 0.35 * (len(knowledge.transform_formats) >= 2 and _known(knowledge.transform_formats)) + 0.3 * (_known(knowledge.connection_to_ai) and _known(knowledge.connection_to_human_thinking))
    scores = {
        "E_experienceable_experimentable": round(float(e), 3),
        "U_understandable_usable": round(float(u), 3),
        "R_repeatable_refinable": round(float(r), 3),
        "T_transferable_transformable": round(float(t), 3),
        "confidence": round(float(knowledge.confidence), 3),
    }
    scores["TRUE"] = round(sum(scores.values()) / len(scores), 3)
    thresholds = {
        "E_experienceable_experimentable": 0.8,
        "U_understandable_usable": 0.75,
        "R_repeatable_refinable": 0.75,
        "T_transferable_transformable": 0.75,
        "confidence": 0.6,
    }
    failed = [k for k, threshold in thresholds.items() if scores[k] < threshold]
    if not failed:
        decision: Decision = "ACCEPT"
    elif scores["confidence"] >= 0.45 and knowledge.mechanism != "unknown":
        decision = "REFINE"
    else:
        decision = "REJECT"
    return {"scores": scores, "thresholds": thresholds, "failed_dimensions": failed, "decision": decision}


def run_pipeline(source_text: str, source_url: str = "", use_llm: bool = False, model: str = "gpt-4o-mini") -> Dict[str, Any]:
    extractor = extract_mechanism_llm if use_llm else extract_mechanism_offline
    knowledge = extractor(source_text=source_text, source_url=source_url, model=model) if use_llm else extractor(source_text, source_url)
    data = asdict(knowledge)
    validate_extraction(data)
    true_result = true_validate(knowledge)
    return {"knowledge": data, "true_validation": true_result, "decision": true_result["decision"]}


def write_json(output: Dict[str, Any], out_path: str) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Neuro-OS TRUE validation loop")
    parser.add_argument("--source-text", default="")
    parser.add_argument("--source-file", default="")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    source_text = Path(args.source_file).read_text(encoding="utf-8") if args.source_file else (args.source_text or "The brain minimizes prediction error and updates its model when surprised.")
    result = run_pipeline(source_text, source_url=args.source_url, use_llm=args.use_llm, model=args.model)
    if args.out:
        write_json(result, args.out)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
