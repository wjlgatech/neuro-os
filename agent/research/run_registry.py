"""Pipeline run registry — groups ingest → compress → express into traceable runs.

Data lives at <research_home>/runs.db (SQLite), which is outside the repo
and never committed. Use ``list_runs`` / ``load_run`` / ``clean_runs`` from
the CLI (``neuro-os research runs …``) or from the daemon.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List, Literal, Optional

from pydantic import BaseModel, Field

StageName = Literal["ingest", "compress", "express"]


class StageRecord(BaseModel, frozen=True):
    stage_id: str
    run_id: str
    stage: StageName
    artifact_id: str
    item_count: int
    recorded_at: str


class PipelineRun(BaseModel, frozen=True):
    run_id: str
    label: str
    opened_at: str
    stages: List[StageRecord] = Field(default_factory=list)

    @property
    def last_stage(self) -> Optional[str]:
        return self.stages[-1].stage if self.stages else None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _db_path(home: Path) -> Path:
    return home / "runs.db"


@contextmanager
def _conn(home: Path) -> Generator[sqlite3.Connection, None, None]:
    home.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_db_path(home))
    con.row_factory = sqlite3.Row
    try:
        _init(con)
        yield con
        con.commit()
    finally:
        con.close()


def _init(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_run (
            run_id    TEXT PRIMARY KEY,
            label     TEXT NOT NULL,
            opened_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pipeline_stage (
            stage_id    TEXT PRIMARY KEY,
            run_id      TEXT NOT NULL REFERENCES pipeline_run(run_id),
            stage       TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            item_count  INTEGER NOT NULL DEFAULT 0,
            recorded_at TEXT NOT NULL
        );
    """)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_stages(con: sqlite3.Connection, run_id: str) -> List[StageRecord]:
    rows = con.execute(
        "SELECT * FROM pipeline_stage WHERE run_id = ? ORDER BY recorded_at",
        (run_id,),
    ).fetchall()
    return [StageRecord(**dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def open_run(home: Path, label: str) -> PipelineRun:
    """Create a new pipeline run entry and return it."""
    run_id = str(uuid.uuid4())[:8]
    opened_at = _now()
    with _conn(home) as con:
        con.execute(
            "INSERT INTO pipeline_run VALUES (?, ?, ?)",
            (run_id, label, opened_at),
        )
    return PipelineRun(run_id=run_id, label=label, opened_at=opened_at)


def record_stage(
    home: Path,
    run_id: str,
    stage: StageName,
    artifact_id: str,
    item_count: int = 0,
) -> StageRecord:
    """Append a stage completion to an existing pipeline run."""
    rec = StageRecord(
        stage_id=str(uuid.uuid4())[:8],
        run_id=run_id,
        stage=stage,
        artifact_id=artifact_id,
        item_count=item_count,
        recorded_at=_now(),
    )
    with _conn(home) as con:
        con.execute(
            "INSERT INTO pipeline_stage VALUES (?, ?, ?, ?, ?, ?)",
            (rec.stage_id, rec.run_id, rec.stage, rec.artifact_id,
             rec.item_count, rec.recorded_at),
        )
    return rec


def list_runs(home: Path, limit: int = 50) -> List[PipelineRun]:
    """Return most recent pipeline runs, newest first."""
    with _conn(home) as con:
        rows = con.execute(
            "SELECT * FROM pipeline_run ORDER BY opened_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            PipelineRun(
                run_id=row["run_id"],
                label=row["label"],
                opened_at=row["opened_at"],
                stages=_load_stages(con, row["run_id"]),
            )
            for row in rows
        ]


def load_run(home: Path, run_id: str) -> Optional[PipelineRun]:
    """Load a single run by ID, or None if not found."""
    with _conn(home) as con:
        row = con.execute(
            "SELECT * FROM pipeline_run WHERE run_id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None
        stages = _load_stages(con, run_id)
    return PipelineRun(
        run_id=row["run_id"],
        label=row["label"],
        opened_at=row["opened_at"],
        stages=stages,
    )


def clean_runs(home: Path, keep: int = 20) -> int:
    """Delete oldest runs, keeping the ``keep`` most recent. Returns count deleted."""
    with _conn(home) as con:
        to_delete = con.execute(
            "SELECT run_id FROM pipeline_run ORDER BY opened_at DESC"
            " LIMIT -1 OFFSET ?",
            (keep,),
        ).fetchall()
        if not to_delete:
            return 0
        ids = [r["run_id"] for r in to_delete]
        placeholders = ",".join("?" * len(ids))
        con.execute(
            f"DELETE FROM pipeline_stage WHERE run_id IN ({placeholders})", ids
        )
        con.execute(
            f"DELETE FROM pipeline_run WHERE run_id IN ({placeholders})", ids
        )
    return len(ids)
