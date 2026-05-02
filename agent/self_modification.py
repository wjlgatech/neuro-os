"""
Closed-loop self-modification for neuro-os.

``run_self_modification(domain)`` runs a full OEC pass against the
domain: observe golden cases, evaluate the result, propose patched
controls, and for each patched proposal:

1. Spin up an isolated sandbox copy of the repo.
2. Apply the patch in the sandbox (allowlisted ops + paths only).
3. Run the domain's validators against the sandbox.
4. If every validator passes AND the post-patch goldens accuracy is
   at least the baseline accuracy, promote the patch by re-applying
   it to the live tree and recording it in the version registry.
   Otherwise revert (the live tree is never touched) and record
   ``rolled_back`` in the registry.

Safety properties:

* The host process never directly mutates the live tree until the
  sandbox has validated the patch.
* Every patch is allowlisted (``ALLOWED_OPS`` in ``patches.py``) and
  must target a path on the domain's ``mutable_paths`` list.
* Every patch carries an inverse so the registry entry includes a
  one-step rollback recipe.
* ``max_patches`` defaults to 1 — at most one mutation per loop tick.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.domains import Domain
from agent.patches import Patch, PatchResult, apply_patch
from agent.sandbox_runner import (
    apply_bounded_change,
    cleanup_sandbox,
    create_sandbox,
    promote_files,
)
from agent.self_evolution_controller import (
    ControlProposal,
    evaluate_observations,
    observe,
    propose_controls,
    validate_change,
)
from agent.version_registry import append_version


def _validators_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compact view of validator results for registry storage."""
    return {
        "all_passed": all(r.get("success") for r in results),
        "results": [
            {k: v for k, v in r.items() if k not in ("imported",)}
            for r in results
        ],
    }


def _accuracy_from_validators(results: List[Dict[str, Any]]) -> Optional[float]:
    for r in results:
        if r.get("name") == "golden_accuracy" and "accuracy" in r:
            return float(r["accuracy"])
    return None


def _evaluate_patch(
    domain: Domain,
    patch: Patch,
    baseline_accuracy: float,
) -> Dict[str, Any]:
    """Apply ``patch`` in a fresh sandbox; return validator + decision results."""
    sandbox_path = create_sandbox()
    try:
        repo_root = Path(__file__).resolve().parent.parent
        # Apply the patch in the sandbox (sandbox is the new repo_root for this op).
        apply_result = apply_patch(patch, sandbox_path, domain.mutable_paths)
        validator_results: List[Dict[str, Any]] = []
        if apply_result.success:
            for validator in domain.validators:
                validator_results.append(validator(sandbox_path))
        post_accuracy = _accuracy_from_validators(validator_results)
        beneficial = (
            apply_result.success
            and all(r.get("success") for r in validator_results)
            and (post_accuracy is None or post_accuracy >= baseline_accuracy)
        )
        promote_summary: Optional[Dict[str, Any]] = None
        if beneficial:
            # Promote: re-apply the patch to the live tree. The sandbox copy
            # already proved the change is safe; re-applying via the same
            # allowlisted handler is simpler than copying files back.
            live_apply = apply_patch(
                patch,
                str(repo_root),
                domain.mutable_paths,
            )
            promote_summary = {
                "live_apply_success": live_apply.success,
                "live_apply_reason": live_apply.reason,
                "files": [apply_result.target_path] if live_apply.success else [],
            }
        return {
            "patch": patch.to_dict(),
            "apply": apply_result.to_dict(),
            "validators": validator_results,
            "validators_summary": _validators_summary(validator_results),
            "baseline_accuracy": baseline_accuracy,
            "post_accuracy": post_accuracy,
            "beneficial": beneficial,
            "promote": promote_summary,
        }
    finally:
        cleanup_sandbox(sandbox_path)


def run_self_modification(
    domain: Domain,
    max_patches: int = 1,
) -> Dict[str, Any]:
    """Execute a closed self-modification loop over ``domain``.

    Returns a structured report and writes one or more rows to the
    version registry.
    """
    # Step 1: observe
    observations = observe(domain.golden_cases, pipeline_fn=domain.extractor)
    baseline_eval = evaluate_observations(observations)

    # Step 2: propose
    proposals = propose_controls(baseline_eval)
    patched_proposals: List[ControlProposal] = [
        p for p in proposals if p.patch is not None
    ][:max_patches]

    # Short-circuit: stable system, no patched proposals → nothing to do.
    if not patched_proposals:
        registry_entry = append_version(
            {
                "event": "self_modification",
                "domain": domain.name,
                "status": "STABLE",
                "baseline_accuracy": baseline_eval.accuracy,
                "errors": baseline_eval.errors,
                "candidate_proposals": [
                    p.change_id for p in proposals if p.patch is None
                ],
            }
        )
        return {
            "status": "STABLE",
            "domain": domain.name,
            "baseline": asdict(baseline_eval),
            "patched_proposals": 0,
            "candidate_proposals": [
                {"change_id": p.change_id, "patchable": False} for p in proposals
            ],
            "results": [],
            "registry": [registry_entry],
        }

    # Step 3: evaluate each patched proposal in its own sandbox
    results: List[Dict[str, Any]] = []
    registry_entries: List[Dict[str, Any]] = []
    for proposal in patched_proposals:
        outcome = _evaluate_patch(domain, proposal.patch, baseline_eval.accuracy)
        outcome["change_id"] = proposal.change_id
        outcome["reason"] = proposal.reason
        results.append(outcome)
        status = "promoted" if outcome["beneficial"] and outcome.get("promote", {}).get("live_apply_success") else "rolled_back"
        entry = append_version(
            {
                "event": "self_modification",
                "domain": domain.name,
                "change_id": proposal.change_id,
                "status": status,
                "baseline_accuracy": baseline_eval.accuracy,
                "post_accuracy": outcome["post_accuracy"],
                "patch": outcome["patch"],
                "rollback_patch": outcome["apply"]["inverse"],
                "validators_summary": outcome["validators_summary"],
                "promote": outcome.get("promote"),
            }
        )
        registry_entries.append(entry)

    overall_status = (
        "MUTATION_PROMOTED"
        if any(r["beneficial"] for r in results)
        else "MUTATION_REVERTED"
    )
    return {
        "status": overall_status,
        "domain": domain.name,
        "baseline": asdict(baseline_eval),
        "patched_proposals": len(patched_proposals),
        "results": results,
        "registry": registry_entries,
    }


__all__ = ["run_self_modification"]
