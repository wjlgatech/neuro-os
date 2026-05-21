"""Tests for agent/research/run_registry.py — pipeline run tracking."""
from __future__ import annotations

import pytest
from pathlib import Path

from agent.research.run_registry import (
    PipelineRun,
    StageRecord,
    clean_runs,
    list_runs,
    load_run,
    open_run,
    record_stage,
)


@pytest.fixture()
def home(tmp_path: Path) -> Path:
    return tmp_path / "neuro_os_research"


def test_open_run_creates_entry(home: Path) -> None:
    run = open_run(home, label="test-run")
    assert isinstance(run, PipelineRun)
    assert run.label == "test-run"
    assert len(run.run_id) == 8

    # Persisted
    runs = list_runs(home)
    assert len(runs) == 1
    assert runs[0].run_id == run.run_id


def test_record_stage_appends(home: Path) -> None:
    run = open_run(home, label="two-stage")
    s1 = record_stage(home, run.run_id, "ingest", artifact_id="abc123", item_count=5)
    s2 = record_stage(home, run.run_id, "compress", artifact_id="def456", item_count=12)

    assert isinstance(s1, StageRecord)
    assert s1.stage == "ingest"
    assert s2.stage == "compress"

    loaded = load_run(home, run.run_id)
    assert loaded is not None
    assert len(loaded.stages) == 2
    assert loaded.stages[0].artifact_id == "abc123"
    assert loaded.stages[1].item_count == 12


def test_list_runs_returns_newest_first(home: Path) -> None:
    r1 = open_run(home, label="first")
    open_run(home, label="second")
    r3 = open_run(home, label="third")

    runs = list_runs(home)
    ids = [r.run_id for r in runs]
    assert ids[0] == r3.run_id
    assert ids[-1] == r1.run_id


def test_load_run_returns_none_for_missing(home: Path) -> None:
    open_run(home, label="exists")
    assert load_run(home, "notarun") is None


def test_clean_runs_keeps_recent(home: Path) -> None:
    for i in range(10):
        open_run(home, label=f"run-{i}")

    deleted = clean_runs(home, keep=3)
    assert deleted == 7
    remaining = list_runs(home)
    assert len(remaining) == 3


def test_clean_runs_noop_when_under_limit(home: Path) -> None:
    open_run(home, label="only-one")
    assert clean_runs(home, keep=10) == 0


def test_list_runs_empty_before_any_runs(home: Path) -> None:
    assert list_runs(home) == []


def test_run_has_last_stage_property(home: Path) -> None:
    run = open_run(home, label="check-property")
    assert run.last_stage is None

    record_stage(home, run.run_id, "ingest", artifact_id="x", item_count=1)
    record_stage(home, run.run_id, "compress", artifact_id="y", item_count=3)

    loaded = load_run(home, run.run_id)
    assert loaded is not None
    assert loaded.last_stage == "compress"


def test_multiple_runs_stages_do_not_cross_contaminate(home: Path) -> None:
    r1 = open_run(home, label="r1")
    r2 = open_run(home, label="r2")
    record_stage(home, r1.run_id, "ingest", artifact_id="a", item_count=2)
    record_stage(home, r2.run_id, "compress", artifact_id="b", item_count=5)

    l1 = load_run(home, r1.run_id)
    l2 = load_run(home, r2.run_id)
    assert l1 is not None and len(l1.stages) == 1 and l1.stages[0].stage == "ingest"
    assert l2 is not None and len(l2.stages) == 1 and l2.stages[0].stage == "compress"
