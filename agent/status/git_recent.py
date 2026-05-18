"""
Read the last N commits via `git log`. Used to populate the
"3 most recent ships" table at the top of STATUS.md.

Pure shell-out + parse + Pydantic-validate. The render path consumes
List[RecentShip]; everything else here is implementation detail.

Defensive: an empty/failed `git log` returns []. STATUS.md must render
even in a fresh clone with no commits.
"""
from __future__ import annotations

import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RecentShip(BaseModel):
    """One row in the 'most recent ships' table.

    Frozen — derived from git log, treated as read-only history.
    """

    model_config = ConfigDict(frozen=True)

    sha: str = Field(min_length=7, max_length=40, description="Short SHA.")
    date: date
    subject: str = Field(min_length=1, max_length=300)


def get_recent_ships(
    *,
    cwd: Optional[Path] = None,
    limit: int = 3,
) -> List[RecentShip]:
    """Return the last ``limit`` commits as RecentShip rows.

    ``cwd`` defaults to the current working directory. Returns [] on any
    git failure (fresh clone, no commits, git absent).
    """
    try:
        out = subprocess.run(
            ["git", "log", f"-{limit}", "--format=%h|%ai|%s"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(cwd) if cwd is not None else None,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    if out.returncode != 0 or not out.stdout.strip():
        return []
    rows: List[RecentShip] = []
    for line in out.stdout.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        sha_raw, when_raw, subj = parts
        when = when_raw.strip().split(" ")[0]
        try:
            d = datetime.strptime(when, "%Y-%m-%d").date()
        except ValueError:
            continue
        try:
            rows.append(RecentShip(
                sha=sha_raw.strip(),
                date=d,
                subject=subj.strip(),
            ))
        except Exception:
            continue
    return rows


__all__ = ["RecentShip", "get_recent_ships"]
