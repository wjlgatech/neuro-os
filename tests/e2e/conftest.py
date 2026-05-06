"""
Shared fixtures for the e2e suite.

* ``daemon`` — boots the founder_loop server in a background thread on
  a free port, yields a `Daemon` handle with the base URL plus the
  per-test paths (registry, contract, events, workflowx fixture).
* ``http`` — a tiny ``urllib``-based client that the test files use to
  hit the daemon without pulling in ``requests`` as a dep.

The browser fixture (Playwright) lives in
``test_browser_scenarios.py``; we don't import it from conftest so the
HTTP-only suite runs on machines without Playwright installed.
"""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pytest

from agent.founder_loop.server import serve


def _free_port() -> int:
    """Bind to port 0 then close — gets us a port we know is free."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class Daemon:
    """Handle returned by the ``daemon`` fixture."""

    base_url: str
    registry_path: Path
    contract_path: Path
    events_path: Path
    workflowx_fixture: Path

    def url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"


class _HTTPClient:
    """Minimal urllib client. Returns (status_code, parsed_json | None)."""

    def get(self, url: str) -> tuple[int, Any]:
        req = urllib.request.Request(url, method="GET")
        return self._do(req)

    def post(self, url: str, body: dict) -> tuple[int, Any]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        return self._do(req)

    def _do(self, req: urllib.request.Request) -> tuple[int, Any]:
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else None
        except json.JSONDecodeError:
            payload = raw.decode("utf-8", errors="replace")
        return status, payload


@pytest.fixture(scope="function")
def http() -> _HTTPClient:
    return _HTTPClient()


@pytest.fixture(scope="function")
def daemon(tmp_path):
    """Boot a daemon on a free port; clean shutdown when the test ends."""
    registry = tmp_path / "registry.jsonl"
    contract = tmp_path / "contracts.jsonl"
    events = tmp_path / "events.jsonl"
    workflowx = tmp_path / "workflowx.jsonl"
    workflowx.write_text("", encoding="utf-8")  # empty fallback by default

    port = _free_port()
    server = serve(
        host="127.0.0.1",
        port=port,
        registry_path=registry,
        contract_path=contract,
        workflowx_fixture=workflowx,
        events_path=events,
        use_llm=False,
        tick_interval_min=0,
        block=False,  # serve() starts its own thread when block=False
    )

    base_url = f"http://127.0.0.1:{port}"
    # Wait for /healthz.
    deadline = time.time() + 5
    last_err = None
    ready = False
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/healthz", timeout=1) as r:
                if r.status == 200:
                    ready = True
                    break
        except Exception as exc:
            last_err = exc
            time.sleep(0.05)
    if not ready:
        raise RuntimeError(
            f"daemon failed to come up on {base_url}; last error: {last_err}"
        )

    try:
        yield Daemon(
            base_url=base_url,
            registry_path=registry,
            contract_path=contract,
            events_path=events,
            workflowx_fixture=workflowx,
        )
    finally:
        server.shutdown()
        server.server_close()
