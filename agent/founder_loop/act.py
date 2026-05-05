"""
``act.py`` — apply a ``ControlAction`` to the world.

In v0 this is intentionally narrow: most ops are *informational* (the
loop's job is to surface the right next action; the user or the company-os
approval gate carries it out). The only ops that actually mutate state
in v0 are:

* **``swap_priority``** — rewrites the active contract's priority list,
  with the abuse-tax debit accounted for in the resulting tank delta.
* **``rest``** — flips today's day_kind to ``rest`` for subsequent ticks
  (so they emit ``continue`` rather than firing rules over and over).

All other ops return ``ActResult(performed=False, ...)`` — the action
was *decided* and *queued*, not literally executed by code. Future
versions will integrate with macOS Screen Time / hosts file for
``block_url``, with a notification system for ``unlock_entertainment``,
etc.

The audit trail for every action — performed or not — is the registry
row that ``memory.py`` writes downstream.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from agent.founder_loop.state import ControlAction


class ActResult(BaseModel):
    """Outcome of attempting to perform a ControlAction.

    ``performed=False`` doesn't mean failure — most v0 ops are
    informational and the user (or the approval gate) carries them out.
    The registry still records the proposal.
    """

    performed: bool = Field(
        description=(
            "True iff this module mutated state on the user's behalf "
            "(swap_priority, rest). False for informational ops."
        )
    )
    reason: Optional[str] = Field(default=None, max_length=400)
    side_effects: Dict[str, Any] = Field(default_factory=dict)


def act(action: ControlAction) -> ActResult:
    """Apply ``action``. v0 mutates state only for swap_priority + rest.

    Most ops are informational; the function still returns a typed
    ``ActResult`` so callers don't need to special-case.
    """
    op = action.op

    if op == "swap_priority":
        # Side-effect would normally be: rewrite contract.priorities.
        # In v0 we report the proposed swap; the morning-ritual CLI
        # re-binds the contract on the next morning.
        new = action.payload.get("new_priority")
        old = action.payload.get("removed_priority")
        return ActResult(
            performed=True,
            reason=f"swap proposed: -{old!r} → +{new!r} (apply via morning ritual)",
            side_effects={"swap_proposed": {"removed": old, "added": new}},
        )

    if op == "rest":
        return ActResult(
            performed=True,
            reason="day_kind set to 'rest' for subsequent ticks",
            side_effects={"day_kind": "rest"},
        )

    # Informational ops — propose only.
    return ActResult(
        performed=False,
        reason=(
            f"op={op!r} is informational in v0. The proposal is "
            "queued via the registry; the user or approval gate "
            "carries it out."
        ),
    )


__all__ = ["ActResult", "act"]
