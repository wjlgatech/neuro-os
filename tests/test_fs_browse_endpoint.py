"""HTTP-level tests for GET /fs/browse.

Backs the /research "Browse folders…" directory picker.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Tuple
from urllib.parse import urlencode

import pytest

from agent.founder_loop.contract import save_contract
from agent.founder_loop.server import serve
from agent.founder_loop.state import Contract, Priority


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str) -> Tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=2.0) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


@pytest.fixture()
def daemon(tmp_path: Path):
    registry = tmp_path / "registry.jsonl"
    contracts = tmp_path / "contracts.jsonl"
    workflowx = tmp_path / "workflowx.jsonl"
    workflowx.write_text("", encoding="utf-8")
    # Bind a minimal contract so the daemon is happy.
    save_contract(
        Contract(
            date="2026-05-21",
            priorities=[Priority(
                title="x", evidence_type="pr_merged",
                evidence_target="#1", weight=1,
            )],
            entertainment_ration_min=60, threshold_pct=90,
            signed_at="2026-05-21T08:00:00+00:00",
        ),
        contracts,
    )
    port = _free_port()
    server = serve(
        host="127.0.0.1", port=port,
        registry_path=registry,
        contract_path=contracts,
        workflowx_fixture=workflowx,
        block=False,
        research_home=tmp_path / "research",
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with urllib.request.urlopen(base + "/healthz", timeout=0.5):
                break
        except (urllib.error.URLError, OSError):
            time.sleep(0.05)
    else:
        server.shutdown()
        pytest.fail("daemon did not come up within 2.5s")
    yield base, tmp_path
    server.shutdown()


def test_fs_browse_lists_directory(daemon) -> None:
    base, tmp_path = daemon
    # Seed a known structure inside tmp_path.
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "one.pdf").write_text("x")
    (tmp_path / "papers" / "two.md").write_text("y")
    (tmp_path / "papers" / "sub").mkdir()

    status, body = _get(base + "/fs/browse?" + urlencode({
        "path": str(tmp_path / "papers"),
    }))
    assert status == 200, body
    assert body["path"] == str((tmp_path / "papers").resolve())
    assert body["parent"] == str(tmp_path.resolve())
    names = [e["name"] for e in body["entries"]]
    assert "sub" in names
    assert "one.pdf" in names
    assert "two.md" in names
    # Dirs sort before files.
    dirs = [e for e in body["entries"] if e["is_dir"]]
    files = [e for e in body["entries"] if not e["is_dir"]]
    if dirs and files:
        assert body["entries"].index(dirs[-1]) < body["entries"].index(files[0])


def test_fs_browse_defaults_to_home(daemon) -> None:
    base, _ = daemon
    status, body = _get(base + "/fs/browse")
    assert status == 200
    assert body["path"] == str(Path.home().resolve())


def test_fs_browse_rejects_relative_path(daemon) -> None:
    base, _ = daemon
    status, body = _get(base + "/fs/browse?" + urlencode({"path": "foo/bar"}))
    assert status == 400
    assert "absolute" in body["error"]


def test_fs_browse_404_on_missing_path(daemon) -> None:
    base, _ = daemon
    status, body = _get(base + "/fs/browse?" + urlencode({
        "path": "/does/not/exist/anywhere",
    }))
    assert status == 404
    assert "not found" in body["error"]


def test_fs_browse_400_on_file_path(daemon, tmp_path: Path) -> None:
    base, _ = daemon
    f = tmp_path / "a-file.txt"
    f.write_text("hi")
    status, body = _get(base + "/fs/browse?" + urlencode({"path": str(f)}))
    assert status == 400
    assert "not a directory" in body["error"]


def test_fs_browse_hides_hidden_by_default(daemon, tmp_path: Path) -> None:
    base, _ = daemon
    d = tmp_path / "with-hidden"
    d.mkdir()
    (d / ".hidden").mkdir()
    (d / "visible.md").write_text("x")

    status, body = _get(base + "/fs/browse?" + urlencode({"path": str(d)}))
    assert status == 200
    names = [e["name"] for e in body["entries"]]
    assert "visible.md" in names
    assert ".hidden" not in names


def test_fs_browse_show_hidden_toggle(daemon, tmp_path: Path) -> None:
    base, _ = daemon
    d = tmp_path / "with-hidden"
    d.mkdir(exist_ok=True)
    (d / ".dotfile").write_text("x")

    status, body = _get(base + "/fs/browse?" + urlencode({
        "path": str(d), "show_hidden": "1",
    }))
    assert status == 200
    names = [e["name"] for e in body["entries"]]
    assert ".dotfile" in names


def test_fs_browse_caps_entries(daemon, tmp_path: Path) -> None:
    base, _ = daemon
    d = tmp_path / "many"
    d.mkdir()
    # Create over the cap (500) to verify truncation.
    for i in range(520):
        (d / f"f{i:04d}.txt").write_text("x")

    status, body = _get(base + "/fs/browse?" + urlencode({"path": str(d)}))
    assert status == 200
    assert body["truncated"] is True
    assert len(body["entries"]) == 500
