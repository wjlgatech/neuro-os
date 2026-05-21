"""Auto-evidence: poll external systems to detect when a priority's
evidence_target has been satisfied (PR merged, PR opened, commit pushed).

Best-effort by design. Every check wraps `gh`/`git` subprocess calls in a
guard that swallows failures (missing CLI, auth error, network, timeout)
and returns ``None`` — the priority stays in its current state. The tank
recomputes next tick, no harm done.

v0.5 scope: pr_merged, pr_opened, commit_pushed. The remaining evidence
types (doc_published, count_reached, human_signoff, artifact_uploaded)
have no clean auto-detector and remain manual via ``loop evidence``.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from agent.founder_loop.priorities import mark_evidenced
from agent.founder_loop.state import Priority

log = logging.getLogger("founder_loop.auto_evidence")


def auto_check_priorities(
    priorities: List[Priority],
    *,
    now: Optional[datetime] = None,
) -> Tuple[List[Priority], int]:
    """Walk priorities; for each non-evidenced one, attempt auto-detection.

    Returns ``(updated_priorities, num_flipped)``. Best-effort: any failure
    in the underlying subprocess leaves the priority unchanged.
    """
    now = now or datetime.now(timezone.utc)
    updated: List[Priority] = []
    flipped = 0
    for p in priorities:
        if p.status == "evidenced":
            updated.append(p)
            continue
        proof = _check_priority(p)
        if proof is None:
            updated.append(p)
            continue
        try:
            updated.append(mark_evidenced(p, proof, when=now))
            flipped += 1
            log.info(
                "auto-evidence: priority %r flipped to evidenced (proof=%s)",
                p.title, proof,
            )
        except ValueError as e:
            log.warning(
                "auto-evidence: shape check rejected proof %r for %r: %s",
                proof, p.title, e,
            )
            updated.append(p)
    return updated, flipped


def _check_priority(priority: Priority) -> Optional[str]:
    """Dispatch by evidence_type. Returns a proof string when satisfied."""
    target = priority.evidence_target
    et = priority.evidence_type
    if et == "pr_merged":
        return _check_pr(target, require_merged=True)
    if et == "pr_opened":
        return _check_pr(target, require_merged=False)
    if et == "commit_pushed":
        return _check_commit_pushed(target)
    return None  # other types: manual only


def _check_pr(target: str, *, require_merged: bool) -> Optional[str]:
    repo, number = _parse_pr_target(target)
    if number is None:
        return None
    args = ["gh", "pr", "view", str(number), "--json", "state,url"]
    if repo:
        args.extend(["--repo", repo])
    out = _run_cmd(args)
    if out is None:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    state = (data.get("state") or "").upper()
    url = data.get("url") or f"#{number}"
    if require_merged:
        if state == "MERGED":
            return url
        return None
    # pr_opened: any state means the PR exists
    return url if state else None


def _check_commit_pushed(target: str) -> Optional[str]:
    """Verify a commit SHA exists in the local repo via git rev-parse."""
    if not re.match(r"^[0-9a-f]{7,40}$", target or "", re.I):
        return None
    out = _run_cmd(["git", "rev-parse", "--verify", target])
    if out is None:
        return None
    full = out.strip()
    if re.match(r"^[0-9a-f]{40}$", full, re.I):
        return full[:12]
    return None


_PR_URL_RE = re.compile(r"github\.com/([^/]+/[^/]+)/pull/(\d+)")
_OWNER_REPO_HASH_RE = re.compile(r"^([\w.-]+/[\w.-]+)#(\d+)$")
_REPO_HASH_RE = re.compile(r"^([\w.-]+)#(\d+)$")
_HASH_ONLY_RE = re.compile(r"^#(\d+)$")


def _parse_pr_target(target: str) -> Tuple[Optional[str], Optional[int]]:
    """Parse an evidence_target into ``(repo, pr_number)``.

    Supported shapes:
        "owner/repo#123"                       → ("owner/repo", 123)
        "https://github.com/owner/repo/pull/4" → ("owner/repo", 4)
        "reponame#123"                         → (None, 123)  # gh uses CWD repo
        "#123"                                 → (None, 123)
    """
    if not target:
        return None, None
    m = _PR_URL_RE.search(target)
    if m:
        return m.group(1), int(m.group(2))
    m = _OWNER_REPO_HASH_RE.match(target)
    if m:
        return m.group(1), int(m.group(2))
    m = _REPO_HASH_RE.match(target)
    if m:
        return None, int(m.group(2))
    m = _HASH_ONLY_RE.match(target)
    if m:
        return None, int(m.group(1))
    return None, None


def _run_cmd(args: List[str]) -> Optional[str]:
    """Run a subprocess; return stdout on success, None on any failure."""
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning("auto-evidence: %s failed (%s)", args[0], e)
        return None
    except OSError as e:
        log.warning("auto-evidence: %s failed (%s)", args[0], e)
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


__all__ = ["auto_check_priorities"]
