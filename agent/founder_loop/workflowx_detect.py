"""
``workflowx_detect.py`` — find a workflowx export file without manual setup.

Workflowx is an external tool that writes JSONL files in the
``RawEvent`` shape (see ``observe.py``). Today, on a clean install, the
daemon defaults to ``~/.founder_loop/workflowx.jsonl`` (auto-created
empty), so the predictor runs blind unless the user wires the path
manually. This module sweeps a small set of well-known platform paths
and returns the first match — so the daemon "just works" the moment
workflowx is present.

Search precedence (highest priority wins):

1. Explicit ``explicit`` argument — the CLI ``--workflowx-fixture`` flag.
2. Environment override (``WORKFLOWX_EXPORTS_PATH``) — direct file or
   directory path.
3. Platform-specific known directories. For each, the most-recently-
   modified ``.jsonl`` is returned.
4. Repo-local ``./workflowx.jsonl`` (covers dev setups where the user
   keeps a fixture next to the project).
5. Fallback to the explicit ``fallback`` path. ``is_real=False`` here so
   the daemon can log loudly that it's running blind.

This module is read-only beyond ``Path.exists`` / ``Path.iterdir`` /
``Path.stat``. It does not write or create anything.
"""
from __future__ import annotations

import os
import platform as _platform_mod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional, Tuple


Platform = Literal["macos", "linux", "windows", "unknown"]

DetectionSource = Literal[
    "explicit",
    "env",
    "macos:application-support",
    "macos:dot-workflowx",
    "linux:xdg-config",
    "linux:xdg-data",
    "linux:dot-workflowx",
    "windows:appdata",
    "windows:localappdata",
    "repo-local",
    "fallback",
]


_ENV_VAR = "WORKFLOWX_EXPORTS_PATH"


def detect_platform() -> Platform:
    """Mirror of ``install.detect_platform`` so this module stays
    independent (no circular imports)."""
    s = _platform_mod.system().lower()
    if s == "darwin":
        return "macos"
    if s == "linux":
        return "linux"
    if s == "windows":
        return "windows"
    return "unknown"


@dataclass(frozen=True)
class DetectionResult:
    """The detector's verdict.

    * ``path`` — what the daemon should pass to ``FixtureWorkflowxAdapter``.
    * ``source`` — short label naming which branch matched, used for
      logging and the `loop workflowx-detect` JSON output.
    * ``is_real`` — True when the path points at a non-fallback workflowx
      export (real signal expected). False only for ``source="fallback"``,
      meaning the daemon will run blind unless the user logs urges.
    * ``note`` — one-liner suitable for printing to the user.
    """

    path: Path
    source: DetectionSource
    is_real: bool
    note: str


def candidate_directories(
    platform: Optional[Platform] = None,
    *,
    home: Optional[Path] = None,
) -> List[Tuple[Path, DetectionSource]]:
    """Per-platform ordered list of (directory, source-label) pairs.

    Tests pass an explicit ``platform`` to keep results deterministic
    across CI environments. ``home`` lets tests redirect the home dir
    without monkey-patching ``Path.home``.
    """
    p = platform or detect_platform()
    h = home or Path.home()
    if p == "macos":
        return [
            (h / "Library" / "Application Support" / "workflowx" / "exports",
             "macos:application-support"),
            (h / ".workflowx" / "exports", "macos:dot-workflowx"),
        ]
    if p == "linux":
        return [
            (h / ".config" / "workflowx" / "exports", "linux:xdg-config"),
            (h / ".local" / "share" / "workflowx" / "exports", "linux:xdg-data"),
            (h / ".workflowx" / "exports", "linux:dot-workflowx"),
        ]
    if p == "windows":
        appdata = os.environ.get("APPDATA")
        localappdata = os.environ.get("LOCALAPPDATA")
        out: List[Tuple[Path, DetectionSource]] = []
        if appdata:
            out.append((Path(appdata) / "workflowx" / "exports", "windows:appdata"))
        if localappdata:
            out.append(
                (Path(localappdata) / "workflowx" / "exports", "windows:localappdata")
            )
        return out
    return []


def newest_jsonl_in(directory: Path) -> Optional[Path]:
    """Return the most-recently-modified ``*.jsonl`` in ``directory``.

    None when the directory is missing, not a directory, or contains no
    ``.jsonl`` files. Symlinks are resolved by ``Path.iterdir`` /
    ``stat`` per stdlib defaults.
    """
    if not directory.exists() or not directory.is_dir():
        return None
    candidates: List[Tuple[float, Path]] = []
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        if entry.suffix.lower() != ".jsonl":
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, entry))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _resolve_env_or_explicit(
    raw: str,
) -> Optional[Path]:
    """Treat ``raw`` as a path. If a directory, descend to the newest
    .jsonl. If a file, return it. Return None if nothing usable.
    """
    p = Path(raw).expanduser()
    if p.is_dir():
        return newest_jsonl_in(p)
    if p.exists() and p.is_file():
        return p
    # Even if the file doesn't exist yet (e.g. workflowx hasn't written
    # its first export), honor an explicit pointer — the daemon will
    # simply read zero events until workflowx writes. This is better
    # than silently switching to fallback.
    if p.suffix.lower() == ".jsonl":
        return p
    return None


def detect_workflowx_export(
    *,
    fallback: Path,
    explicit: Optional[Path] = None,
    env_override: Optional[str] = None,
    platform: Optional[Platform] = None,
    home: Optional[Path] = None,
    cwd: Optional[Path] = None,
) -> DetectionResult:
    """Run the precedence chain and return where the daemon should read.

    ``explicit`` and ``env_override`` are the two non-default surfaces.
    ``platform`` and ``home`` exist for tests; production callers pass
    neither and the function calls ``detect_platform()`` /
    ``Path.home()`` itself. Same for ``cwd``.
    """
    # 1. Explicit always wins.
    if explicit is not None:
        return DetectionResult(
            path=explicit,
            source="explicit",
            is_real=True,
            note=f"workflowx: using explicit path {explicit}",
        )

    # 2. Env var.
    env_raw = (
        env_override
        if env_override is not None
        else os.environ.get(_ENV_VAR)
    )
    if env_raw:
        resolved = _resolve_env_or_explicit(env_raw)
        if resolved is not None:
            return DetectionResult(
                path=resolved,
                source="env",
                is_real=True,
                note=f"workflowx: detected via {_ENV_VAR}={env_raw} → {resolved}",
            )

    # 3. Platform-specific known directories.
    for directory, source in candidate_directories(platform, home=home):
        newest = newest_jsonl_in(directory)
        if newest is not None:
            return DetectionResult(
                path=newest,
                source=source,
                is_real=True,
                note=f"workflowx: detected at {newest} (source={source})",
            )

    # 4. Repo-local.
    cwd_path = (cwd or Path.cwd()).resolve()
    repo_local = cwd_path / "workflowx.jsonl"
    if repo_local.exists() and repo_local.is_file():
        return DetectionResult(
            path=repo_local,
            source="repo-local",
            is_real=True,
            note=f"workflowx: using repo-local {repo_local}",
        )

    # 5. Fallback.
    return DetectionResult(
        path=fallback,
        source="fallback",
        is_real=False,
        note=(
            f"workflowx: not detected; running blind on fallback {fallback}. "
            f"Set --workflowx-fixture or {_ENV_VAR} to feed real signal."
        ),
    )


__all__ = [
    "Platform",
    "DetectionSource",
    "DetectionResult",
    "detect_platform",
    "candidate_directories",
    "newest_jsonl_in",
    "detect_workflowx_export",
]
