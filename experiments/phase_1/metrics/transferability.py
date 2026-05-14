"""H3 — Transferability lift.

For schema systems, the `invariant` field is supposed to capture a property
that holds across verticals (it's domain-transferable by definition). H3
predicts: decisions that cite the invariant field cross-vertically should
succeed at a rate above chance.

For non-schema systems, there's no invariant field, so cross-vertical
performance is just diluted in-vertical performance. We measure the LIFT:
cross-vertical success rate ÷ in-vertical success rate.
"""

from __future__ import annotations


def transferability_lift(system: str, decisions: list, outcomes: list) -> dict:
    outcome_by_id = {o.decision_id: o for o in outcomes}

    native_decisions = [d for d in decisions if not d.is_cross_vertical]
    cross_decisions = [d for d in decisions if d.is_cross_vertical]

    def _success_rate(ds):
        if not ds:
            return None
        n_success = sum(1 for d in ds if outcome_by_id.get(d.decision_id) and outcome_by_id[d.decision_id].success)
        return n_success / len(ds)

    native_rate = _success_rate(native_decisions)
    cross_rate = _success_rate(cross_decisions)

    if native_rate is None or cross_rate is None:
        return {
            "applicable": False,
            "n_native": len(native_decisions),
            "n_cross": len(cross_decisions),
        }

    if native_rate == 0:
        lift = None
    else:
        lift = cross_rate / native_rate

    return {
        "applicable": True,
        "native_success_rate": native_rate,
        "cross_vertical_success_rate": cross_rate,
        "transferability_lift_ratio": lift,
        "n_native": len(native_decisions),
        "n_cross": len(cross_decisions),
    }
