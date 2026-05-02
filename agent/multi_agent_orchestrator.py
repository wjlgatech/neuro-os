"""
Neuro-OS Multi-Agent Orchestrator

Implements a minimal but explicit CompanyOS-style loop:
Planner → Extractor → Evaluator → Decision → Logger

This file does NOT hide logic in prompts.
Each step is explicit, testable, and replaceable.
"""

from typing import Dict, Any
from ingestion_pipeline import run_pipeline


def planner(concept: str) -> Dict[str, Any]:
    return {
        "concept": concept,
        "tasks": [
            "find_sources",
            "extract_mechanism",
            "evaluate",
            "decide",
        ],
    }


def extractor(source_text: str):
    return run_pipeline(source_text)


def evaluator(result: Dict[str, Any]):
    return result["scores"]


def decision(result: Dict[str, Any]):
    return result["decision"]


def orchestrate(source_text: str):
    plan = planner("neuroscience_mechanism")
    result = extractor(source_text)
    scores = evaluator(result)
    decision_result = decision(result)

    return {
        "plan": plan,
        "scores": scores,
        "decision": decision_result,
        "knowledge": result["knowledge"],
    }


if __name__ == "__main__":
    demo = "Dopamine encodes reward prediction error signals"
    print(orchestrate(demo))
