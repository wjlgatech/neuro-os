"""
Neuro-OS-specific patch ops, registered on top of flywheel-loop.

The substrate (``flywheel_loop.patches``) provides ``Patch``,
``PatchResult``, ``apply_patch``, ``ALLOWED_OPS``, and a handful of
generic JSON-list ops. This module adds two domain-flavored ops that
target ``agent/data/priority_rules.json``:

* ``append_priority_rule(cue, mechanism)``
* ``remove_priority_rule(cue, mechanism)``

These are convenience wrappers around the generic
``json_append_to_list`` / ``json_remove_from_list`` so callers can use
domain-meaningful payload keys.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

# Re-export the substrate primitives so existing imports continue to work.
from flywheel_loop.patches import (
    ALLOWED_OPS,
    Patch,
    PatchResult,
    apply_patch,
    register_op,
)

PRIORITY_RULES_RELATIVE = "agent/data/priority_rules.json"


def _read_rules(target: Path):
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8") as f:
        return [list(item) for item in json.load(f)]


def _write_rules(target: Path, items) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
        f.write("\n")


def _apply_append_priority_rule(
    payload: Dict[str, Any],
    repo_root: Path,
    target_path: str,
) -> PatchResult:
    cue = (payload.get("cue") or "").strip().lower()
    mechanism = (payload.get("mechanism") or "").strip()
    if not cue or not mechanism:
        return PatchResult(
            success=False,
            target_path=target_path,
            inverse=None,
            reason="cue and mechanism are required",
        )
    target = repo_root / target_path
    rules = _read_rules(target)
    if [cue, mechanism] in rules:
        return PatchResult(
            success=False,
            target_path=target_path,
            inverse=None,
            reason="rule already present",
        )
    rules.append([cue, mechanism])
    _write_rules(target, rules)
    return PatchResult(
        success=True,
        target_path=target_path,
        inverse=Patch(
            op="remove_priority_rule",
            payload={"cue": cue, "mechanism": mechanism},
            target_path=target_path,
            description=f"remove ({cue!r}, {mechanism!r})",
        ),
        reason=f"appended ({cue!r}, {mechanism!r})",
    )


def _apply_remove_priority_rule(
    payload: Dict[str, Any],
    repo_root: Path,
    target_path: str,
) -> PatchResult:
    cue = (payload.get("cue") or "").strip().lower()
    mechanism = (payload.get("mechanism") or "").strip()
    target = repo_root / target_path
    rules = _read_rules(target)
    pair = [cue, mechanism] if mechanism else None
    if pair and pair in rules:
        rules = [r for r in rules if r != pair]
        _write_rules(target, rules)
        return PatchResult(
            success=True,
            target_path=target_path,
            inverse=Patch(
                op="append_priority_rule",
                payload={"cue": cue, "mechanism": mechanism},
                target_path=target_path,
                description=f"re-append ({cue!r}, {mechanism!r})",
            ),
            reason=f"removed ({cue!r}, {mechanism!r})",
        )
    if not mechanism:
        removed = [r for r in rules if r and r[0] == cue]
        if not removed:
            return PatchResult(
                success=False,
                target_path=target_path,
                inverse=None,
                reason="no matching rules to remove",
            )
        rules = [r for r in rules if not (r and r[0] == cue)]
        _write_rules(target, rules)
        return PatchResult(
            success=True,
            target_path=target_path,
            inverse=Patch(
                op="append_priority_rule",
                payload={"cue": cue, "mechanism": removed[0][1]},
                target_path=target_path,
                description=f"re-append first removed pair {removed[0]}",
            ),
            reason=f"removed {len(removed)} rules with cue {cue!r}",
        )
    return PatchResult(
        success=False,
        target_path=target_path,
        inverse=None,
        reason="rule not found",
    )


# Idempotent registration: these op names are unique to neuro-os and
# don't collide with the substrate's generic JSON-list ops.
if "append_priority_rule" not in ALLOWED_OPS:
    register_op("append_priority_rule", _apply_append_priority_rule)
if "remove_priority_rule" not in ALLOWED_OPS:
    register_op("remove_priority_rule", _apply_remove_priority_rule)


__all__ = [
    "Patch",
    "PatchResult",
    "ALLOWED_OPS",
    "PRIORITY_RULES_RELATIVE",
    "apply_patch",
]
