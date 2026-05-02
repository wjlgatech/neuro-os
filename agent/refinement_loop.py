"""Refinement loop for TRUE."""

from typing import Dict


def propose_refinement(true_validation: Dict):
    failed = true_validation.get("failed_dimensions", [])
    actions = []
    for f in failed:
        if f.startswith("E"):
            actions.append("Add concrete experiment")
        elif f.startswith("U"):
            actions.append("Make it usable immediately")
        elif f.startswith("R"):
            actions.append("Add repeatable protocol")
        elif f.startswith("T"):
            actions.append("Add transfer domains")
    return actions
