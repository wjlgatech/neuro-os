"""
Local HTTP daemon — the bridge between UI surfaces (browser extension,
tray app) and the ``FounderLoop`` engine.

Bound to ``127.0.0.1`` only. No auth in v0 (localhost is the boundary).
Uses stdlib ``http.server`` so we add zero deps.

Endpoints
---------

* ``GET  /healthz`` — liveness probe
* ``GET  /tank`` — current ``TankState``
* ``GET  /contract`` — current ``Contract``
* ``GET  /tick?intent=...&dry_run=true`` — run a tick, return ``TickResult``
* ``POST /diagnose`` — body ``{state, urge_type}`` → ``Diagnosis`` (stateless)
* ``POST /events`` — body ``{kind, ...}`` → append to events log
* ``GET  /today`` — composite: tank + last-N ticks + contract summary

The browser extension polls ``/tank`` for the badge, calls ``/tick`` on
URL navigation to high-distraction hosts, and POSTs to ``/events`` when
the user accepts/refuses a sublimation card. The tray app polls
``/today`` once a minute and renders the menu.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import urllib.parse
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent.founder_loop import (
    FounderLoop,
    diagnose_underlying_need,
)
from agent.founder_loop.contract import load_latest_contract
from agent.founder_loop.memory import filter_by_day, read_registry
from agent.founder_loop.observe import FixtureWorkflowxAdapter
from agent.founder_loop.reward_ledger import compute_tank
from agent.founder_loop.state import FounderState

log = logging.getLogger("founder_loop.server")


class _Config:
    """Server-wide config. Built once in ``serve()``."""

    def __init__(
        self,
        *,
        registry_path: Path,
        contract_path: Path,
        workflowx_fixture: Path,
        events_path: Path,
        use_llm: bool,
        api_key: Optional[str],
    ) -> None:
        self.registry_path = registry_path
        self.contract_path = contract_path
        self.workflowx_fixture = workflowx_fixture
        self.events_path = events_path
        self.use_llm = use_llm
        self.api_key = api_key

    def make_loop(self) -> FounderLoop:
        return FounderLoop(
            registry_path=self.registry_path,
            contract_path=self.contract_path,
            adapter=FixtureWorkflowxAdapter(self.workflowx_fixture),
            use_llm=self.use_llm,
            api_key=self.api_key,
        )


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"not serialisable: {type(obj)!r}")


class FounderLoopHandler(BaseHTTPRequestHandler):
    """One handler instance per request (stdlib semantics)."""

    config: _Config  # set on the class by ``serve()``

    # ------------------------------------------------------------------
    # Wire-level helpers
    # ------------------------------------------------------------------

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # CORS — localhost-only daemon, browser extension origin is
        # ``chrome-extension://...`` / ``moz-extension://...``. Wildcard
        # is fine since we bind to 127.0.0.1.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise _BadRequest(f"invalid JSON body: {exc}") from exc

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D401
        # Quiet by default; stdlib logs to stderr otherwise.
        log.info("%s - %s", self.address_string(), fmt % args)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(204, {})

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._dispatch_get()
        except _BadRequest as exc:
            self._send_json(400, {"error": str(exc)})
        except FileNotFoundError as exc:
            self._send_json(404, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover — defensive
            log.exception("GET handler failed: %s", self.path)
            self._send_json(500, {"error": repr(exc)})

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._dispatch_post()
        except _BadRequest as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover — defensive
            log.exception("POST handler failed: %s", self.path)
            self._send_json(500, {"error": repr(exc)})

    # ------------------------------------------------------------------
    # GET routes
    # ------------------------------------------------------------------

    def _dispatch_get(self) -> None:
        path, query = _split_path_query(self.path)
        if path == "/healthz":
            self._healthz()
        elif path == "/tank":
            self._tank()
        elif path == "/contract":
            self._contract()
        elif path == "/tick":
            self._tick(query)
        elif path == "/today":
            self._today()
        else:
            self._send_json(404, {"error": f"unknown route: {path}"})

    def _healthz(self) -> None:
        self._send_json(200, {
            "ok": True,
            "service": "founder_loop",
            "registry": str(self.config.registry_path),
            "use_llm": self.config.use_llm,
        })

    def _tank(self) -> None:
        contract = load_latest_contract(self.config.contract_path)
        if contract is None:
            self._send_json(200, {
                "tank": None,
                "reason": "no contract bound — run `loop morning` first",
            })
            return
        all_rows = read_registry(self.config.registry_path)
        today_rows = filter_by_day(all_rows, datetime.now(timezone.utc).date())
        tank = compute_tank(today_rows, contract=contract)
        self._send_json(200, {"tank": json.loads(tank.model_dump_json())})

    def _contract(self) -> None:
        contract = load_latest_contract(self.config.contract_path)
        self._send_json(200, {
            "contract": (
                json.loads(contract.model_dump_json()) if contract else None
            ),
        })

    def _tick(self, query: Dict[str, str]) -> None:
        loop = self.config.make_loop()
        intent = query.get("intent") or None
        dry_run = query.get("dry_run", "").lower() in {"1", "true", "yes"}
        result = loop.tick(intent=intent, dry_run=dry_run)
        self._send_json(200, {
            "tick": json.loads(result.model_dump_json()),
        })

    def _today(self) -> None:
        contract = load_latest_contract(self.config.contract_path)
        all_rows = read_registry(self.config.registry_path)
        today = datetime.now(timezone.utc).date()
        today_rows = filter_by_day(all_rows, today)
        tank = (
            compute_tank(today_rows, contract=contract) if contract else None
        )
        # Last 3 ticks for the tray menu.
        recent = today_rows[-3:] if today_rows else []
        self._send_json(200, {
            "date": today.isoformat(),
            "tank": json.loads(tank.model_dump_json()) if tank else None,
            "contract": (
                json.loads(contract.model_dump_json()) if contract else None
            ),
            "recent_ticks": recent,
        })

    # ------------------------------------------------------------------
    # POST routes
    # ------------------------------------------------------------------

    def _dispatch_post(self) -> None:
        path, _ = _split_path_query(self.path)
        if path == "/diagnose":
            self._diagnose()
        elif path == "/events":
            self._events()
        else:
            self._send_json(404, {"error": f"unknown route: {path}"})

    def _diagnose(self) -> None:
        body = self._read_json_body()
        state_payload = body.get("state")
        urge_type = body.get("urge_type", "entertainment")
        if not state_payload:
            raise _BadRequest("`state` required in request body")
        try:
            state = FounderState.model_validate(state_payload)
        except Exception as exc:
            raise _BadRequest(f"invalid state: {exc}") from exc
        diagnosis = diagnose_underlying_need(state, urge_type=urge_type)
        self._send_json(200, {
            "diagnosis": json.loads(diagnosis.model_dump_json()),
        })

    def _events(self) -> None:
        body = self._read_json_body()
        kind = body.get("kind")
        if kind not in {
            "accepted_expression",
            "overrode_proposal",
            "opened_distraction_url",
            "manual_intent_capture",
        }:
            raise _BadRequest(
                f"unknown event kind: {kind!r}. "
                "expected one of: accepted_expression | overrode_proposal | "
                "opened_distraction_url | manual_intent_capture"
            )
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            **{k: v for k, v in body.items() if k != "kind"},
        }
        self.config.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        self._send_json(201, {"logged": record})


class _BadRequest(Exception):
    """Raised inside handlers; converted to HTTP 400."""


def _split_path_query(raw: str) -> Tuple[str, Dict[str, str]]:
    parsed = urllib.parse.urlparse(raw)
    qs = urllib.parse.parse_qs(parsed.query)
    flat = {k: v[0] for k, v in qs.items() if v}
    return parsed.path, flat


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    registry_path: Path,
    contract_path: Path,
    workflowx_fixture: Path,
    events_path: Optional[Path] = None,
    use_llm: bool = False,
    api_key: Optional[str] = None,
    block: bool = True,
) -> ThreadingHTTPServer:
    """Start the daemon. Returns the server (already listening)."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        # Refuse to bind to non-loopback. This is a personal-data daemon.
        raise ValueError(
            f"refusing to bind to non-loopback host {host!r}; "
            "the daemon is local-only by design"
        )
    events_path = events_path or registry_path.with_name("events.jsonl")
    cfg = _Config(
        registry_path=Path(registry_path),
        contract_path=Path(contract_path),
        workflowx_fixture=Path(workflowx_fixture),
        events_path=Path(events_path),
        use_llm=use_llm,
        api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
    )
    FounderLoopHandler.config = cfg
    server = ThreadingHTTPServer((host, port), FounderLoopHandler)
    log.info("founder_loop daemon listening on http://%s:%d", host, port)
    if block:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log.info("shutting down")
            server.shutdown()
    else:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
    return server


__all__ = ["serve", "FounderLoopHandler"]
