"""Self-modification controller for Neuro-OS.

Implements a safe, bounded self-evolution loop:
OBSERVE -> EVALUATE -> PROPOSE -> SANDBOX -> TEST -> COMPARE -> PROMOTE/REJECT -> LOG.

This controller does not let the model freely rewrite production files. It uses
allowlisted sandbox changes, validation tests, metric comparison, and a version
registry before any promotion.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from agent.self_evolution_controller import run_self_evolution
from agent.sandbox_runner import create_sandbox, apply_bounded_change, run_validation, promote_files
from agent.version_registry import append_version


def is_beneficial(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    """Return True only when the candidate does not regress core metrics."""
    if not before or not after:
        return False

    before_errors = len(before.get("errors", []))
    after_errors = len(after.get("errors", []))

    return (
        after.get("accuracy", 0.0) >= before.get("accuracy", 0.0)
        and after.get("avg_true_score", 0.0) >= before.get("avg_true_score", 0.0)
        and after_errors <= before_errors
    )


def evaluate_current_system() -> Dict[str, Any]:
    """Evaluate the production system using the current OEC controller."""
    return run_self_evolution().get("evaluation", {})


def self_modify(promote: bool = False) -> Dict[str, Any]:
    """Run safe self-modification.

    Args:
        promote: If False, validated changes are reported but not promoted.
                 If True, accepted sandbox files are copied back to production.

    Returns:
        A structured report containing baseline status, evaluated changes,
        validation results, and any promoted files.
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
            after_eval = evaluate_current_system()

            beneficial = is_beneficial(before_eval, after_eval)
            accepted = bool(beneficial and sandbox_test.success)

            promoted_files: List[str] = []
            status = "ACCEPTED_NOT_PROMOTED"

            if accepted and promote:
                promoted_files = promote_files(sandbox_path, changed_files)
                status = "PROMOTED"
            elif not accepted:
                status = "REJECTED"

            append_version({
                "change_id": change_id,
                "status": status.lower(),
                "changed_files": changed_files,
                "promoted_files": promoted_files,
                "metrics_before": before_eval,
                "metrics_after": after_eval,
                "sandbox_success": sandbox_test.success,
                "sandbox_path": str(sandbox_path),
            })

            results.append({
                "change": change,
                "status": status,
                "accepted": accepted,
                "promoted_files": promoted_files,
                "sandbox_success": sandbox_test.success,
                "changed_files": changed_files,
                "metrics_before": before_eval,
                "metrics_after": after_eval,
            })

        except Exception as exc:
            append_version({
                "change_id": change_id,
                "status": "error",
                "error": str(exc),
            })
            results.append({
                "change": change,
                "status": "ERROR",
                "error": str(exc),
            })

    return {
        "base_status": base.get("status"),
        "proposal_count": len(proposals),
        "promote_mode": promote,
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(self_modify(promote=False), indent=2))
