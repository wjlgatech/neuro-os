"""
Neuro-OS L2 (code loop): closed self-modification.

The substrate (``flywheel_loop.self_modification.run_self_modification``)
provides the generic OEC loop. This module is the thin neuro-os adapter
that:

* uses ``propose_controls`` from ``agent.self_evolution_controller``
  as the proposer,
* enriches each outcome with ``post_accuracy`` extracted from the
  ``golden_accuracy`` validator's result, so existing tests can read
  it directly off the outcome dict,
* exposes the same ``report["registry_entries"]`` and
  ``report["merges_applied"]`` shape neuro-os tests expect (the
  substrate uses ``registry`` and reports beneficial-but-not-promoted
  separately).

The substrate is the engine; this file is the steering wheel.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from flywheel_loop.self_modification import (
    run_self_modification as _fw_run_self_modification,
)

from agent.domains import Domain
from agent.self_evolution_controller import propose_controls


def _post_accuracy_from_validators(validators) -> Optional[float]:
    for r in validators or []:
        if r.get("name") == "golden_accuracy" and "accuracy" in r:
            return float(r["accuracy"])
    return None


def run_self_modification(
    domain: Domain,
    max_patches: int = 1,
) -> Dict[str, Any]:
    """Drive ``domain`` through one OEC tick using neuro-os's proposer."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw = _fw_run_self_modification(
        domain,
        propose_controls,
        source_dir=repo_root,
        repo_root=repo_root,
        max_patches=max_patches,
    )
    # Enrich each outcome with post_accuracy + adapt to neuro-os keys.
    enriched_results = []
    merges_applied = 0
    for outcome in raw.get("results", []):
        post = _post_accuracy_from_validators(outcome.get("validators"))
        outcome["post_accuracy"] = post
        if outcome.get("beneficial") and (
            outcome.get("promote", {}).get("live_apply_success")
        ):
            merges_applied += 1
        enriched_results.append(outcome)

    return {
        **raw,
        "results": enriched_results,
        "registry_entries": raw.get("registry", []),
        "merges_applied": merges_applied,
    }


__all__ = ["run_self_modification"]
