"""
End-user API surface for Neuro-OS.

Two convenience entry points:

* ``process_text(text, ontology=None)`` — run a single document through
  the full pipeline (ingest → consistency → evolution → evaluate) and
  return a structured result. Read-only: never mutates the ontology.

* ``ingest_documents(texts, ontology=None, ontology_path=None, ...)`` —
  multi-doc ingestion that drives the full self-evolving loop with
  optional ontology persistence and sandbox validation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from agent.ingestion_pipeline import _canonical_ontology, run_pipeline
from agent.ontology_evolution import evolve_from_extraction
from agent.primitive_evolution_evaluator import evaluate_update_dict
from agent.primitive_feedback import build_extraction_context
from agent.self_evolving_loop import run_self_evolution


def _load_ontology_arg(
    ontology: Optional[Union[Dict[str, Any], str, Path]] = None,
) -> Dict[str, Any]:
    """Accept an ontology dict, a path, or None (canonical fallback)."""
    if ontology is None:
        return _canonical_ontology()
    if isinstance(ontology, (str, Path)):
        with open(ontology, "r", encoding="utf-8") as f:
            return json.load(f)
    if isinstance(ontology, dict):
        return ontology
    raise TypeError(f"unsupported ontology argument: {type(ontology).__name__}")


def process_text(
    text: str,
    ontology: Optional[Union[Dict[str, Any], str, Path]] = None,
) -> Dict[str, Any]:
    """Run a single document through the pipeline and report what happened.

    Returns
    -------
    dict
        ``{mechanism, pipeline_decision, true_score, action, evaluation,
        proposal, consistency, feedback_context}``.
    """
    ont = _load_ontology_arg(ontology)
    pipeline_result = run_pipeline(text, ont)
    evolution = evolve_from_extraction(pipeline_result, ont)
    proposal = evolution.get("proposal")
    evaluation: Optional[Dict[str, Any]] = None
    if proposal:
        try:
            evaluation = evaluate_update_dict(proposal)
        except ValueError as exc:
            evaluation = {"decision": "REJECT", "scores": {}, "reason": str(exc)}
    return {
        "mechanism": pipeline_result["knowledge"].get("mechanism"),
        "pipeline_decision": pipeline_result.get("decision"),
        "true_score": pipeline_result["true_validation"]["scores"]["TRUE"],
        "action": evolution.get("action"),
        "consistency": evolution.get("consistency"),
        "proposal": proposal,
        "evaluation": evaluation,
        "feedback_context": build_extraction_context(),
    }


def ingest_documents(
    texts: Iterable[str],
    ontology: Optional[Union[Dict[str, Any], str, Path]] = None,
    ontology_path: Optional[Union[str, Path]] = None,
    run_in_sandbox: bool = False,
    enable_merge: bool = True,
) -> Dict[str, Any]:
    """Drive the full self-evolving loop over a batch of documents."""
    ont = _load_ontology_arg(ontology)
    return run_self_evolution(
        texts,
        ontology=ont,
        ontology_path=ontology_path,
        run_in_sandbox=run_in_sandbox,
        enable_merge=enable_merge,
    )


__all__ = ["process_text", "ingest_documents"]
