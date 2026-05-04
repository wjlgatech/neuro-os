"""
Self-Evolving Loop Orchestrator.

Wires the modules into the closed loop documented in the README:

1. **Ingest** — ``run_pipeline`` extracts a candidate mechanism and TRUE
   scores from raw text.
2. **Validate + detect contradiction** — ``evolve_from_extraction``
   compares the extraction to the ontology and either does nothing,
   proposes a refinement, or escalates for review.
3. **Evaluate refinement** — ``evaluate_update_dict`` scores any proposal
   along TRUE + evidence.
4. **Golden-case gate** — before merging an accepted refinement into the
   ontology, run the project's golden cases through ``run_pipeline``
   with the proposed ontology. If accuracy drops the merge is reverted.
5. **Persist** — every doc produces a ``version_registry.jsonl`` entry
   with before/after metrics, golden-gate results, and merge status.
   Accepted, gate-passing refinements are written to
   ``primitive_feedback.jsonl`` and the updated ontology is written
   back to ``ontology_path`` if one was provided.
6. **Optional sandbox testing** — when ``run_in_sandbox=True`` the loop
   spins up a sandbox copy of ``agent/`` and runs an import smoke test
   so the in-process code is never the only thing validating itself.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from agent.ingestion_pipeline import _canonical_ontology, run_pipeline
from agent.ontology_evolution import evolve_from_extraction
from agent.primitive_evolution_evaluator import evaluate_update_dict
from agent.primitive_feedback import append_primitive_feedback
from agent.sandbox_runner import create_sandbox, cleanup_sandbox, run_validation
from agent.self_evolution_controller import GOLDEN_CASES
from agent.version_registry import append_version


def _safe_evaluate(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a proposal, converting ``ValueError`` into a REJECT result."""
    try:
        return evaluate_update_dict(proposal)
    except ValueError as exc:
        return {
            "decision": "REJECT",
            "scores": {},
            "reason": f"missing required fields: {exc}",
        }


def _golden_accuracy(
    ontology: Dict[str, Any],
    golden_cases: Optional[List[Dict[str, str]]] = None,
    priority_rules_path: Optional[Path] = None,
) -> float:
    """Run golden cases through the pipeline; return classification accuracy.

    ``golden_cases`` defaults to the neuroscience ``GOLDEN_CASES`` so existing
    callers are unchanged. Custom domains pass their own list.
    """
    cases = golden_cases if golden_cases is not None else GOLDEN_CASES
    if not cases:
        return 1.0
    correct = 0
    for case in cases:
        result = run_pipeline(
            case["text"], ontology, priority_rules_path=priority_rules_path
        )
        if result["knowledge"].get("mechanism") == case["expected_mechanism"]:
            correct += 1
    return round(correct / len(cases), 3)


def _apply_ontology_merge(
    ontology: Dict[str, Any], proposal: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge an accepted proposal into the ontology in place; return snapshot."""
    name = proposal["primitive_name"]
    primitives = ontology.setdefault("primitives", {})
    primitive = primitives.setdefault(
        name,
        {"definition": "", "aliases": [], "sources": [], "relations": []},
    )
    snapshot = copy.deepcopy(primitive)
    new_def = (
        proposal.get("one_sentence_definition")
        or proposal.get("proposed_change")
        or ""
    )
    if new_def and new_def != primitive.get("definition"):
        primitive["definition"] = new_def
    quote = proposal.get("source_quote")
    if quote:
        sources = primitive.setdefault("sources", [])
        if quote not in sources:
            sources.append(quote)
    return snapshot


def _revert_ontology_merge(
    ontology: Dict[str, Any], name: str, snapshot: Dict[str, Any]
) -> None:
    ontology["primitives"][name] = snapshot


def _persist_ontology(ontology: Dict[str, Any], ontology_path: Optional[Path]) -> None:
    if ontology_path is None:
        return
    ontology_path.parent.mkdir(parents=True, exist_ok=True)
    with ontology_path.open("w", encoding="utf-8") as f:
        json.dump(ontology, f, indent=2)


def run_self_evolution(
    source_texts: Iterable[str],
    ontology: Optional[Dict[str, Any]] = None,
    ontology_path: Optional[Union[str, Path]] = None,
    run_in_sandbox: bool = False,
    enable_merge: bool = True,
    golden_cases: Optional[List[Dict[str, str]]] = None,
    priority_rules_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run the closed loop over a batch of source texts.

    Parameters
    ----------
    source_texts : iterable of str
        Raw documents to ingest.
    ontology : dict, optional
        Ontology to validate against. Falls back to the built-in
        canonical ontology when ``None``.
    ontology_path : str or Path, optional
        Where to persist the updated ontology after each accepted merge.
    run_in_sandbox : bool
        When True, runs an import smoke test against a sandbox copy of
        ``agent/`` and records the result on every ingestion.
    enable_merge : bool
        When True (default), accepted refinements that pass the golden
        gate mutate the ontology and append to feedback. When False,
        accepted refinements are still scored and recorded but the
        ontology is left untouched.
    golden_cases : list of dict, optional
        Domain-specific golden cases to gate merges against. Defaults to
        the neuroscience ``GOLDEN_CASES``; custom domains pass their own.
    priority_rules_path : Path, optional
        Domain-specific priority-rules file for keyword routing. Defaults
        to the neuroscience ``PRIORITY_RULES_PATH``.
    """
    if ontology is None:
        ontology = _canonical_ontology()
    onto_path = Path(ontology_path) if ontology_path is not None else None

    report: Dict[str, Any] = {
        "ingested": [],
        "evolutions": [],
        "evaluations": [],
        "registry_entries": [],
        "feedback_appended": 0,
        "merges_applied": 0,
        "merges_reverted": 0,
        "sandbox": None,
    }

    sandbox_path: Optional[str] = None
    sandbox_validation: Optional[Dict[str, Any]] = None
    try:
        if run_in_sandbox:
            sandbox_path = create_sandbox()
            sandbox_validation = run_validation(sandbox_path)
            report["sandbox"] = sandbox_validation

        for text in source_texts:
            pipeline_result = run_pipeline(
                text, ontology, priority_rules_path=priority_rules_path
            )
            report["ingested"].append(pipeline_result)

            evolution = evolve_from_extraction(pipeline_result, ontology)
            report["evolutions"].append(evolution)

            evaluation: Optional[Dict[str, Any]] = None
            merge_status = "no_proposal"
            baseline_acc: Optional[float] = None
            new_acc: Optional[float] = None

            proposal = evolution.get("proposal")
            if proposal:
                evaluation = _safe_evaluate(proposal)
                report["evaluations"].append(evaluation)
                merge_status = "evaluated"
                if evaluation["decision"] == "ACCEPT":
                    if enable_merge:
                        baseline_acc = _golden_accuracy(
                            ontology, golden_cases, priority_rules_path
                        )
                        snapshot = _apply_ontology_merge(ontology, proposal)
                        new_acc = _golden_accuracy(
                            ontology, golden_cases, priority_rules_path
                        )
                        if new_acc >= baseline_acc:
                            append_primitive_feedback({**proposal, **evaluation})
                            report["feedback_appended"] += 1
                            report["merges_applied"] += 1
                            merge_status = "merged"
                            _persist_ontology(ontology, onto_path)
                        else:
                            _revert_ontology_merge(
                                ontology, proposal["primitive_name"], snapshot
                            )
                            report["merges_reverted"] += 1
                            merge_status = "reverted_on_regression"
                    else:
                        append_primitive_feedback({**proposal, **evaluation})
                        report["feedback_appended"] += 1
                        merge_status = "accepted_no_merge"

            entry = append_version(
                {
                    "doc": text,
                    "mechanism": pipeline_result["knowledge"].get("mechanism"),
                    "pipeline_decision": pipeline_result.get("decision"),
                    "before_true_score": pipeline_result["true_validation"]["scores"]["TRUE"],
                    "evolution_action": evolution.get("action"),
                    "consistency": evolution.get("consistency"),
                    "evaluation_decision": evaluation["decision"] if evaluation else None,
                    "evaluation_scores": evaluation["scores"] if evaluation else None,
                    "merge_status": merge_status,
                    "golden_accuracy_before": baseline_acc,
                    "golden_accuracy_after": new_acc,
                    "after_true_score": (
                        max(
                            pipeline_result["true_validation"]["scores"]["TRUE"],
                            (
                                sum(evaluation["scores"].values())
                                / max(len(evaluation["scores"]), 1)
                            )
                            if evaluation and evaluation.get("scores")
                            else 0.0,
                        )
                    ),
                    "sandbox_success": (
                        sandbox_validation["success"] if sandbox_validation else None
                    ),
                }
            )
            report["registry_entries"].append(entry)
    finally:
        if sandbox_path is not None:
            cleanup_sandbox(sandbox_path)

    return report


__all__ = [
    "run_self_evolution",
    "_golden_accuracy",
    "_apply_ontology_merge",
    "_revert_ontology_merge",
]
