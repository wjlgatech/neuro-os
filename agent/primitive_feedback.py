"""Primitive feedback loop for Neuro-OS.

Turns accepted primitive evolution decisions into machine-readable feedback that
can influence extraction and evaluation without silently overwriting primitives.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

FEEDBACK_PATH = Path("memory/primitive_feedback.jsonl")


def append_primitive_feedback(decision: Dict[str, Any], path: Path = FEEDBACK_PATH) -> None:
    if decision.get("decision") != "ACCEPT":
        raise ValueError("Only ACCEPT primitive decisions can become feedback")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(decision, ensure_ascii=False) + "\n")


def read_primitive_feedback(path: Path = FEEDBACK_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_extraction_context(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    context: Dict[str, Any] = {"primitive_definitions": {}, "transfer_domains": {}, "transform_formats": {}}
    for record in records:
        update = record.get("update", {})
        primitive = update.get("primitive_name")
        if not primitive:
            continue
        context["primitive_definitions"][primitive] = update.get("one_sentence_definition", "")
        context["transfer_domains"][primitive] = update.get("transfer_domains", [])
        context["transform_formats"][primitive] = update.get("transform_formats", [])
    return context


def strengthen_extraction_prompt(base_prompt: str, context: Dict[str, Any]) -> str:
    if not context.get("primitive_definitions"):
        return base_prompt
    return base_prompt + "\n\nAccepted primitive feedback:\n" + json.dumps(context, indent=2, ensure_ascii=False)


def evaluation_bias(record: Dict[str, Any]) -> Dict[str, Any]:
    update = record.get("update", {})
    return {
        "primitive_name": update.get("primitive_name"),
        "required_transfer_domains": update.get("transfer_domains", []),
        "required_transform_formats": update.get("transform_formats", []),
        "definition": update.get("one_sentence_definition", ""),
    }
