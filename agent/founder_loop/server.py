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
from typing import Any, Dict, Optional, Tuple

from agent.founder_loop import (
    FounderLoop,
    diagnose_underlying_need,
)
from agent.founder_loop._markdown import render_markdown
from agent.founder_loop.contract import bind_morning_contract, load_latest_contract
from agent.founder_loop.conversation import ConversationManager
from agent.founder_loop.memory import filter_by_day, read_registry
from agent.founder_loop.observe import FixtureWorkflowxAdapter
from agent.founder_loop.reward_ledger import compute_tank
from agent.founder_loop.state import FounderState

STATIC_DIR = Path(__file__).parent / "static"
DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

# Map URL path → (markdown filename, page title)
_DOC_ROUTES: Dict[str, tuple[str, str]] = {
    "/about": ("what-is-this.md", "What is this?"),
    "/how-to-use": ("how-to-use-it.md", "How to use it"),
    "/how-it-works": ("how-it-works.md", "How it works"),
    "/roadmap": ("roadmap.md", "Roadmap"),
}

# Cross-origin defense. Loopback binding alone does NOT stop a browser
# script on attacker.com from issuing fetch('http://127.0.0.1:8765/...')
# — the browser will deliver the request, and a wildcard CORS response
# lets the attacker read it. We reject browser cross-origin requests at
# the dispatcher and echo (not wildcard) CORS for allowed ones.
_ALLOWED_ORIGIN_SCHEMES: Tuple[str, ...] = (
    "chrome-extension://",
    "moz-extension://",
)

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
        queues_dir: Optional[Path] = None,
    ) -> None:
        self.registry_path = registry_path
        self.contract_path = contract_path
        self.workflowx_fixture = workflowx_fixture
        self.events_path = events_path
        self.use_llm = use_llm
        self.api_key = api_key
        # Queues live next to the registry by default. The conversation
        # manager mutates these JSON files during the queues flow.
        self.queues_dir = (
            queues_dir or registry_path.parent / "queues"
        )
        self.queues_dir.mkdir(parents=True, exist_ok=True)
        self.conversations = ConversationManager(
            use_llm=use_llm,
            api_key=api_key,
            queues_dir=self.queues_dir,
        )

    def make_loop(self) -> FounderLoop:
        return FounderLoop(
            registry_path=self.registry_path,
            contract_path=self.contract_path,
            adapter=FixtureWorkflowxAdapter(self.workflowx_fixture),
            events_path=self.events_path,
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
    # Set by ``serve()``: the set of HTTP origins that map to the
    # daemon's own host:port (e.g. ``http://127.0.0.1:8765``). Browser
    # extension origins are matched by scheme prefix, not by exact set.
    allowed_exact_origins: frozenset = frozenset()

    # ------------------------------------------------------------------
    # Wire-level helpers
    # ------------------------------------------------------------------

    @classmethod
    def _is_origin_allowed(cls, origin: str) -> bool:
        if not origin:
            return False
        if origin in cls.allowed_exact_origins:
            return True
        return any(origin.startswith(s) for s in _ALLOWED_ORIGIN_SCHEMES)

    def _origin_check_passes(self) -> bool:
        """Reject browser cross-origin requests; allow same-origin,
        extensions, and non-browser clients (curl, tray app).

        Rule:
        - ``Sec-Fetch-Site: cross-site`` (modern browsers): reject.
        - ``Origin`` present but not allowlisted: reject.
        - Otherwise (same-origin, extension, or no Origin at all): allow.
        """
        if self.headers.get("Sec-Fetch-Site", "") == "cross-site":
            return False
        origin = self.headers.get("Origin", "")
        if origin and not self._is_origin_allowed(origin):
            return False
        return True

    def _reject_cross_origin(self) -> bool:
        """Send 403 and return True if the request is cross-origin from
        a non-allowlisted source. Caller must return immediately on True."""
        if self._origin_check_passes():
            return False
        self.send_response(403)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # CORS — echo the validated Origin (never wildcard). Wildcard
        # would let any browser script read responses to its
        # cross-origin fetch on 127.0.0.1, defeating the loopback
        # boundary. Cross-origin requests are rejected upstream by
        # ``_reject_cross_origin``; this just labels responses for the
        # allowed cases (same-origin daemon page, browser extension).
        origin = self.headers.get("Origin", "")
        if self._is_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
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
        if self._reject_cross_origin():
            return
        self._send_json(204, {})

    def do_GET(self) -> None:  # noqa: N802
        if self._reject_cross_origin():
            return
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
        if self._reject_cross_origin():
            return
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
        elif path in ("/onboard", "/onboard/", "/"):
            self._serve_chat_shell(kind="morning")
        elif path in ("/review", "/review/"):
            self._serve_chat_shell(kind="review")
        elif path in ("/queues", "/queues/"):
            self._serve_chat_shell(kind="queues")
        elif path == "/queues-state":
            self._queues_state()
        elif path.startswith("/onboard/"):
            asset = path[len("/onboard/"):]
            self._serve_static(asset, _guess_mime(asset))
        elif path in _DOC_ROUTES:
            md_name, title = _DOC_ROUTES[path]
            self._serve_doc(md_name, title)
        else:
            self._send_json(404, {"error": f"unknown route: {path}"})

    def _healthz(self) -> None:
        self._send_json(200, {
            "ok": True,
            "service": "founder_loop",
            "registry": str(self.config.registry_path),
            "use_llm": self.config.use_llm,
            "has_api_key": bool(self.config.api_key),
            "contract_bound": load_latest_contract(self.config.contract_path) is not None,
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

    def _queues_state(self) -> None:
        out: Dict[str, Any] = {}
        for q in ("bookmarks_queue", "social_queue", "rubber_duck_venues"):
            path = self.config.queues_dir / f"{q}.json"
            if path.is_file():
                try:
                    out[q] = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    out[q] = []
            else:
                out[q] = []
        self._send_json(200, out)

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
        elif path == "/chat":
            self._chat()
        elif path == "/sign":
            self._sign()
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


    # ------------------------------------------------------------------
    # Conversational onboarding
    # ------------------------------------------------------------------

    def _chat(self) -> None:
        body = self._read_json_body()
        cid = body.get("conversation_id")
        message = (body.get("message") or "").strip()
        kind = body.get("kind") or "morning"
        if kind not in ("morning", "review", "queues"):
            raise _BadRequest(f"unknown conversation kind: {kind!r}")

        if not cid:
            kickoff = self._build_kickoff(kind)
            cid, greeting = self.config.conversations.start(
                kind=kind, kickoff=kickoff,
            )
            self._send_json(200, {
                "conversation_id": cid,
                "kind": kind,
                "assistant_text": greeting,
                "priorities": [],
                "settings": {
                    "entertainment_ration_min": 60,
                    "threshold_pct": 90,
                },
                "can_sign": False,
                "using_llm": bool(self.config.api_key and self.config.use_llm),
                "queue_mutations": [],
                "kickoff": kickoff,  # so the UI can show today's summary
            })
            return
        if not message:
            raise _BadRequest("`message` required for non-initial /chat calls")
        turn = self.config.conversations.respond(cid, message)
        self._send_json(200, turn.to_jsonable())

    def _build_kickoff(self, kind: str) -> Optional[str]:
        """Runtime context injected as the first user message so Claude
        reasons over today's actual state."""
        if kind == "morning":
            return None
        if kind == "review":
            contract = load_latest_contract(self.config.contract_path)
            if contract is None:
                return (
                    "(No contract was bound for today. Ask the user how the "
                    "day went and propose tomorrow's priorities from "
                    "scratch.)"
                )
            try:
                loop = self.config.make_loop()
                summary = loop.nightly()
                summary_dict = json.loads(summary.model_dump_json())
            except Exception as exc:
                summary_dict = {"error": f"could not compute summary: {exc}"}
            priorities_status = "\n".join(
                f"  - [{p.status}] {p.title} "
                f"(weight {p.weight}; {p.evidence_type}: {p.evidence_target})"
                for p in contract.priorities
            )
            return (
                "Today's summary (use this to inform reflection — don't echo "
                "it back verbatim):\n"
                f"date: {contract.date}\n"
                f"priorities:\n{priorities_status}\n"
                f"ration: {contract.entertainment_ration_min} min · "
                f"threshold: {contract.threshold_pct}%\n"
                f"summary: {summary_dict}"
            )
        if kind == "queues":
            queues_dir = self.config.queues_dir
            queues = {}
            for q in ("bookmarks_queue", "social_queue", "rubber_duck_venues"):
                path = queues_dir / f"{q}.json"
                if path.is_file():
                    try:
                        queues[q] = json.loads(path.read_text())
                    except json.JSONDecodeError:
                        queues[q] = []
                else:
                    queues[q] = []
            return (
                "Current queue contents (use this to know what's already "
                "there — don't re-add duplicates):\n"
                + json.dumps(queues, indent=2)
            )
        return None

    def _sign(self) -> None:
        body = self._read_json_body()
        cid = body.get("conversation_id")
        if not cid:
            raise _BadRequest("`conversation_id` required to sign")

        state = self.config.conversations.convos.get(cid)
        kind = state.kind if state else "morning"

        # Queues kind has no contract to sign — it's mutation-only. Treat
        # /sign as an acknowledgement that the user is done.
        if kind == "queues":
            mutations = list(state.queue_mutations) if state else []
            self._send_json(200, {
                "kind": "queues",
                "queue_mutations_applied": mutations,
            })
            return

        priorities = self.config.conversations.priorities_for(cid)
        if not priorities:
            raise _BadRequest("no priorities crystallized in this conversation")
        settings = self.config.conversations.settings_for(cid)
        ration = int(body.get(
            "entertainment_ration_min", settings.entertainment_ration_min
        ))
        threshold = int(body.get("threshold_pct", settings.threshold_pct))
        notes = body.get("notes")

        # Review writes tomorrow's contract (date offset +1 day).
        when = None
        if kind == "review":
            from datetime import datetime, timedelta, timezone
            when = datetime.now(timezone.utc) + timedelta(days=1)
        contract = bind_morning_contract(
            priorities=priorities,
            entertainment_ration_min=ration,
            threshold_pct=threshold,
            notes=notes,
            when=when,
            save_to=self.config.contract_path,
        )
        self._send_json(201, {
            "kind": kind,
            "contract": json.loads(contract.model_dump_json()),
        })

    # ------------------------------------------------------------------
    # Static file serving (for /onboard)
    # ------------------------------------------------------------------

    def _serve_static(self, name: str, mime: str) -> None:
        # Prevent path traversal — names cannot contain '..' or be absolute.
        if ".." in name.split("/") or name.startswith("/"):
            self._send_json(400, {"error": "bad asset path"})
            return
        path = STATIC_DIR / name
        if not path.is_file():
            self._send_json(404, {"error": f"asset not found: {name}"})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _serve_chat_shell(self, *, kind: str) -> None:
        """Render onboard.html with the kind injected so the same SPA
        serves morning ritual, nightly review, and queue maintenance.

        Onboard.html reads ``window.__FL_KIND`` to know which API
        endpoints to hit and how to label things.
        """
        path = STATIC_DIR / "onboard.html"
        if not path.is_file():
            self._send_json(404, {"error": "onboard.html missing"})
            return
        body = path.read_text(encoding="utf-8")
        # Inject kind via a meta tag the JS reads on init. We use a
        # stable replacement marker so multiple shells stay in sync.
        injected = body.replace(
            "<head>",
            f'<head>\n  <meta name="fl-kind" content="{kind}">',
            1,
        )
        encoded = injected.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_doc(self, md_name: str, title: str) -> None:
        # Try the editable-install path first (docs/ next to the package),
        # fall back to the package-data static copy.
        md_path = DOCS_DIR / md_name
        if not md_path.is_file():
            md_path = STATIC_DIR / md_name
        if not md_path.is_file():
            self._send_json(404, {
                "error": f"doc not found: {md_name}",
                "looked_in": [str(DOCS_DIR / md_name), str(STATIC_DIR / md_name)],
            })
            return
        body_html = render_markdown(md_path.read_text(encoding="utf-8"))
        shell = (STATIC_DIR / "about_shell.html").read_text(encoding="utf-8")
        page = shell.replace("{{TITLE}}", title).replace("{{BODY}}", body_html)
        encoded = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(encoded)


class _BadRequest(Exception):
    """Raised inside handlers; converted to HTTP 400."""


def _guess_mime(name: str) -> str:
    if name.endswith(".html"):
        return "text/html; charset=utf-8"
    if name.endswith(".css"):
        return "text/css; charset=utf-8"
    if name.endswith(".js"):
        return "application/javascript; charset=utf-8"
    if name.endswith(".json"):
        return "application/json; charset=utf-8"
    if name.endswith(".svg"):
        return "image/svg+xml"
    if name.endswith(".png"):
        return "image/png"
    return "application/octet-stream"


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
    tick_interval_min: int = 0,
    block: bool = True,
) -> ThreadingHTTPServer:
    """Start the daemon. Returns the server (already listening).

    ``tick_interval_min``: if > 0, daemon runs ``loop.tick()`` every N
    minutes in a background thread. v0 default is 0 (cron-driven).
    """
    if host not in {"127.0.0.1", "localhost", "::1"}:
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
    # ThreadingHTTPServer resolves port=0 to an actual OS-assigned port;
    # read it back so the same-origin allowlist matches what the browser
    # sees in its address bar.
    bound_port = server.server_address[1]
    FounderLoopHandler.allowed_exact_origins = frozenset({
        f"http://127.0.0.1:{bound_port}",
        f"http://localhost:{bound_port}",
        f"http://[::1]:{bound_port}",
    })
    log.info("founder_loop daemon listening on http://%s:%d", host, bound_port)

    stop_scheduler = threading.Event()
    if tick_interval_min and tick_interval_min > 0:
        scheduler = threading.Thread(
            target=_tick_scheduler,
            args=(cfg, tick_interval_min, stop_scheduler),
            daemon=True,
            name="founder_loop-tick-scheduler",
        )
        scheduler.start()
        log.info(
            "tick scheduler started (interval = %d min)", tick_interval_min
        )

    if block:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log.info("shutting down")
            stop_scheduler.set()
            server.shutdown()
    else:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
    return server


def _tick_scheduler(
    cfg: "_Config", interval_min: int, stop_event: threading.Event
) -> None:
    """Background thread: run ``loop.tick()`` every ``interval_min``
    minutes. Skips ticks if no contract is bound (nothing to score
    against). Logs failures but keeps running."""
    interval_s = max(60, interval_min * 60)
    # Sleep first so the daemon's initial state is observable cleanly
    # before the scheduler races in.
    if stop_event.wait(min(interval_s, 30)):
        return
    while not stop_event.is_set():
        try:
            contract = load_latest_contract(cfg.contract_path)
            if contract is None:
                log.debug("scheduler: no contract bound — skipping tick")
            else:
                loop = cfg.make_loop()
                result = loop.tick()
                op = result.action.op
                log.info("scheduler tick: op=%s (registry: %s)",
                         op, result.registry_row_id)
        except Exception as exc:
            log.exception("scheduler tick failed: %s", exc)
        if stop_event.wait(interval_s):
            return


__all__ = ["serve", "FounderLoopHandler"]
