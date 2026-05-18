"""
Tests for agent.status — the STATUS.md auto-sync pipeline.

Covers:
* PlanStamp Pydantic validation (taxonomy + extras-forbidden)
* walker frontmatter parsing + malformed-stamp detection
* git_recent parses git log output
* render builds deterministic markdown (idempotent)
* CLI: `neuro-os status` + `--sync`
* `scripts/sync_status.py --check` exits 1 when out of sync
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.status import (
    NorthStarConfig,
    PlanStamp,
    RecentShip,
    build_status_markdown,
    get_recent_ships,
    walk_stamped_plans,
)
from agent.status.render import DEFAULT_CONFIG
from agent.status.stamp import StampedPlan
from agent.status.walker import _split_frontmatter, SKIP_NAMES


# ---------------------------------------------------------------------------
# PlanStamp — schema invariants
# ---------------------------------------------------------------------------


def test_plan_stamp_accepts_minimal_active():
    stamp = PlanStamp(status="active", parent="phase-1-paper")
    assert stamp.status == "active"
    assert stamp.parent == "phase-1-paper"
    assert stamp.acceptance is None
    assert stamp.reason is None


def test_plan_stamp_rejects_unknown_status():
    with pytest.raises(ValidationError):
        PlanStamp(status="in-progress", parent="phase-1-paper")  # type: ignore[arg-type]


def test_plan_stamp_rejects_unknown_parent():
    with pytest.raises(ValidationError):
        PlanStamp(status="active", parent="phase-2-something")  # type: ignore[arg-type]


def test_plan_stamp_rejects_extra_fields():
    """extra='forbid' — typos in stamps must raise, not silently drop."""
    with pytest.raises(ValidationError):
        PlanStamp.model_validate({
            "status": "active",
            "parent": "infra",
            "acceptence": "typo",  # note: 'acceptence' not 'acceptance'
        })


def test_plan_stamp_is_frozen():
    stamp = PlanStamp(status="parked", parent="infra")
    with pytest.raises(ValidationError):
        stamp.status = "active"  # type: ignore[misc]


def test_plan_stamp_accepts_all_status_values():
    for s in ("active", "parked", "done", "abandoned"):
        PlanStamp(status=s, parent="infra")  # type: ignore[arg-type]


def test_plan_stamp_accepts_all_parent_values():
    for p in ("phase-1-paper", "phase-3-moonshot", "invest", "infra", "other"):
        PlanStamp(status="active", parent=p)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Walker — frontmatter parsing
# ---------------------------------------------------------------------------


def test_split_frontmatter_basic():
    text = "---\nstatus: active\nparent: infra\n---\n# Title\n\nbody"
    fm, body = _split_frontmatter(text)
    assert fm == {"status": "active", "parent": "infra"}
    assert body.startswith("# Title")


def test_split_frontmatter_no_delimiter():
    text = "# Title\n\nbody"
    fm, body = _split_frontmatter(text)
    assert fm is None
    assert body == text


def test_split_frontmatter_unclosed_delimiter():
    """A `---` opener with no closer = no frontmatter, full text returned."""
    text = "---\nstatus: active\n# Title\n\nbody"
    fm, body = _split_frontmatter(text)
    assert fm is None


def test_split_frontmatter_malformed_yaml():
    """Broken YAML inside the delimiters returns None, not raise."""
    text = "---\nstatus: [unclosed\n---\n# Title"
    fm, _ = _split_frontmatter(text)
    assert fm is None


def test_walker_finds_stamped_files(tmp_path):
    docs = tmp_path / "docs"
    plans = docs / "plans"
    plans.mkdir(parents=True)
    (plans / "active.md").write_text(
        "---\nstatus: active\nparent: phase-1-paper\nacceptance: do it\n---\n# Active Plan\n"
    )
    (plans / "parked.md").write_text(
        "---\nstatus: parked\nparent: infra\nreason: blocked\n---\n# Parked Plan\n"
    )
    result = walk_stamped_plans(docs, quiet=True)
    assert len(result) == 2
    titles = {r.title for r in result}
    assert titles == {"Active Plan", "Parked Plan"}


def test_walker_skips_unstamped_files(tmp_path, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "unstamped.md").write_text("# No frontmatter\n\nplain markdown")
    result = walk_stamped_plans(docs, quiet=False)
    assert result == []
    err = capsys.readouterr().err
    assert "no frontmatter" in err


def test_walker_skips_status_md_itself(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "STATUS.md").write_text(
        "---\nstatus: active\nparent: infra\n---\n# Status\n"
    )
    (docs / "real.md").write_text(
        "---\nstatus: active\nparent: infra\n---\n# Real Plan\n"
    )
    result = walk_stamped_plans(docs, quiet=True)
    assert len(result) == 1
    assert result[0].title == "Real Plan"


def test_walker_raises_on_malformed_stamp(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "bad.md").write_text(
        "---\nstatus: not-a-real-status\nparent: infra\n---\n# Bad\n"
    )
    with pytest.raises(ValueError, match="malformed stamp"):
        walk_stamped_plans(docs, quiet=True)


def test_walker_skip_names_includes_known_reference_docs():
    """Sanity check: don't accidentally include reference docs."""
    for name in (
        "STATUS.md",
        "AI_NATIVE_ENGINEERING_PRINCIPLES.md",
        "how-it-works.md",
        "how-to-use-it.md",
        "what-is-this.md",
    ):
        assert name in SKIP_NAMES


# ---------------------------------------------------------------------------
# git_recent
# ---------------------------------------------------------------------------


def test_recent_ship_validates_short_sha():
    with pytest.raises(ValidationError):
        RecentShip(sha="abc", date=date(2026, 5, 18), subject="x")


def test_recent_ship_validates_subject_required():
    with pytest.raises(ValidationError):
        RecentShip(sha="abc1234", date=date(2026, 5, 18), subject="")


def test_get_recent_ships_returns_list_in_real_repo():
    """In this repo (which has commits), we should get rows."""
    rows = get_recent_ships(limit=3)
    assert isinstance(rows, list)
    assert len(rows) <= 3
    if rows:
        assert all(isinstance(r, RecentShip) for r in rows)


def test_get_recent_ships_empty_in_blank_repo(tmp_path):
    """Fresh `git init` with no commits → []."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert get_recent_ships(cwd=tmp_path, limit=3) == []


# ---------------------------------------------------------------------------
# Render — pure-function determinism
# ---------------------------------------------------------------------------


def _sample_plans(tmp_docs):
    """A minimal StampedPlan set for render tests."""
    return [
        StampedPlan(
            path=tmp_docs / "plans/active.md",
            title="Active Plan",
            stamp=PlanStamp(
                status="active", parent="phase-1-paper",
                acceptance="ship it by Friday",
            ),
            last_touched=date(2026, 5, 18),
        ),
        StampedPlan(
            path=tmp_docs / "plans/parked.md",
            title="Parked Plan",
            stamp=PlanStamp(
                status="parked", parent="infra",
                reason="blocked on Phase-1 push",
            ),
            last_touched=date(2026, 5, 1),
        ),
        StampedPlan(
            path=tmp_docs / "plans/done.md",
            title="Done Plan",
            stamp=PlanStamp(status="done", parent="invest"),
            last_touched=date(2026, 5, 12),
        ),
    ]


def test_render_is_idempotent(tmp_path):
    docs = tmp_path / "docs"
    plans = _sample_plans(docs)
    ships = [RecentShip(sha="abc1234", date=date(2026, 5, 18), subject="test")]
    out1 = build_status_markdown(
        plans=plans, recent=ships, config=DEFAULT_CONFIG,
        docs_root=docs, today=date(2026, 5, 18),
    )
    out2 = build_status_markdown(
        plans=plans, recent=ships, config=DEFAULT_CONFIG,
        docs_root=docs, today=date(2026, 5, 18),
    )
    assert out1 == out2


def test_render_includes_north_star(tmp_path):
    out = build_status_markdown(
        plans=[], recent=[], config=DEFAULT_CONFIG,
        docs_root=tmp_path / "docs", today=date(2026, 5, 18),
    )
    assert "neuro-os" in out
    assert "Phase 1" in out
    assert "Phase 3" in out


def test_render_groups_by_parent(tmp_path):
    docs = tmp_path / "docs"
    out = build_status_markdown(
        plans=_sample_plans(docs), recent=[], config=DEFAULT_CONFIG,
        docs_root=docs, today=date(2026, 5, 18),
    )
    assert "Active Plan" in out
    assert "Parked Plan" in out
    assert "Done Plan" in out
    # Active section header present
    assert "## Active this week" in out
    assert "## Parked but real" in out
    assert "## Done this cycle" in out


def test_render_handles_empty_state(tmp_path):
    """No plans + no ships still produces a valid markdown."""
    out = build_status_markdown(
        plans=[], recent=[], config=DEFAULT_CONFIG,
        docs_root=tmp_path / "docs", today=date(2026, 5, 18),
    )
    assert "neuro-os" in out
    assert "nothing marked status=active" in out
    assert "nothing parked" in out
    assert "no commits yet" in out


def test_render_omits_done_section_when_no_done(tmp_path):
    plans = [_sample_plans(tmp_path / "docs")[0]]  # only the active one
    out = build_status_markdown(
        plans=plans, recent=[], config=DEFAULT_CONFIG,
        docs_root=tmp_path / "docs", today=date(2026, 5, 18),
    )
    assert "## Done this cycle" not in out


def test_north_star_config_is_frozen():
    cfg = NorthStarConfig(
        one_sentence="x", weekly_ritual_lines=["a"], not_happening_lines=[],
    )
    with pytest.raises(ValidationError):
        cfg.one_sentence = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# sync_status.py CLI
# ---------------------------------------------------------------------------


_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync_status.py"
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_script(*args: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True, text=True, timeout=30,
        cwd=str(cwd) if cwd else None,
    )


def test_sync_status_write_creates_file(tmp_path):
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    # No plan files → empty state, but the file should still be created.
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    proc = _run_script("--write", "--repo-root", str(repo), "--quiet")
    assert proc.returncode == 0, proc.stderr
    assert (docs / "STATUS.md").exists()
    assert "neuro-os" in (docs / "STATUS.md").read_text()


def test_sync_status_check_passes_when_in_sync():
    """In this repo, after running --write, --check should pass."""
    proc_write = _run_script("--write", "--quiet")
    assert proc_write.returncode == 0, proc_write.stderr
    proc_check = _run_script("--check", "--quiet")
    assert proc_check.returncode == 0, (
        f"Expected --check to pass right after --write. stderr:\n{proc_check.stderr}"
    )


def test_sync_status_check_fails_when_out_of_sync(tmp_path):
    """Hand-corrupt STATUS.md and verify --check fails."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    _run_script("--write", "--repo-root", str(repo), "--quiet")
    (docs / "STATUS.md").write_text("this is hand-edited and stale\n")
    proc = _run_script("--check", "--repo-root", str(repo), "--quiet")
    assert proc.returncode == 1
    assert "stale" in proc.stderr.lower()


def test_sync_status_print_emits_to_stdout(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    proc = _run_script("--print", "--repo-root", str(repo), "--quiet")
    assert proc.returncode == 0
    assert "neuro-os" in proc.stdout
    assert not (repo / "docs" / "STATUS.md").exists()  # didn't write


# ---------------------------------------------------------------------------
# `neuro-os status` CLI subcommand
# ---------------------------------------------------------------------------


def test_status_cli_prints_existing_file():
    """`neuro-os status` (no --sync) prints whatever's in docs/STATUS.md."""
    proc = subprocess.run(
        [sys.executable, "-m", "agent", "status", "--repo-root", str(_REPO_ROOT)],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    assert "neuro-os" in proc.stdout


def test_status_cli_with_sync_regenerates(tmp_path):
    """`neuro-os status --sync` builds the file fresh, then prints it."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    proc = subprocess.run(
        [sys.executable, "-m", "agent", "status", "--sync",
         "--repo-root", str(repo)],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    assert (repo / "docs" / "STATUS.md").exists()
    assert "neuro-os" in proc.stdout


def test_status_cli_no_file_no_sync_returns_error(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    proc = subprocess.run(
        [sys.executable, "-m", "agent", "status", "--repo-root", str(repo)],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 2
    assert "does not exist" in proc.stderr
