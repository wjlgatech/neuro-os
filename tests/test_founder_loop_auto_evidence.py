"""Tests for agent/founder_loop/auto_evidence.py.

Subprocess calls (`gh`, `git`) are mocked so the tests don't depend on
network, GitHub auth, or the local git history.
"""
from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

from agent.founder_loop.auto_evidence import (
    _parse_pr_target,
    auto_check_priorities,
)
from agent.founder_loop.state import Priority


def _proposed(
    title: str = "ship daemon UI",
    evidence_type: str = "pr_merged",
    evidence_target: str = "neuro-os#44",
    weight: int = 3,
) -> Priority:
    return Priority(
        title=title,
        evidence_type=evidence_type,
        evidence_target=evidence_target,
        weight=weight,
    )


# ---------------------------------------------------------------------------
# _parse_pr_target
# ---------------------------------------------------------------------------

def test_parse_pr_target_owner_repo_hash() -> None:
    assert _parse_pr_target("anthropics/claude-code#142") == (
        "anthropics/claude-code", 142,
    )


def test_parse_pr_target_repo_hash_only() -> None:
    repo, num = _parse_pr_target("neuro-os#999")
    assert repo is None
    assert num == 999


def test_parse_pr_target_hash_only() -> None:
    assert _parse_pr_target("#44") == (None, 44)


def test_parse_pr_target_github_url() -> None:
    assert _parse_pr_target("https://github.com/wjlgatech/neuro-os/pull/44") == (
        "wjlgatech/neuro-os", 44,
    )


def test_parse_pr_target_garbage_returns_none() -> None:
    assert _parse_pr_target("not-a-pr") == (None, None)
    assert _parse_pr_target("") == (None, None)


# ---------------------------------------------------------------------------
# auto_check_priorities — happy paths
# ---------------------------------------------------------------------------

def _gh_run(state: str = "MERGED", url: str = "https://github.com/x/y/pull/1"):
    """Build a fake subprocess.run result returning gh JSON output."""
    def _fake(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=0,
            stdout=json.dumps({"state": state, "url": url}),
            stderr="",
        )
    return _fake


def test_auto_check_flips_when_pr_merged() -> None:
    p = _proposed()
    with patch("subprocess.run", side_effect=_gh_run("MERGED")):
        updated, flipped = auto_check_priorities([p])
    assert flipped == 1
    assert updated[0].status == "evidenced"
    assert updated[0].evidence_proof == "https://github.com/x/y/pull/1"


def test_auto_check_does_not_flip_when_pr_open() -> None:
    p = _proposed(evidence_type="pr_merged")
    with patch("subprocess.run", side_effect=_gh_run("OPEN")):
        updated, flipped = auto_check_priorities([p])
    assert flipped == 0
    assert updated[0].status == "pending"


def test_auto_check_pr_opened_accepts_any_state() -> None:
    p = _proposed(evidence_type="pr_opened")
    with patch("subprocess.run", side_effect=_gh_run("OPEN")):
        updated, flipped = auto_check_priorities([p])
    assert flipped == 1
    assert updated[0].status == "evidenced"


def test_auto_check_skips_already_evidenced() -> None:
    p = _proposed().model_copy(
        update={"status": "evidenced", "evidence_proof": "#1"}
    )
    with patch("subprocess.run") as run:
        updated, flipped = auto_check_priorities([p])
    assert flipped == 0
    assert run.call_count == 0  # subprocess never invoked
    assert updated[0].status == "evidenced"


# ---------------------------------------------------------------------------
# Failure modes — best-effort means "never raise"
# ---------------------------------------------------------------------------

def test_auto_check_gh_not_installed_leaves_priorities_unchanged() -> None:
    p = _proposed()
    with patch("subprocess.run", side_effect=FileNotFoundError("gh: not found")):
        updated, flipped = auto_check_priorities([p])
    assert flipped == 0
    assert updated[0].status == "pending"


def test_auto_check_gh_nonzero_exit_leaves_unchanged() -> None:
    p = _proposed()

    def _failing(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=1, stdout="", stderr="HTTP 404",
        )

    with patch("subprocess.run", side_effect=_failing):
        updated, flipped = auto_check_priorities([p])
    assert flipped == 0


def test_auto_check_gh_timeout_leaves_unchanged() -> None:
    p = _proposed()
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=10),
    ):
        updated, flipped = auto_check_priorities([p])
    assert flipped == 0


def test_auto_check_gh_returns_malformed_json_leaves_unchanged() -> None:
    p = _proposed()

    def _bad_json(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="not-json", stderr="",
        )

    with patch("subprocess.run", side_effect=_bad_json):
        updated, flipped = auto_check_priorities([p])
    assert flipped == 0


# ---------------------------------------------------------------------------
# evidence_type dispatch
# ---------------------------------------------------------------------------

def test_auto_check_unsupported_evidence_type_returns_unchanged() -> None:
    # doc_published has no auto-detector
    p = _proposed(
        evidence_type="doc_published",
        evidence_target="https://example.com/post.md",
    )
    with patch("subprocess.run") as run:
        updated, flipped = auto_check_priorities([p])
    assert flipped == 0
    assert run.call_count == 0


def test_auto_check_commit_pushed_flips_when_git_verify_succeeds() -> None:
    p = _proposed(evidence_type="commit_pushed", evidence_target="a1b2c3d")

    def _git_ok(args, **kwargs):
        # git rev-parse returns the full SHA
        return subprocess.CompletedProcess(
            args=args, returncode=0,
            stdout="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0\n",
            stderr="",
        )

    with patch("subprocess.run", side_effect=_git_ok):
        updated, flipped = auto_check_priorities([p])
    assert flipped == 1
    assert updated[0].status == "evidenced"
    # Proof is the short SHA — verify_evidence_shape accepts 7-40 hex chars
    assert updated[0].evidence_proof == "a1b2c3d4e5f6"
