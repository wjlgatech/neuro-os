"""
Walk docs/ for files with YAML frontmatter stamps.

Returns a List[StampedPlan]. Skips:
  * STATUS.md itself (the generated artifact must not stamp itself).
  * Reference docs that are not goals (what-is-this, how-it-works,
    how-to-use-it, paul-week-may-11, AI_NATIVE_ENGINEERING_PRINCIPLES).
  * Files without frontmatter (warning printed, not raised — the walker
    is tolerant so partial rollouts work).

Parses frontmatter with PyYAML's safe_load and validates the dict
against PlanStamp via Pydantic. A malformed stamp surfaces the file path
so the user can fix it.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from pydantic import ValidationError

from agent.status.stamp import PlanStamp, StampedPlan


# Files inside docs/ that are reference, not goals — skip even if someone
# accidentally stamps them. Keeps the kitchen-whiteboard short.
SKIP_NAMES = frozenset({
    "STATUS.md",
    "AI_NATIVE_ENGINEERING_PRINCIPLES.md",
    "how-it-works.md",
    "how-to-use-it.md",
    "what-is-this.md",
    "paul-week-may-11.md",
})


def _split_frontmatter(text: str) -> Tuple[Optional[dict], str]:
    """Split a markdown file into (frontmatter_dict, body).

    Returns (None, full_text) when no frontmatter delimiter is present.
    Frontmatter must start at the first byte of the file: ``---\\n``.
    """
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return (None, text)
    # Find the closing delimiter on a line by itself.
    rest = text[4:] if text.startswith("---\n") else text[5:]
    end_marker = rest.find("\n---\n")
    if end_marker == -1:
        return (None, text)
    fm_raw = rest[:end_marker]
    body = rest[end_marker + 5:]
    try:
        fm = yaml.safe_load(fm_raw)
    except yaml.YAMLError:
        return (None, text)
    if not isinstance(fm, dict):
        return (None, text)
    return (fm, body)


def _extract_title(body: str, *, fallback: str) -> str:
    """First `# heading` line; fallback to the filename stem if absent."""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _git_last_touched(path: Path) -> Optional[date]:
    """Return the most recent commit date for ``path``. None if the
    file is untracked or git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ai", "--", str(path)],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    raw = out.stdout.strip().split(" ")[0]  # "2026-05-18"
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def walk_stamped_plans(
    docs_root: Path,
    *,
    quiet: bool = False,
) -> List[StampedPlan]:
    """Walk ``docs_root`` and return every successfully-stamped plan.

    Files in SKIP_NAMES are skipped silently.
    Files in docs/ that have no frontmatter print a one-line warning
    unless ``quiet=True``. Files with malformed stamps raise — silent
    skip would mask user typos and defeat the discipline gate.
    """
    out: List[StampedPlan] = []
    for path in sorted(docs_root.rglob("*.md")):
        if path.name in SKIP_NAMES:
            continue
        text = path.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)
        if fm is None:
            if not quiet:
                rel = path.relative_to(docs_root.parent)
                print(
                    f"sync_status: warning: {rel} has no frontmatter "
                    "stamp; skipping. Add `--- status: ... parent: ... ---` "
                    "at the top to include it in STATUS.md.",
                    file=sys.stderr,
                )
            continue
        try:
            stamp = PlanStamp.model_validate(fm)
        except ValidationError as exc:
            rel = path.relative_to(docs_root.parent)
            raise ValueError(
                f"sync_status: malformed stamp in {rel}: {exc}"
            ) from exc
        title = _extract_title(body, fallback=path.stem)
        out.append(StampedPlan(
            path=path,
            title=title,
            stamp=stamp,
            last_touched=_git_last_touched(path),
        ))
    return out


__all__ = ["walk_stamped_plans", "SKIP_NAMES"]
