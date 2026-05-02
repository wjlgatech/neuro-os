"""Feedback memory for Neuro-OS TRUE decisions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

DEFAULT_MEMORY_PATH = "memory/true_feedback.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_feedback(record: Dict[str, Any], path: str = DEFAULT_MEMORY_PATH) -> None:
    event = {"timestamp": utc_now(), **record}
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_feedback(path: str = DEFAULT_MEMORY_PATH) -> List[Dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize_feedback(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    records = list(records)
    by_decision: Dict[str, int] = {}
    by_mechanism: Dict[str, int] = {}
    failed_dimensions: Dict[str, int] = {}

    for record in records:
        decision = record.get("decision", "UNKNOWN")
        by_decision[decision] = by_decision.get(decision, 0) + 1
        mechanism = record.get("knowledge", {}).get("mechanism", "UNKNOWN")
        by_mechanism[mechanism] = by_mechanism.get(mechanism, 0) + 1
        validation = record.get("true_validation", {})
        for dimension in validation.get("failed_dimensions", []):
            failed_dimensions[dimension] = failed_dimensions.get(dimension, 0) + 1

    return {
        "count": len(records),
        "by_decision": by_decision,
        "by_mechanism": by_mechanism,
        "failed_dimensions": failed_dimensions,
    }
