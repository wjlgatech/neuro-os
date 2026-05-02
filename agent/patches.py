"""
Structured patch operations for self-modification.

A ``Patch`` is a small, allowlisted, reversible operation on a specific
data file. Patches are the only way the self-modification loop is
allowed to change the codebase: free-form code edits are not permitted,
because their blast radius cannot be bounded.

Every operation:

* Has a hardcoded handler (no eval, no string interpolation into source).
* Refuses to run unless the target path is on the caller-supplied
  ``mutable_paths`` allowlist.
* Returns a ``Patch`` describing the inverse, so any single mutation can
  be rolled back deterministically.

Add a new op only if you are willing to defend the safety of every
caller that could trigger it.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class Patch:
    op: str
    payload: Dict[str, Any]
    target_path: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PatchResult:
    success: bool
    target_path: str
    inverse: Optional[Patch]
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "target_path": self.target_path,
            "inverse": self.inverse.to_dict() if self.inverse else None,
            "reason": self.reason,
        }


PRIORITY_RULES_RELATIVE = "agent/data/priority_rules.json"


def _read_rules(path: Path) -> List[List[str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [list(item) for item in json.load(f)]


def _write_rules(path: Path, rules: List[List[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
        f.write("\n")


def _resolve_target(repo_root: Path, target_path: str) -> Path:
    return repo_root / target_path


def _is_path_allowed(target_path: str, mutable_paths: List[str]) -> bool:
    return target_path in mutable_paths


def _apply_append_priority_rule(
    payload: Dict[str, Any],
    repo_root: Path,
) -> PatchResult:
    cue = (payload.get("cue") or "").strip().lower()
    mechanism = (payload.get("mechanism") or "").strip()
    if not cue or not mechanism:
        return PatchResult(
            success=False,
            target_path=PRIORITY_RULES_RELATIVE,
            inverse=None,
            reason="cue and mechanism are required",
        )
    target = _resolve_target(repo_root, PRIORITY_RULES_RELATIVE)
    rules = _read_rules(target)
    if [cue, mechanism] in rules:
        return PatchResult(
            success=False,
            target_path=PRIORITY_RULES_RELATIVE,
            inverse=None,
            reason="rule already present",
        )
    rules.append([cue, mechanism])
    _write_rules(target, rules)
    inverse = Patch(
        op="remove_priority_rule",
        payload={"cue": cue, "mechanism": mechanism},
        target_path=PRIORITY_RULES_RELATIVE,
        description=f"remove ({cue!r}, {mechanism!r})",
    )
    return PatchResult(
        success=True,
        target_path=PRIORITY_RULES_RELATIVE,
        inverse=inverse,
        reason=f"appended ({cue!r}, {mechanism!r})",
    )


def _apply_remove_priority_rule(
    payload: Dict[str, Any],
    repo_root: Path,
) -> PatchResult:
    cue = (payload.get("cue") or "").strip().lower()
    mechanism = (payload.get("mechanism") or "").strip()
    target = _resolve_target(repo_root, PRIORITY_RULES_RELATIVE)
    rules = _read_rules(target)
    pair = [cue, mechanism] if mechanism else None
    if pair and pair in rules:
        rules = [r for r in rules if r != pair]
        _write_rules(target, rules)
        inverse = Patch(
            op="append_priority_rule",
            payload={"cue": cue, "mechanism": mechanism},
            target_path=PRIORITY_RULES_RELATIVE,
            description=f"re-append ({cue!r}, {mechanism!r})",
        )
        return PatchResult(
            success=True,
            target_path=PRIORITY_RULES_RELATIVE,
            inverse=inverse,
            reason=f"removed ({cue!r}, {mechanism!r})",
        )
    if not mechanism:
        # Remove all rules with this cue
        removed = [r for r in rules if r and r[0] == cue]
        if not removed:
            return PatchResult(
                success=False,
                target_path=PRIORITY_RULES_RELATIVE,
                inverse=None,
                reason="no matching rules to remove",
            )
        rules = [r for r in rules if not (r and r[0] == cue)]
        _write_rules(target, rules)
        # Inverse re-appends every removed rule via a sequence of patches;
        # for the prototype we only support single-rule rollback, so flag.
        inverse = Patch(
            op="append_priority_rule",
            payload={"cue": cue, "mechanism": removed[0][1]},
            target_path=PRIORITY_RULES_RELATIVE,
            description=f"re-append first removed pair {removed[0]}",
        )
        return PatchResult(
            success=True,
            target_path=PRIORITY_RULES_RELATIVE,
            inverse=inverse,
            reason=f"removed {len(removed)} rules with cue {cue!r}",
        )
    return PatchResult(
        success=False,
        target_path=PRIORITY_RULES_RELATIVE,
        inverse=None,
        reason="rule not found",
    )


# Allowlist of patch handlers. Anything not in this dict is rejected.
ALLOWED_OPS: Dict[str, Callable[[Dict[str, Any], Path], PatchResult]] = {
    "append_priority_rule": _apply_append_priority_rule,
    "remove_priority_rule": _apply_remove_priority_rule,
}


def apply_patch(
    patch: Patch,
    repo_root: str | Path,
    mutable_paths: List[str],
) -> PatchResult:
    """Apply ``patch`` rooted at ``repo_root``, gated on ``mutable_paths``.

    ``repo_root`` is typically the live repo for promotion or a sandbox
    path during evaluation. The handler is selected from ``ALLOWED_OPS``;
    unknown ops are refused without touching the filesystem.
    """
    if patch.op not in ALLOWED_OPS:
        return PatchResult(
            success=False,
            target_path=patch.target_path,
            inverse=None,
            reason=f"op {patch.op!r} is not in ALLOWED_OPS",
        )
    if not _is_path_allowed(patch.target_path, mutable_paths):
        return PatchResult(
            success=False,
            target_path=patch.target_path,
            inverse=None,
            reason=f"target {patch.target_path!r} not in mutable_paths",
        )
    handler = ALLOWED_OPS[patch.op]
    return handler(patch.payload, Path(repo_root))


__all__ = [
    "Patch",
    "PatchResult",
    "ALLOWED_OPS",
    "PRIORITY_RULES_RELATIVE",
    "apply_patch",
]
