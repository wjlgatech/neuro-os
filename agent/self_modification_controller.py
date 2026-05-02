"""Self-modification controller for Neuro-OS.

Implements true A/B self-evolution:
production pipeline -> sandbox pipeline -> compare -> promote/reject -> log.

The controller is bounded by:
- allowlisted sandbox mutations
- unittest validation inside the sandbox
- sandbox pipeline import for real after metrics
- no production promotion unless promote=True
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from agent.self_evolution_controller import GOLDEN_CASES, evaluate_observations, observe, run_self_evolution
from agent.sandbox_runner import (
    apply_bounded_change,
    create_sandbox,
    load_sandbox_pipeline,
    promote_files,
    run_validation,
    write_sandbox_report,
)
from agent.version_registry import append_version


def is_beneficial(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    """Return True only when the sandbox candidate does not regress metrics."""
    if not before or not after:
        return False

    before_errors = len(before.get("errors", []))
    after_errors = len(after.get("errors", []))

    return (
        after.get("accuracy", 0.0) >= before.get("accuracy", 0.0)
        and after.get("avg_true_score", 0.0) >= before.get("avg_true_score", 0.0)
        and after.get("accept_rate", 0.0) >= before.get("accept_rate", 0.0)
        and after_errors <= before_errors
    )


def evaluate_sandbox_system(sandbox_path) -> Dict[str, Any]:
    """Evaluate the sandbox pipeline directly for true A/B comparison."""
    sandbox_pipeline = load_sandbox_pipeline(sandbox_path)
    sandbox_observations = observe(GOLDEN_CASES, pipeline_fn=sandbox_pipeline)
    return evaluate_observations(sandbox_observations).__dict__


def self_modify(promote: bool = False) -> Dict[str, Any]:
    """Run bounded self-modification with true sandbox A/B evaluation.

    Args:
        promote: If False, accepted changes are logged but not copied back.
                 If True, accepted sandbox files are promoted to production.
    """
    base = run_self_evolution()
    before_eval = base.get("evaluation", {})
    proposals = base.get("control_proposals", [])

    results: List[Dict[str, Any]] = []

    for change in proposals:
        change_id = change.get("change_id", "unknown_change")
        try:
            sandbox_path = create_sandbox()
            changed_files = apply_bounded_change(sandbox_path, change)
            sandbox_test = run_validation(sandbox_path)
            after_eval = evaluate_sandbox_system(sandbox_path)

            beneficial = is_beneficial(before_eval, after_eval)
            accepted = bool(beneficial and sandbox_test.success)

            promoted_files: List[str] = []
            if accepted and promote:
                promoted_files = promote_files(sandbox_path, changed_files)
                status = "PROMOTED"
            elif accepted:
                status = "ACCEPTED_NOT_PROMOTED"
            else:
                status = "REJECTED"

            record = {
                "change_id": change_id,
                "status": status.lower(),
                "changed_files": changed_files,
                "promoted_files": promoted_files,
                "metrics_before": before_eval,
                "metrics_after": after_eval,
                "sandbox_success": sandbox_test.success,
                "sandbox_path": str(sandbox_path),
                "true_ab": True,
            }
            append_version(record)
            write_sandbox_report(sandbox_path, record)

            results.append({
                "change": change,
                "status": status,
                "accepted": accepted,
                "promoted_files": promoted_files,
                "sandbox_success": sandbox_test.success,
                "changed_files": changed_files,
                "metrics_before": before_eval,
                "metrics_after": after_eval,
                "sandbox_path": str(sandbox_path),
            })

        except Exception as exc:
            append_version({"change_id": change_id, "status": "error", "error": str(exc), "true_ab": True})
            results.append({"change": change, "status": "ERROR", "error": str(exc)})

    return {
        "base_status": base.get("status"),
        "proposal_count": len(proposals),
        "promote_mode": promote,
        "true_ab": True,
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(self_modify(promote=False), indent=2))
