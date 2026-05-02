"""
Primitive Feedback Persistence.

Stores accepted primitive updates to a JSON-lines log on disk
(``memory/primitive_feedback.jsonl`` by default) and exposes the
accumulated context for downstream extraction.

Loading happens lazily on the first call so tests can override
``FEEDBACK_PATH`` without import-time side effects.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

FEEDBACK_PATH = Path("memory/primitive_feedback.jsonl")

_loaded_path: Path | None = None
_primitive_feedback: List[Dict[str, Any]] = []


def _ensure_loaded() -> None:
    """Load feedback from ``FEEDBACK_PATH`` once per process / path change."""
    global _loaded_path, _primitive_feedback
    if _loaded_path == FEEDBACK_PATH:
        return
    _primitive_feedback = []
    if FEEDBACK_PATH.exists():
        with FEEDBACK_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    _primitive_feedback.append(json.loads(line))
    _loaded_path = FEEDBACK_PATH


def append_primitive_feedback(update: Dict[str, Any]) -> None:
    """Append an accepted primitive update to the feedback log.

    Raises ``ValueError`` if the update is not marked ``ACCEPT``.
    """
    if update.get("decision") != "ACCEPT":
        raise ValueError(
            "Only accepted updates may be appended to primitive feedback."
        )
    _ensure_loaded()
    _primitive_feedback.append(update)
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(update, ensure_ascii=False) + "\n")


def build_extraction_context() -> Dict[str, Any]:
    """Return accepted-primitive context for downstream extraction.

    Most recent definition for each primitive wins.
    """
    _ensure_loaded()
    context: Dict[str, str] = {}
    for update in _primitive_feedback:
        primitive_name = update.get("primitive_name")
        definition = (
            update.get("one_sentence_definition")
            or update.get("proposed_change")
        )
        if primitive_name and definition:
            context[primitive_name] = definition
    return {"primitive_definitions": context}


def reset_for_tests() -> None:
    """Drop the in-memory cache; the next call reloads from disk."""
    global _loaded_path, _primitive_feedback
    _loaded_path = None
    _primitive_feedback = []


__all__ = [
    "FEEDBACK_PATH",
    "append_primitive_feedback",
    "build_extraction_context",
    "reset_for_tests",
]
