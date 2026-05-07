"""
``priorities.py`` — daily priority management with explicit evidence.

A ``Priority`` is the unit of "what's done today." The crucial design
choice is that ``evidence_type`` is a fixed enum, not free-text — at 3pm,
today-self cannot redefine "done" to mean whatever they want.

Three operations:

* ``MAX_PRIORITIES_WARN`` — five priorities is the soft cap. The morning
  ritual surfaces a warning past this so the contract doesn't degrade
  into a scroll.
* ``mark_evidenced(priority, proof)`` — flip the priority to the
  ``evidenced`` status with a verified proof string.
* ``verify_evidence(priority, repo_root, proof)`` — best-effort
  verification that the proof matches the evidence_type. v0 ships
  string-shape checks; v1 will hook into git/GitHub APIs.

The actual storage of priorities lives on ``Contract`` (``contract.py``);
this module is the type + helper layer.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from agent.founder_loop.state import EvidenceType, Priority, PriorityStatus


MAX_PRIORITIES_WARN = 5

# Soft validators per evidence_type: minimal shape checks that catch
# obvious self-deception (target='done' for evidence_type='pr_merged'
# wouldn't satisfy this). Full verification (querying GitHub) is v0.5.
_SHAPE_RES = {
    "commit_pushed": re.compile(r"^[0-9a-f]{7,40}$|^\d+_commits$|^\d+_commit$", re.I),
    "pr_opened": re.compile(r"#\d+|/pull/\d+", re.I),
    "pr_merged": re.compile(r"#\d+|/pull/\d+", re.I),
    "doc_published": re.compile(r"^https?://|\.md$|\.html$|published", re.I),
    "count_reached": re.compile(r"^\d+", re.I),
    "human_signoff": re.compile(r"signoff:|approved:|@\w+", re.I),
    "artifact_uploaded": re.compile(r"^https?://|s3://|gs://|\.zip$|\.tar", re.I),
}


def warn_if_over_capacity(priorities: list[Priority]) -> Optional[str]:
    """Return a warning string when there are too many priorities, else None.

    The morning ritual prints the warning but doesn't block. Today-self
    can still proceed; the morning_ritual_prompt golden later catches
    chronic over-ambition.
    """
    if len(priorities) > MAX_PRIORITIES_WARN:
        return (
            f"Contract has {len(priorities)} priorities. "
            f"Most days only support 3-5; over {MAX_PRIORITIES_WARN} risks "
            "afternoon-despair-as-escape (the contract becomes a source of "
            "distraction-fuel rather than focus). Recommend pruning to top "
            f"{MAX_PRIORITIES_WARN} or fewer."
        )
    return None


def verify_evidence_shape(
    priority: Priority, proof: str
) -> tuple[bool, Optional[str]]:
    """Best-effort shape check that ``proof`` could satisfy
    ``priority.evidence_type``.

    Returns ``(passed, reason)``. Passed=True means the shape is plausible
    (a real verification step would now hit git/GitHub). Passed=False
    means the proof obviously doesn't match the evidence_type — surface
    this to the user before flipping ``status``.

    This is the v0 anti-self-deception layer. v0.5 hooks into real
    verifiers (``git log --grep``, GitHub PR API).
    """
    proof = (proof or "").strip()
    if not proof:
        return False, "proof is empty"
    pattern = _SHAPE_RES.get(priority.evidence_type)
    if pattern is None:
        # Unknown evidence_type would have failed Pydantic validation
        # already, so this is only reachable if the catalog grows.
        return True, None
    if pattern.search(proof):
        return True, None
    return False, (
        f"proof '{proof}' does not match the expected shape for "
        f"evidence_type='{priority.evidence_type}'. Examples that would "
        f"match: {_evidence_examples(priority.evidence_type)}"
    )


def _evidence_examples(evidence_type: EvidenceType) -> str:
    return {
        "commit_pushed": "'a1b2c3d', '2_commits'",
        "pr_opened": "'#142', 'github.com/foo/bar/pull/142'",
        "pr_merged": "'#142', 'github.com/foo/bar/pull/142'",
        "doc_published": "'https://...', '/path/to.md'",
        "count_reached": "'5', '120_pages'",
        "human_signoff": "'signoff: @alice', 'approved: lead-eng'",
        "artifact_uploaded": "'https://s3...', '/build/release.tar.gz'",
    }[evidence_type]


def mark_evidenced(priority: Priority, proof: str, *, when: Optional[datetime] = None) -> Priority:
    """Return a copy of ``priority`` with status='evidenced'.

    Validates the proof shape; raises ``ValueError`` on shape mismatch.
    The caller is expected to surface the error to the user rather than
    silently overriding (that would defeat the anti-self-deception goal).
    """
    passed, reason = verify_evidence_shape(priority, proof)
    if not passed:
        raise ValueError(reason)
    return priority.model_copy(
        update={
            "status": "evidenced",
            "evidenced_at": when or datetime.now(timezone.utc),
            "evidence_proof": proof,
        }
    )


def mark_status(priority: Priority, status: PriorityStatus) -> Priority:
    """Return a copy of ``priority`` with the new status (no proof check).

    Used for ``in_progress`` / ``abandoned`` transitions where there's
    no proof to verify. Flipping to ``evidenced`` via this function is
    not allowed — call ``mark_evidenced`` instead so the proof check
    cannot be bypassed.
    """
    if status == "evidenced":
        raise ValueError(
            "use mark_evidenced(priority, proof) — the evidenced "
            "status requires a verified proof string"
        )
    return priority.model_copy(update={"status": status})


__all__ = [
    "MAX_PRIORITIES_WARN",
    "warn_if_over_capacity",
    "verify_evidence_shape",
    "mark_evidenced",
    "mark_status",
]
