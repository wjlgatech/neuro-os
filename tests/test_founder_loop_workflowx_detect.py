"""
Tests for the workflowx auto-detect module.

Detection precedence: explicit > env > platform-specific known
directories > repo-local > fallback. Every test forces a platform via
the ``platform=`` kwarg and uses ``home=`` to redirect ``Path.home()``
so CI runs deterministically regardless of the host.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from agent.founder_loop.workflowx_detect import (
    candidate_directories,
    detect_workflowx_export,
    newest_jsonl_in,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _touch_jsonl(parent: Path, name: str, mtime: float | None = None) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    path = parent / name
    path.write_text(
        '{"timestamp":"2026-05-06T14:00:00+00:00",'
        '"distraction_minutes":5,"deep_work_minutes":40,'
        '"context_switches":2}\n',
        encoding="utf-8",
    )
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_explicit_path_always_wins(tmp_path):
    """An explicit path overrides every other branch."""
    explicit = tmp_path / "explicit.jsonl"
    fallback = tmp_path / "fallback.jsonl"
    # Even with an env var also set, explicit wins.
    result = detect_workflowx_export(
        explicit=explicit,
        env_override=str(tmp_path / "env.jsonl"),
        fallback=fallback,
        platform="linux",
        home=tmp_path,
    )
    assert result.source == "explicit"
    assert result.path == explicit
    assert result.is_real is True


def test_env_var_wins_over_platform_paths(tmp_path):
    """``env_override`` is honored when no explicit path is given."""
    # Populate a known platform path that would normally win.
    populated_dir = tmp_path / ".config" / "workflowx" / "exports"
    _touch_jsonl(populated_dir, "today.jsonl")
    # Env var points at a different file (a directory, in this case).
    env_dir = tmp_path / "env-exports"
    env_file = _touch_jsonl(env_dir, "env-today.jsonl")

    result = detect_workflowx_export(
        env_override=str(env_dir),
        fallback=tmp_path / "fallback.jsonl",
        platform="linux",
        home=tmp_path,
    )
    assert result.source == "env"
    assert result.path == env_file
    assert result.is_real is True


def test_finds_newest_jsonl_in_directory(tmp_path):
    """Multiple .jsonl files → newest mtime wins."""
    target = tmp_path / ".workflowx" / "exports"
    older = _touch_jsonl(target, "monday.jsonl", mtime=time.time() - 86400 * 2)
    newer = _touch_jsonl(target, "today.jsonl", mtime=time.time())
    middle = _touch_jsonl(target, "yesterday.jsonl", mtime=time.time() - 86400)

    found = newest_jsonl_in(target)
    assert found == newer
    assert found != older
    assert found != middle


def test_skips_empty_directory_then_finds_next(tmp_path):
    """First candidate empty, second populated → returns second."""
    empty = tmp_path / ".config" / "workflowx" / "exports"
    empty.mkdir(parents=True)
    populated = tmp_path / ".local" / "share" / "workflowx" / "exports"
    real_file = _touch_jsonl(populated, "today.jsonl")

    result = detect_workflowx_export(
        fallback=tmp_path / "fallback.jsonl",
        platform="linux",
        home=tmp_path,
    )
    assert result.source == "linux:xdg-data"
    assert result.path == real_file
    assert result.is_real is True


def test_skips_missing_directory(tmp_path):
    """No directories exist; final candidate populated → finds it."""
    populated = tmp_path / ".workflowx" / "exports"
    real_file = _touch_jsonl(populated, "today.jsonl")

    result = detect_workflowx_export(
        fallback=tmp_path / "fallback.jsonl",
        platform="linux",
        home=tmp_path,
    )
    assert result.source == "linux:dot-workflowx"
    assert result.path == real_file


def test_falls_back_when_nothing_found(tmp_path):
    """Every candidate absent → fallback with is_real=False."""
    fallback = tmp_path / ".founder_loop" / "workflowx.jsonl"

    result = detect_workflowx_export(
        fallback=fallback,
        platform="linux",
        home=tmp_path,
        cwd=tmp_path,  # Empty cwd ensures repo-local doesn't match either.
    )
    assert result.source == "fallback"
    assert result.path == fallback
    assert result.is_real is False
    assert "not detected" in result.note.lower()


def test_repo_local_matches_when_known_paths_empty(tmp_path):
    """A workflowx.jsonl in cwd is detected as ``repo-local``."""
    real_file = tmp_path / "workflowx.jsonl"
    real_file.write_text("", encoding="utf-8")

    result = detect_workflowx_export(
        fallback=tmp_path / "fallback.jsonl",
        platform="linux",
        home=tmp_path / "noop_home",  # No matches in known paths.
        cwd=tmp_path,
    )
    assert result.source == "repo-local"
    assert result.path == real_file


def test_candidate_paths_per_platform(tmp_path):
    """Each platform returns the documented ordered list."""
    home = tmp_path

    macos = candidate_directories("macos", home=home)
    macos_paths = [p for p, _ in macos]
    assert (home / "Library" / "Application Support" / "workflowx" / "exports") in macos_paths
    assert (home / ".workflowx" / "exports") in macos_paths
    assert macos_paths[0] == home / "Library" / "Application Support" / "workflowx" / "exports"

    linux = candidate_directories("linux", home=home)
    linux_sources = [s for _, s in linux]
    assert linux_sources == [
        "linux:xdg-config",
        "linux:xdg-data",
        "linux:dot-workflowx",
    ]
    assert linux[0][0] == home / ".config" / "workflowx" / "exports"
    assert linux[1][0] == home / ".local" / "share" / "workflowx" / "exports"
    assert linux[2][0] == home / ".workflowx" / "exports"


def test_unknown_platform_returns_no_candidates(tmp_path):
    """Unknown platform falls all the way through to fallback."""
    result = detect_workflowx_export(
        fallback=tmp_path / "fallback.jsonl",
        platform="unknown",
        home=tmp_path,
        cwd=tmp_path / "no-cwd",  # Avoids repo-local picking up real cwd files.
    )
    assert result.source == "fallback"
    assert result.is_real is False


def test_detection_result_is_frozen_dataclass(tmp_path):
    """``DetectionResult`` is immutable so callers can't mutate the
    label after the fact."""
    result = detect_workflowx_export(
        fallback=tmp_path / "fallback.jsonl",
        platform="linux",
        home=tmp_path,
        cwd=tmp_path / "no-cwd",
    )
    with pytest.raises((AttributeError, TypeError)):
        result.source = "explicit"  # type: ignore[misc]
