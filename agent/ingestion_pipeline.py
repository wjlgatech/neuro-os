"""
Neuro-OS Ingestion Pipeline

AI-native research ingestion pipeline for turning unstructured neuroscience
sources into structured, evaluated, executable knowledge.

Design goals:
- Typed extraction, not conversational summarization
- Schema validation before evaluation
- Evaluation before primitive mutation
- Human review gate before source-of-truth updates
- Offline demo mode for deterministic testing

Usage:
  python agent/ingestion_pipeline.py --source-text "The brain minimizes prediction error..."
  python agent/ingestion_pipeline.py --source-file sources/raw/example.txt --out parsed/summaries/example.json
  python agent/ingestion_pipeline.py --source-text "..." --use-llm

Environment:
  OPENAI_API_KEY must be set when --use-llm is enabled.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


# -----------------------------------------------------------------------------
# Schema
# -----------------------------------------------------------------------------

MechanismName = Literal[
    "predictive_processing",
    "hebbian_learning",
    "reinforcement_learning",
    "attention",
    "hierarchical_abstraction",
    "unknown",
]


@dataclass
class ExtractedKnowledge:
    title: str
    source_type: str
    source_url: str
    mechanism: MechanismName
    core_mechanism: str
    key_equation: str
    main_claim: str
    experimental_setup: str
    failure_modes: List[str]
    connection_to_ai: str
    connection_to_human_thinking: str
    executable_experiment: str
    mental_practice: str
    confidence: float
    evidence_quotes: List[str] = field(default_factory=list)


EXTRACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "source_type": {"type": "string", "enum": ["paper", "blog", "repo", "book", "unknown"]},
        "source_url": {"type": "string"},
        "mechanism": {
            "type": "string",
            "enum": [
                "predictive_processing",
                "hebbian_learning",
                "reinforcement_learning",
                "attention",
                "hierarchical_abstraction",
                "unknown",
            ],
        },
        "core_mechanism": {"type": "string"},
        "key_equation": {"type": "string"},
        "main_claim": {"type": "string"},
        "experimental_setup": {"type": "string"},
        "failure_modes": {"type": "array", "items": {"type": "string"}},
        "connection_to_ai": {"type": "string"},
        "connection_to_human_thinking": {"type": "string"},
        "executable_experiment": {"type": "string"},
        "mental_practice": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence_quotes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title",
        "source_type",
        "source_url",
        "mechanism",
        "core_mechanism",
        "key_equation",
        "main_claim",
        "experimental_setup",
        "failure_modes",
        "connection_to_ai",
        "connection_to_human_thinking",
        "executable_experiment",
        "mental_practice",
        "confidence",
        "evidence_quotes",
    ],
}


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------

def validate_extraction(data: Dict[str, Any]) -> None:
    """Small local validator to avoid mandatory jsonschema dependency."""
    required = EXTRACTION_SCHEMA["required"]
    missing = [field for field in required if field not in data]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    if data["mechanism"] not in EXTRACTION_SCHEMA["properties"]["mechanism"]["enum"]:
        raise ValueError(f"Invalid mechanism: {data['mechanism']}")

    if not isinstance(data["failure_modes"], list):
        raise ValueError("failure_modes must be a list")

    if not isinstance(data["evidence_quotes"], list):
        raise ValueError("evidence_quotes must be a list")

    confidence = float(data["confidence"])
    if confidence < 0 or confidence > 1:
        raise ValueError("confidence must be between 0 and 1")


# -----------------------------------------------------------------------------
# Extraction
# -----------------------------------------------------------------------------

def extract_mechanism_offline(source_text: str, source_url: str = "") -> ExtractedKnowledge:
    """Deterministic fallback extractor for local tests and CI.

    This is intentionally simple: it proves the pipeline loop works without
    pretending to be a scientific reader. Use --use-llm for real extraction.
    """
    text = source_text.lower()

    if any(k in text for k in ["prediction error", "free energy", "predictive coding", "surprise"]):
        mechanism: MechanismName = "predictive_processing"
        core = "The system predicts sensory input, computes error, and updates its internal model."
        equation = "F ≈ prediction_error + model_complexity"
        ai = "Variational inference, autoencoders, and predictive world models."
        human = "Surprise, confusion, and expectation mismatch trigger belief updating."
        failures = ["strong prior ignores evidence", "over-updating to noise", "hallucination under weak correction"]
    elif any(k in text for k in ["hebb", "synaptic", "stdp", "fire together", "spike timing"]):
        mechanism = "hebbian_learning"
        core = "Repeated co-activation strengthens connection weights; timing can determine potentiation or depression."
        equation = "Δw ∝ x_i y_j"
        ai = "Local learning rules, associative memory, and biologically inspired alternatives to backpropagation."
        human = "Repeated practice binds perception, action, and memory into easier future activation."
        failures = ["spurious association", "runaway excitation", "overlearning brittle habits"]
    elif any(k in text for k in ["dopamine", "reward", "td error", "reinforcement", "q-learning"]):
        mechanism = "reinforcement_learning"
        core = "Actions are reinforced when outcomes exceed prediction and weakened when outcomes disappoint."
        equation = "δ = r + γV(s') - V(s)"
        ai = "Temporal-difference learning, Q-learning, policy gradients, and reward shaping."
        human = "Motivation and habit loops are shaped by reward prediction error."
        failures = ["reward hacking", "short-term dopamine capture", "misaligned habit formation"]
    elif any(k in text for k in ["attention", "saliency", "query", "key", "value", "gating"]):
        mechanism = "attention"
        core = "The system selectively routes high-relevance information while suppressing irrelevant signals."
        equation = "Attention(Q,K,V)=softmax(QK^T/sqrt(d_k))V"
        ai = "Transformer self-attention and saliency-based routing."
        human = "Focus is a gating function that determines which errors, goals, and signals control behavior."
        failures = ["attention capture", "missing weak but important signals", "saliency bias"]
    elif any(k in text for k in ["hierarchy", "cortex", "abstraction", "column", "levels"]):
        mechanism = "hierarchical_abstraction"
        core = "Intelligence is organized across levels, from low-level features to high-level concepts and plans."
        equation = "level_n = compress(level_{n-1})"
        ai = "Deep neural networks, hierarchical RL, and multi-level world models."
        human = "Understanding improves when details are compressed into reusable abstractions."
        failures = ["wrong abstraction", "premature compression", "loss of detail across levels"]
    else:
        mechanism = "unknown"
        core = "UNKNOWN"
        equation = "UNKNOWN"
        ai = "UNKNOWN"
        human = "UNKNOWN"
        failures = ["insufficient evidence"]

    title = source_text.strip().split("\n", 1)[0][:90] or "Untitled source"
    quote = source_text.strip()[:240]

    return ExtractedKnowledge(
        title=title,
        source_type="unknown",
        source_url=source_url,
        mechanism=mechanism,
        core_mechanism=core,
        key_equation=equation,
        main_claim=core,
        experimental_setup="Derive a small simulation or observation task that isolates the mechanism.",
        failure_modes=failures,
        connection_to_ai=ai,
        connection_to_human_thinking=human,
        executable_experiment="Run a minimal numerical or behavioral test for the mechanism.",
        mental_practice="Predict, observe, compare, and update in a daily journal loop.",
        confidence=0.72 if mechanism != "unknown" else 0.2,
        evidence_quotes=[quote] if quote else [],
    )


def extract_mechanism_llm(source_text: str, source_url: str = "", model: str = "gpt-4o-mini") -> ExtractedKnowledge:
    """LLM extraction with structured output.

    Uses OpenAI Responses API structured outputs. Falls back to an explicit error
    if the OpenAI SDK or API key is unavailable.
    """
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Install openai package to use --use-llm") from exc

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for --use-llm")

    client = OpenAI()
    prompt = f"""
Extract one core neuroscience mechanism from the source below.

Rules:
- Return only fields in the schema.
- If a field is not supported by the source, write UNKNOWN.
- Mechanism must be one of the five Neuro-OS primitives or unknown.
- Prefer causal mechanisms over descriptions.
- Include short evidence quotes from the source when available.

Source URL: {source_url or 'UNKNOWN'}

Source text:
{source_text[:12000]}
""".strip()

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": "You are a strict neuroscience mechanism extraction engine. Return JSON only."},
            {"role": "user", "content": prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "neuro_os_extraction",
                "strict": True,
                "schema": EXTRACTION_SCHEMA,
            }
        },
    )

    data = json.loads(response.output_text)
    validate_extraction(data)
    return ExtractedKnowledge(**data)


# -----------------------------------------------------------------------------
# Evaluation
# -----------------------------------------------------------------------------

def _score_compression(core_mechanism: str) -> float:
    if core_mechanism == "UNKNOWN":
        return 0.0
    word_count = len(core_mechanism.split())
    return 1.0 if word_count <= 18 else 0.8 if word_count <= 30 else 0.5


def _score_transferability(knowledge: ExtractedKnowledge) -> float:
    fields = [knowledge.connection_to_ai, knowledge.connection_to_human_thinking]
    if any(f == "UNKNOWN" for f in fields):
        return 0.4
    return 1.0 if all(len(f.strip()) > 20 for f in fields) else 0.7


def _score_executability(knowledge: ExtractedKnowledge) -> float:
    if knowledge.executable_experiment == "UNKNOWN":
        return 0.0
    return 1.0 if any(k in knowledge.executable_experiment.lower() for k in ["test", "run", "simulate", "experiment"]) else 0.7


def _score_falsifiability(knowledge: ExtractedKnowledge) -> float:
    if not knowledge.failure_modes:
        return 0.0
    return 1.0 if len(knowledge.failure_modes) >= 2 else 0.7


def evaluate(knowledge: ExtractedKnowledge) -> Dict[str, float]:
    scores = {
        "compression": _score_compression(knowledge.core_mechanism),
        "transferability": _score_transferability(knowledge),
        "executability": _score_executability(knowledge),
        "falsifiability": _score_falsifiability(knowledge),
        "confidence": float(knowledge.confidence),
    }
    scores["final"] = round(sum(scores.values()) / len(scores), 3)
    return scores


def should_accept(scores: Dict[str, float]) -> bool:
    return (
        scores["compression"] >= 0.8
        and scores["transferability"] >= 0.7
        and scores["executability"] >= 0.7
        and scores["falsifiability"] >= 0.6
        and scores["confidence"] >= 0.6
    )


# -----------------------------------------------------------------------------
# Pipeline
# -----------------------------------------------------------------------------

def run_pipeline(
    source_text: str,
    source_url: str = "",
    use_llm: bool = False,
    model: str = "gpt-4o-mini",
) -> Dict[str, Any]:
    extractor = extract_mechanism_llm if use_llm else extract_mechanism_offline
    knowledge = extractor(source_text=source_text, source_url=source_url, model=model) if use_llm else extractor(source_text, source_url)
    data = asdict(knowledge)
    validate_extraction(data)
    scores = evaluate(knowledge)
    decision = "ACCEPT" if should_accept(scores) else "REJECT"
    return {"knowledge": data, "scores": scores, "decision": decision}


def write_json(output: Dict[str, Any], out_path: str) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Neuro-OS ingestion pipeline")
    parser.add_argument("--source-text", default="", help="Raw source text to extract")
    parser.add_argument("--source-file", default="", help="Path to raw source text file")
    parser.add_argument("--source-url", default="", help="URL or source identifier")
    parser.add_argument("--use-llm", action="store_true", help="Use OpenAI structured extraction")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model for --use-llm")
    parser.add_argument("--out", default="", help="Optional output JSON path")
    args = parser.parse_args()

    if args.source_file:
        source_text = Path(args.source_file).read_text(encoding="utf-8")
    elif args.source_text:
        source_text = args.source_text
    else:
        source_text = "The brain minimizes prediction error and updates its internal model when surprised."

    result = run_pipeline(source_text, source_url=args.source_url, use_llm=args.use_llm, model=args.model)

    if args.out:
        write_json(result, args.out)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
