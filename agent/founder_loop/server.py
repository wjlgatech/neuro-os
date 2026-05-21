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
        research_home: Optional[Path] = None,
    ) -> None:
        self.registry_path = registry_path
        self.contract_path = contract_path
        self.workflowx_fixture = workflowx_fixture
        self.events_path = events_path
        self.use_llm = use_llm
        self.api_key = api_key
        self.research_home = research_home  # None → default ~/.neuro_os_research
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
        # Tracks the pipeline run opened at ingest time so compress/express
        # can attach to it without the client needing to pass a run_id.
        self.current_pipeline_run_id: Optional[str] = None

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
        elif path in ("/", "/dashboard", "/dashboard/"):
            self._serve_dashboard_page()
        elif path == "/dashboard/data":
            self._dashboard_data()
        elif path in ("/onboard", "/onboard/"):
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
        elif path in ("/research", "/research/"):
            self._serve_research_workspace_page()
        elif path == "/research/state":
            self._research_state()
        elif path in (
            "/research/living-knowledge",
            "/research/living-knowledge/",
        ):
            self._serve_living_knowledge_page()
        elif path == "/research/living-knowledge/data":
            self._living_knowledge_data()
        elif path in ("/research/review", "/research/review/"):
            self._serve_research_review_page()
        elif path == "/research/review/data":
            self._research_review_data()
        elif path in ("/invest/dashboard", "/invest/dashboard/"):
            self._serve_invest_dashboard_page()
        elif path == "/invest/dashboard/data":
            self._invest_dashboard_data(query)
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
        elif path == "/research/living-knowledge/express":
            self._living_knowledge_express()
        elif path == "/research/living-knowledge/reveal":
            self._living_knowledge_reveal()
        elif path == "/research/living-knowledge/chat":
            self._living_knowledge_chat()
        elif path == "/research/living-knowledge/delete":
            self._living_knowledge_delete()
        elif path == "/research/living-knowledge/restore":
            self._living_knowledge_restore()
        elif path == "/queues-restore":
            self._queues_restore()
        elif path == "/research/review/accept":
            self._research_review_accept()
        elif path == "/research/review/reject":
            self._research_review_reject()
        elif path == "/research/ingest":
            self._research_ingest()
        elif path == "/research/compress":
            self._research_compress()
        elif path == "/priority/evidence":
            self._priority_evidence()
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
            # Amend mode: if /onboard reopens with today already
            # signed, load existing priorities + settings into the
            # new conversation so additions APPEND rather than overwrite.
            seed_priorities = None
            seed_settings = None
            amend_mode = False
            if kind == "morning":
                existing = load_latest_contract(self.config.contract_path)
                today_utc = datetime.now(timezone.utc).date().isoformat()
                if existing is not None and existing.date == today_utc:
                    from agent.founder_loop.conversation import ContractSettings
                    seed_priorities = list(existing.priorities)
                    seed_settings = ContractSettings(
                        entertainment_ration_min=existing.entertainment_ration_min,
                        threshold_pct=existing.threshold_pct,
                    )
                    amend_mode = True
            cid, greeting = self.config.conversations.start(
                kind=kind,
                kickoff=kickoff,
                seed_priorities=seed_priorities,
                seed_settings=seed_settings,
            )
            initial_priorities = (
                [p.model_dump() for p in seed_priorities]
                if seed_priorities else []
            )
            if seed_settings is not None:
                from dataclasses import asdict as _asdict
                initial_settings = _asdict(seed_settings)
            else:
                initial_settings = {
                    "entertainment_ration_min": 60,
                    "threshold_pct": 90,
                }
            self._send_json(200, {
                "conversation_id": cid,
                "kind": kind,
                "assistant_text": greeting,
                "priorities": initial_priorities,
                "settings": initial_settings,
                "can_sign": amend_mode,
                "amend_mode": amend_mode,
                "using_llm": bool(self.config.api_key and self.config.use_llm),
                "queue_mutations": [],
                "kickoff": kickoff,
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
    # Priority evidence — manual flip, mirrors `neuro-os loop evidence`.
    # ------------------------------------------------------------------

    def _priority_evidence(self) -> None:
        """POST /priority/evidence — mark a priority as evidenced.

        Body: {"title": "<unique-substring>", "proof": "<proof-string>"}

        Returns the updated priority on success, or {"error": "..."} with
        a 400 / 404 on bad input. The CLI handler at
        ``_cmd_loop_evidence`` performs the same flow.
        """
        from agent.founder_loop.contract import save_contract
        from agent.founder_loop.priorities import mark_evidenced

        body = self._read_json_body()
        title = (body.get("title") or "").strip()
        proof = (body.get("proof") or "").strip()
        if not title or not proof:
            self._send_json(400, {
                "error": "both 'title' and 'proof' are required",
            })
            return

        contract = load_latest_contract(self.config.contract_path)
        if contract is None:
            self._send_json(404, {"error": "no contract bound for today"})
            return

        needle = title.lower()
        matches = [p for p in contract.priorities if needle in p.title.lower()]
        if not matches:
            self._send_json(404, {
                "error": f"no priority matches {title!r}",
                "candidates": [p.title for p in contract.priorities],
            })
            return
        if len(matches) > 1:
            self._send_json(400, {
                "error": f"ambiguous title {title!r}",
                "matches": [p.title for p in matches],
            })
            return

        target = matches[0]
        if target.status == "evidenced":
            self._send_json(200, {
                "ok": True,
                "already": True,
                "priority": json.loads(target.model_dump_json()),
            })
            return

        try:
            updated = mark_evidenced(target, proof)
        except ValueError as e:
            self._send_json(400, {"error": str(e)})
            return

        new_priorities = [
            updated if p.title == target.title else p
            for p in contract.priorities
        ]
        new_contract = contract.model_copy(
            update={"priorities": new_priorities}
        )
        save_contract(new_contract, self.config.contract_path)
        self._send_json(200, {
            "ok": True,
            "already": False,
            "priority": json.loads(updated.model_dump_json()),
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

    # ------------------------------------------------------------------
    # Unified dashboard at "/" — 4 vertical tiles + a next-step hint
    # ------------------------------------------------------------------

    def _serve_dashboard_page(self) -> None:
        path = STATIC_DIR / "dashboard.html"
        if not path.is_file():
            self._send_json(500, {"error": "dashboard.html missing"})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _dashboard_data(self) -> None:
        """One read of every vertical's headline number for the homepage.

        Pure read-on-poll. Each block is defensive — if a vertical's
        on-disk state is missing/corrupt, the field is None and the
        tile renders a "not bound" hint rather than 500ing the page."""
        out: Dict[str, Any] = {
            "loop": self._dashboard_loop_block(),
            "research": self._dashboard_research_block(),
            "invest": self._dashboard_invest_block(),
            "startup": self._dashboard_startup_block(),
        }
        self._send_json(200, out)

    def _dashboard_loop_block(self) -> Dict[str, Any]:
        contract = load_latest_contract(self.config.contract_path)
        if contract is None:
            return {"contract_bound": False, "tank": None, "priorities_count": 0}
        all_rows = read_registry(self.config.registry_path)
        today_rows = filter_by_day(
            all_rows, datetime.now(timezone.utc).date()
        )
        tank = compute_tank(today_rows, contract=contract)
        return {
            "contract_bound": True,
            "tank": json.loads(tank.model_dump_json()),
            "priorities_count": len(contract.priorities),
        }

    def _dashboard_research_block(self) -> Dict[str, Any]:
        """Research headline: pending proposals count + active thesis.

        Reads from ``~/.neuro_os_research/proposals/pending/*.json`` and
        the research contract; both are optional."""
        home = Path.home() / ".neuro_os_research"
        pending = 0
        try:
            pdir = home / "proposals" / "pending"
            if pdir.is_dir():
                pending = sum(
                    1 for p in pdir.iterdir()
                    if p.is_file() and p.suffix == ".json"
                )
        except OSError:
            pending = 0
        active_thesis = None
        cards_total = 0
        try:
            contract_path = home / "contract.json"
            if contract_path.is_file():
                data = json.loads(contract_path.read_text(encoding="utf-8"))
                active_thesis = data.get("active_thesis_id")
        except (OSError, json.JSONDecodeError):
            active_thesis = None
        try:
            cards_dir = home / "cards"
            if cards_dir.is_dir():
                cards_total = sum(
                    1 for p in cards_dir.iterdir()
                    if p.is_file() and p.suffix == ".json"
                )
        except OSError:
            cards_total = 0
        return {
            "pending_proposals": pending,
            "active_thesis_id": active_thesis,
            "cards_total": cards_total,
        }

    def _dashboard_invest_block(self) -> Dict[str, Any]:
        home = Path.home() / ".neuro_os_invest"
        col_usd = None
        open_positions = 0
        try:
            col_path = home / "cost_of_living.json"
            if col_path.is_file():
                d = json.loads(col_path.read_text(encoding="utf-8"))
                col_usd = d.get("monthly_usd")
        except (OSError, json.JSONDecodeError):
            col_usd = None
        try:
            trades_path = home / "trades.jsonl"
            if trades_path.is_file():
                open_ids: set[str] = set()
                closed_ids: set[str] = set()
                for line in trades_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    tid = row.get("trade_id") or row.get("id")
                    action = row.get("action")
                    if action == "close":
                        closed_ids.add(tid)
                    elif tid:
                        open_ids.add(tid)
                open_positions = len(open_ids - closed_ids)
        except OSError:
            open_positions = 0
        return {
            "cost_of_living_usd": col_usd,
            "open_positions": open_positions,
        }

    def _dashboard_startup_block(self) -> Dict[str, Any]:
        home = Path.home() / ".neuro_os_startup"
        active_hypothesis = None
        ticks_today = 0
        try:
            contract_path = home / "contract.json"
            if contract_path.is_file():
                d = json.loads(contract_path.read_text(encoding="utf-8"))
                active_hypothesis = d.get("active_hypothesis_id")
        except (OSError, json.JSONDecodeError):
            active_hypothesis = None
        try:
            registry_path = home / "registry.jsonl"
            if registry_path.is_file():
                today = datetime.now(timezone.utc).date().isoformat()
                for line in registry_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = row.get("ts") or row.get("timestamp") or ""
                    if ts.startswith(today):
                        ticks_today += 1
        except OSError:
            ticks_today = 0
        return {
            "active_hypothesis_id": active_hypothesis,
            "ticks_today": ticks_today,
        }

    # ------------------------------------------------------------------
    # Living Knowledge (research vertical) — Layer 4 + 5 UI
    # ------------------------------------------------------------------

    def _research_home(self) -> Optional[Path]:
        """Return the research home dir or None to use the default
        ``~/.neuro_os_research``. Pass ``research_home`` to ``serve()``
        to override (tests use this for isolation)."""
        return self.config.research_home

    # ------------------------------------------------------------------
    # Research workspace — the unified ingest → review → compress → express
    # entry point. The other research browser pages (review, living-knowledge)
    # are deep-link surfaces; this is the home.
    # ------------------------------------------------------------------

    def _serve_research_workspace_page(self) -> None:
        path = STATIC_DIR / "research-workspace.html"
        if not path.is_file():
            self._send_json(500, {"error": "research-workspace.html missing"})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _research_state(self) -> None:
        """Counts that drive the workspace strip.

        All reads are defensive — a missing home dir returns zero, never
        500. The strip is a one-glance status; if something is wrong on
        disk the user finds out from the specific section that needs it."""
        from agent.research.compress import list_compressions
        from agent.research.expression import list_expressions
        from agent.research.proposals import list_proposals

        home = self._research_home()
        out: Dict[str, Any] = {
            "sources_ingested": 0,
            "proposals_pending": 0,
            "cards_accepted": 0,
            "compressions_count": 0,
            "expressions_count": 0,
            "llm_available": bool(
                self.config.api_key and self.config.use_llm
            ),
            "compressions": [],
        }
        try:
            pending = list_proposals(status="pending", home=home)
            out["proposals_pending"] = len(pending)
        except Exception:
            pass
        try:
            accepted = list_proposals(status="accepted", home=home)
            out["cards_accepted"] = len(accepted)
        except Exception:
            pass
        try:
            comps = list_compressions(home=home, limit=10)
            out["compressions_count"] = len(comps)
            out["compressions"] = [
                {
                    "id": c.compression_id,
                    "l0_count": len(c.level_0_nodes),
                    "l1_count": len(c.level_1_nodes),
                    "cards_total": len(c.level_2_nodes),
                }
                for c in comps
            ]
        except Exception:
            pass
        try:
            exprs = list_expressions(home=home)
            out["expressions_count"] = len(exprs)
        except Exception:
            pass
        # sources_ingested = unique source files referenced across all
        # proposals (pending + accepted + rejected). Cheap approximation.
        try:
            home_dir = Path.home() / ".neuro_os_research" if home is None else home
            srcs: set[str] = set()
            for sub in ("pending", "accepted", "rejected"):
                d = home_dir / "proposals" / sub
                if d.is_dir():
                    for p in d.iterdir():
                        if p.is_file() and p.suffix == ".json":
                            try:
                                data = json.loads(p.read_text(encoding="utf-8"))
                                sid = data.get("source_id")
                                if sid:
                                    srcs.add(sid)
                            except (OSError, json.JSONDecodeError):
                                continue
            out["sources_ingested"] = len(srcs)
        except Exception:
            pass
        self._send_json(200, out)

    def _research_ingest(self) -> None:
        """POST /research/ingest

        Body modes (mutually exclusive):
            {"mode": "dir",   "source_dir": "/abs/path", "no_llm": false}
            {"mode": "url",   "url": "https://...pdf"}
            {"mode": "paste", "title": "...", "text": "..."}

        Returns the IngestionRun shape on success:
            {sources_scanned, sources_skipped_unchanged, proposals_emitted,
             extraction_method, run_id}
        Or {"error": "..."} on input / runtime failure.
        """
        from agent.research.ingest import ingest as ingest_fn

        body = self._read_json_body()
        mode = body.get("mode")
        if mode not in ("dir", "url", "paste"):
            raise _BadRequest("mode must be one of: dir, url, paste")

        # Resolve source_dir for each mode. URL + paste materialize a
        # tempdir so the same ingest() entry point handles all three.
        cleanup_tempdir: Optional[Path] = None
        try:
            if mode == "dir":
                raw = body.get("source_dir", "")
                if not raw:
                    raise _BadRequest("source_dir required for mode=dir")
                source_dir = Path(raw).expanduser().resolve()
                if not source_dir.is_dir():
                    raise _BadRequest(
                        f"not a directory: {source_dir}. Use an absolute "
                        "path to a folder of .txt/.md/.pdf files."
                    )
                no_llm = bool(body.get("no_llm", False))
            elif mode == "url":
                url = body.get("url", "").strip()
                if not url or not (
                    url.startswith("http://") or url.startswith("https://")
                ):
                    raise _BadRequest("url must start with http:// or https://")
                source_dir, cleanup_tempdir = self._download_url_to_tempdir(url)
                no_llm = bool(body.get("no_llm", False))
            else:  # paste
                title = (body.get("title") or "").strip()
                text = body.get("text") or ""
                if not title or not text:
                    raise _BadRequest(
                        "paste mode requires both 'title' and 'text'"
                    )
                source_dir, cleanup_tempdir = self._paste_to_tempdir(title, text)
                no_llm = bool(body.get("no_llm", False))

            # Pick the LLM callable. Prefer OpenAI when OPENAI_API_KEY is
            # set (e.g. when Anthropic quota is exhausted); fall back to
            # Anthropic; fall back to heuristic when no_llm or no key.
            llm_fn = None
            if not no_llm and self.config.use_llm:
                import os as _os
                if _os.environ.get("OPENAI_API_KEY"):
                    llm_fn = self._build_openai_extractor()
                elif self.config.api_key:
                    llm_fn = self._build_anthropic_extractor()

            home = self._research_home()
            run = ingest_fn(
                source_dir=source_dir,
                llm_fn=llm_fn,
                home=home,
            )
            # Open a pipeline run and record the ingest stage so downstream
            # compress/express calls can attach to the same run.
            if home is not None:
                from agent.research.run_registry import open_run, record_stage
                label = f"run-{run.run_id}"
                pipeline_run = open_run(home, label=label)
                record_stage(
                    home,
                    pipeline_run.run_id,
                    "ingest",
                    artifact_id=run.run_id,
                    item_count=run.proposals_emitted,
                )
                self.config.current_pipeline_run_id = pipeline_run.run_id
            else:
                pipeline_run = None

            # Pull read-failure + llm-failure lists from module attrs.
            from agent.research.ingest import (
                load_sources as _load,
                extract_mechanisms as _ext,
            )
            read_failures = getattr(_load, "last_read_failures", []) or []
            llm_errors = getattr(_ext, "last_llm_errors", []) or []
            self._send_json(200, {
                "run_id": run.run_id,
                "pipeline_run_id": pipeline_run.run_id if pipeline_run else None,
                "sources_scanned": run.sources_scanned,
                "sources_skipped_unchanged": run.sources_skipped_unchanged,
                "sources_failed_to_read": [
                    {"name": n, "reason": r} for (n, r) in read_failures
                ],
                "llm_errors": [
                    {"source_id": s, "reason": r} for (s, r) in llm_errors
                ],
                "proposals_emitted": run.proposals_emitted,
                "extraction_method": run.extraction_method,
            })
        finally:
            if cleanup_tempdir is not None and cleanup_tempdir.is_dir():
                # Best-effort cleanup. Sources are already snapshotted
                # in the proposals on disk (each carries source_id +
                # excerpt), so removing the originals is safe.
                import shutil
                shutil.rmtree(cleanup_tempdir, ignore_errors=True)

    def _download_url_to_tempdir(self, url: str) -> tuple[Path, Path]:
        """Fetch a single URL into a fresh tempdir. Returns (dir, dir)
        so the caller can ingest the dir and then clean it up."""
        import tempfile
        import urllib.parse
        import urllib.request
        # Pick a filename from the URL — preserve extension so the
        # ingest router routes correctly (.pdf vs .md vs .txt).
        parsed = urllib.parse.urlparse(url)
        name = Path(parsed.path).name or "fetched"
        if "." not in name:
            name += ".txt"
        tmp = Path(tempfile.mkdtemp(prefix="neuroos-ingest-"))
        target = tmp / name
        # urlopen with a short timeout; fail loudly on non-200.
        req = urllib.request.Request(url, headers={
            "User-Agent": "neuro-os/research-ingest"
        })
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            if resp.status != 200:
                raise _BadRequest(f"fetch failed: HTTP {resp.status}")
            target.write_bytes(resp.read())
        return tmp, tmp

    def _paste_to_tempdir(self, title: str, text: str) -> tuple[Path, Path]:
        """Materialize pasted text as a .md file in a fresh tempdir,
        with a YAML front-matter block carrying the user-supplied title
        so the ingest pipeline picks it up as the source title."""
        import tempfile
        import re
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", title.lower()).strip("-")[:48]
        slug = slug or "paste"
        tmp = Path(tempfile.mkdtemp(prefix="neuroos-ingest-"))
        body = f"---\ntitle: {title}\n---\n\n{text.strip()}\n"
        (tmp / f"{slug}.md").write_text(body, encoding="utf-8")
        return tmp, tmp

    def _build_anthropic_extractor(self):
        """Return an llm_fn matching agent.research.ingest.LLMCallable:
        ``(system_prompt: str, user_message: str) -> List[dict]``.

        Wraps ``anthropic.Anthropic.messages.create``. The model is
        instructed (via the existing system prompt) to emit JSON; this
        wrapper extracts the first JSON array/object it finds and
        returns it as ``List[dict]``. Lazy-imports anthropic so the
        daemon boots without it installed."""
        import json as _json
        import re as _re

        api_key = self.config.api_key

        def _call(system_prompt: str, user_message: str) -> List[Dict[str, Any]]:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            parts: List[str] = []
            for block in resp.content:
                t = getattr(block, "text", None)
                if t:
                    parts.append(t)
            text = "".join(parts).strip()
            if not text:
                return []
            # The system prompt asks for JSON; model often wraps it in
            # ```json fences or pre/post-amble. Strip both.
            fenced = _re.search(
                r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", text, _re.S,
            )
            if fenced:
                text = fenced.group(1)
            else:
                # Best-effort: first '[' to its matching ']' (greedy).
                m = _re.search(r"(\[.*\])", text, _re.S)
                if m:
                    text = m.group(1)
            try:
                parsed = _json.loads(text)
            except _json.JSONDecodeError:
                return []
            if isinstance(parsed, list):
                return [r for r in parsed if isinstance(r, dict)]
            if isinstance(parsed, dict):
                return [parsed]
            return []

        return _call

    def _build_openai_extractor(self):
        """Return an llm_fn using OpenAI gpt-4o-mini via OPENAI_API_KEY."""
        import json as _json
        import os as _os

        api_key = _os.environ.get("OPENAI_API_KEY")

        def _call(system_prompt: str, user_message: str) -> List[Dict[str, Any]]:
            import openai
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=4096,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
            if not text:
                return []
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = _json.loads(text[start:end + 1])
                    if isinstance(parsed, list):
                        return [r for r in parsed if isinstance(r, dict)]
                except _json.JSONDecodeError:
                    pass
            try:
                obj = _json.loads(text)
                if isinstance(obj, dict):
                    for v in obj.values():
                        if isinstance(v, list):
                            return [r for r in v if isinstance(v, dict)]
            except _json.JSONDecodeError:
                pass
            return []

        return _call

    def _research_compress(self) -> None:
        """POST /research/compress — run synthesis (if needed) then
        compress its output into a HierarchicalCompression.

        Body (all optional):
            {"window_days": 30, "min_cluster_size": 2, "max_level_0": 5}

        Returns: {compression_id, l0_count, l1_count, cards_total}
        Or {"error": "..."} if there aren't enough accepted cards.
        """
        from agent.research.compress import (
            compress_from_synthesis,
            write_compression,
        )
        from agent.research.synthesis import run_synthesis

        body = self._read_json_body()
        window_days = int(body.get("window_days") or 30)
        min_cluster_size = int(body.get("min_cluster_size") or 1)
        max_level_0 = int(body.get("max_level_0") or 5)
        home = self._research_home()

        # Step 1 — synthesize accepted cards into clusters.
        run = run_synthesis(
            home=home,
            window_days=window_days,
            min_cluster_size=min_cluster_size,
            llm_fn=None,  # heuristic is reliable for v0; user can pass --llm later
        )
        if not run.clusters:
            self._send_json(200, {
                "error": (
                    f"no accepted cards to compress "
                    f"(input_card_count={run.input_card_count}). "
                    "Accept at least one proposal in the review queue, then try again."
                ),
            })
            return

        # Step 2 — compress the synthesis run.
        compression = compress_from_synthesis(run, max_level_0=max_level_0)
        write_compression(compression, home=home)

        # Attach to the current pipeline run if one is open.
        pipeline_run_id = self.config.current_pipeline_run_id
        if pipeline_run_id and home is not None:
            from agent.research.run_registry import record_stage
            record_stage(
                home,
                pipeline_run_id,
                "compress",
                artifact_id=compression.compression_id,
                item_count=(
                    len(compression.level_0_nodes)
                    + len(compression.level_1_nodes)
                    + len(compression.level_2_nodes)
                ),
            )

        self._send_json(200, {
            "compression_id": compression.compression_id,
            "pipeline_run_id": pipeline_run_id,
            "l0_count": len(compression.level_0_nodes),
            "l1_count": len(compression.level_1_nodes),
            "cards_total": len(compression.level_2_nodes),
        })

    def _serve_living_knowledge_page(self) -> None:
        path = STATIC_DIR / "research-living-knowledge.html"
        if not path.is_file():
            self._send_json(500, {"error": "living-knowledge.html missing"})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _living_knowledge_data(self) -> None:
        """Read the latest compression and all its expressions."""
        from agent.research.compress import latest_compression
        from agent.research.expression import list_expressions

        home = self._research_home()
        compression = latest_compression(home=home)
        if compression is None:
            self._send_json(200, {
                "compression": None,
                "expressions": [],
                "reason": (
                    "no compression yet — run `neuro-os research compress` "
                    "after a synthesis run to populate this view"
                ),
            })
            return
        expressions = list_expressions(
            home=home, compression_id=compression.compression_id,
        )
        self._send_json(200, {
            "compression": json.loads(compression.model_dump_json()),
            "expressions": [
                json.loads(e.model_dump_json()) for e in expressions
            ],
        })

    def _living_knowledge_express(self) -> None:
        from agent.research.expression import record_expression

        body = self._read_json_body()
        required = ("compression_id", "source_node_id", "modality", "title", "content")
        missing = [k for k in required if not body.get(k)]
        if missing:
            self._send_json(400, {"error": f"missing fields: {missing}"})
            return
        try:
            expression = record_expression(
                compression_id=body["compression_id"],
                source_node_id=body["source_node_id"],
                modality=body["modality"],
                title=body["title"],
                content=body["content"],
                tool_hint=body.get("tool_hint") or None,
                home=self._research_home(),
            )
        except (FileNotFoundError, ValueError) as e:
            self._send_json(400, {"error": str(e)})
            return
        self._send_json(200, {"expression": json.loads(expression.model_dump_json())})

    def _living_knowledge_reveal(self) -> None:
        from agent.research.expression import reveal_expression

        body = self._read_json_body()
        expression_id = body.get("expression_id")
        insight = body.get("insight") or body.get("reveals")
        if not expression_id or not insight:
            self._send_json(400, {
                "error": "expression_id and insight are required",
            })
            return
        try:
            updated = reveal_expression(
                expression_id=expression_id,
                reveals=insight,
                feeds_back_to_node_id=body.get("feeds_back_to_node_id") or None,
                home=self._research_home(),
            )
        except (FileNotFoundError, ValueError) as e:
            self._send_json(400, {"error": str(e)})
            return
        self._send_json(200, {"expression": json.loads(updated.model_dump_json())})

    def _living_knowledge_chat(self) -> None:
        """Single-turn assist: brainstorm (suggest expressions) OR
        interview (probe what an expression revealed).

        Falls back to a templated response without an API key. The
        chat is stateless — the client sends all context every turn.
        """
        body = self._read_json_body()
        kind = body.get("kind") or ""
        if kind not in ("brainstorm", "interview"):
            self._send_json(400, {
                "error": "kind must be 'brainstorm' or 'interview'",
            })
            return

        if kind == "brainstorm":
            node_label = (body.get("node_label") or "").strip()[:300]
            node_one_sentence = (body.get("node_one_sentence") or "").strip()[:600]
            modality = (body.get("modality") or "").strip()[:40]
            if not (node_label and node_one_sentence and modality):
                self._send_json(400, {
                    "error": "brainstorm requires node_label, node_one_sentence, modality",
                })
                return
            reply = self._chat_brainstorm(
                node_label=node_label,
                node_one_sentence=node_one_sentence,
                modality=modality,
            )
        else:  # interview
            node_one_sentence = (body.get("node_one_sentence") or "").strip()[:600]
            modality = (body.get("modality") or "").strip()[:40]
            expression_content = (body.get("expression_content") or "").strip()[:2000]
            user_observation = (body.get("user_observation") or "").strip()[:1000]
            if not (node_one_sentence and modality and expression_content):
                self._send_json(400, {
                    "error": (
                        "interview requires node_one_sentence, modality, "
                        "expression_content (and optionally user_observation)"
                    ),
                })
                return
            reply = self._chat_interview(
                node_one_sentence=node_one_sentence,
                modality=modality,
                expression_content=expression_content,
                user_observation=user_observation,
            )

        self._send_json(200, {"reply": reply, "used_llm": bool(self.config.api_key)})

    def _chat_brainstorm(
        self, *, node_label: str, node_one_sentence: str, modality: str,
    ) -> str:
        """Suggest 3 ways to express the principle in the chosen modality."""
        if not self.config.api_key:
            return self._brainstorm_fallback(modality, node_one_sentence)
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.config.api_key)
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=900,
                system=(
                    "You help a researcher express compressed principles in new "
                    "modalities to surface insights the text missed. Be concrete, "
                    "punchy, and structurally faithful to the principle's mechanism. "
                    "Output exactly 3 suggestions, numbered, one paragraph each. No preamble."
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Principle to express:\n"
                        f"  label: {node_label}\n"
                        f"  one_sentence: {node_one_sentence}\n\n"
                        f"Modality: {modality}\n\n"
                        f"Give 3 distinct ways to express this principle as {modality}. "
                        f"Each should preserve the mechanism but reveal something the "
                        f"text version hides."
                    ),
                }],
            )
            return "".join(
                getattr(b, "text", "") for b in resp.content
                if getattr(b, "type", None) == "text"
            ).strip() or self._brainstorm_fallback(modality, node_one_sentence)
        except Exception:
            return self._brainstorm_fallback(modality, node_one_sentence)

    def _chat_interview(
        self,
        *,
        node_one_sentence: str,
        modality: str,
        expression_content: str,
        user_observation: str,
    ) -> str:
        """Help the user crystallize what the expression revealed."""
        if not self.config.api_key:
            return self._interview_fallback(modality, user_observation)
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.config.api_key)
            if not user_observation:
                # First turn: ask a probing question.
                user_msg = (
                    f"Principle:\n  {node_one_sentence}\n\n"
                    f"Just expressed as {modality}:\n\n"
                    f"\"\"\"{expression_content}\"\"\"\n\n"
                    f"Ask ONE probing question that helps the user notice what "
                    f"this {modality} expression reveals about the principle "
                    f"that the text version did not. One question, no preamble."
                )
            else:
                # Second turn: crystallize the user's observation into a reveal sentence.
                user_msg = (
                    f"Principle:\n  {node_one_sentence}\n\n"
                    f"Expressed as {modality}:\n\"\"\"{expression_content}\"\"\"\n\n"
                    f"User's observation:\n\"\"\"{user_observation}\"\"\"\n\n"
                    f"Crystallize the observation into a 1-3 sentence `reveals` "
                    f"string suitable for the expression's reveal field. Be "
                    f"specific about what the {modality} form surfaced that the "
                    f"text version hid. No preamble; just the crystallized text."
                )
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=600,
                system=(
                    "You are a research-coach helping a writer extract insight "
                    "from cross-modal expressions. Keep responses short, specific, "
                    "and mechanism-focused. No flattery, no AI-vocabulary."
                ),
                messages=[{"role": "user", "content": user_msg}],
            )
            return "".join(
                getattr(b, "text", "") for b in resp.content
                if getattr(b, "type", None) == "text"
            ).strip() or self._interview_fallback(modality, user_observation)
        except Exception:
            return self._interview_fallback(modality, user_observation)

    @staticmethod
    def _brainstorm_fallback(modality: str, one_sentence: str) -> str:
        return (
            f"(No ANTHROPIC_API_KEY — using a template.)\n\n"
            f"Three angles to express \"{one_sentence}\" as {modality}:\n\n"
            f"1. STRUCTURAL — instantiate the mechanism literally in the {modality} "
            f"form (e.g., for narrative: write the principle as a character's "
            f"decision rule; for musical: encode it as a recurring motif).\n\n"
            f"2. INVERTED — show what the principle's FAILURE looks like in {modality}: "
            f"what would the system do if the mechanism were absent or broken?\n\n"
            f"3. STRESSED — push the principle to an extreme in {modality} space "
            f"(maximum tempo / maximum scale / maximum conflict) and observe where "
            f"it breaks."
        )

    @staticmethod
    def _interview_fallback(modality: str, user_observation: str) -> str:
        if not user_observation:
            return (
                f"(No ANTHROPIC_API_KEY — using a template question.)\n\n"
                f"What does the {modality} form make visible that the text "
                f"version of this principle did not? Look especially at: timing, "
                f"emotional valence, embodied cost, or what happens at the edges."
            )
        return (
            f"(No ANTHROPIC_API_KEY — using a template crystallization.)\n\n"
            f"The {modality} expression reveals: {user_observation}"
        )

    def _living_knowledge_delete(self) -> None:
        """Soft delete: move the expression file to expressions/_trash/.
        Reversible via /research/living-knowledge/restore within the session."""
        from agent.research.expression import soft_delete_expression

        body = self._read_json_body()
        expression_id = body.get("expression_id")
        if not expression_id:
            self._send_json(400, {"error": "expression_id is required"})
            return
        try:
            path = soft_delete_expression(expression_id, home=self._research_home())
        except FileNotFoundError as e:
            self._send_json(404, {"error": str(e)})
            return
        self._send_json(200, {"trashed_path": str(path), "expression_id": expression_id})

    def _living_knowledge_restore(self) -> None:
        """Restore a soft-deleted expression from _trash/."""
        from agent.research.expression import restore_expression

        body = self._read_json_body()
        expression_id = body.get("expression_id")
        if not expression_id:
            self._send_json(400, {"error": "expression_id is required"})
            return
        try:
            path = restore_expression(expression_id, home=self._research_home())
        except FileNotFoundError as e:
            self._send_json(404, {"error": str(e)})
            return
        self._send_json(200, {"restored_path": str(path), "expression_id": expression_id})

    def _serve_research_review_page(self) -> None:
        path = STATIC_DIR / "research-review.html"
        if not path.is_file():
            self._send_json(500, {"error": "research-review.html missing"})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _serve_invest_dashboard_page(self) -> None:
        path = STATIC_DIR / "invest-dashboard.html"
        if not path.is_file():
            self._send_json(500, {"error": "invest-dashboard.html missing"})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _invest_dashboard_data(self, query: Dict[str, str]) -> None:
        """Read-only rollup of the investment vertical, mirroring the CLI's
        `invest dashboard`. ``window`` defaults to 30 days; query param
        ``window`` clamps to [1, 365]."""
        from agent.investment.config import read_position_theses
        from agent.investment.dashboard import build_dashboard_summary

        try:
            window = int(query.get("window", "30"))
        except ValueError:
            self._send_json(400, {"error": "window must be an integer"})
            return
        if not 1 <= window <= 365:
            self._send_json(400, {"error": "window must be between 1 and 365"})
            return

        # Investment data lives at ~/.neuro_os_investment/ by default.
        # The daemon doesn't yet expose --invest-home; for v0 use the default.
        home: Optional[Path] = None
        try:
            theses = [
                t for t in read_position_theses(home=home)
                if t.status == "active"
            ]
        except Exception:
            theses = []
        try:
            summary = build_dashboard_summary(
                theses=theses, home=home, window_days=window,
            )
        except Exception as e:  # pragma: no cover — defensive
            self._send_json(500, {"error": f"dashboard build failed: {e}"})
            return
        self._send_json(200, {
            "summary": json.loads(summary.model_dump_json()),
        })

    def _research_review_data(self) -> None:
        """Return pending + recently-resolved (accepted/rejected, last 20)
        MechanismCardProposals as JSON so the review UI can render them."""
        from agent.research.proposals import list_proposals

        home = self._research_home()
        pending = list_proposals(home=home, status="pending")
        accepted = list_proposals(home=home, status="accepted")
        rejected = list_proposals(home=home, status="rejected")
        # Newest-first by proposed_at
        accepted_recent = sorted(
            accepted, key=lambda p: p.proposed_at, reverse=True,
        )[:20]
        rejected_recent = sorted(
            rejected, key=lambda p: p.proposed_at, reverse=True,
        )[:20]
        self._send_json(200, {
            "pending": [json.loads(p.model_dump_json()) for p in pending],
            "recently_accepted": [json.loads(p.model_dump_json()) for p in accepted_recent],
            "recently_rejected": [json.loads(p.model_dump_json()) for p in rejected_recent],
        })

    def _research_review_accept(self) -> None:
        """Accept a pending proposal: write a MechanismCard, transition the
        proposal to accepted, upsert any user-supplied entity mentions."""
        from datetime import datetime, timezone

        from agent.cross_vertical import upsert_entity
        from agent.research import MechanismCard
        from agent.research.config import write_mechanism_card
        from agent.research.proposals import (
            list_proposals,
            transition_proposal,
        )

        body = self._read_json_body()
        proposal_id = body.get("proposal_id")
        if not proposal_id:
            self._send_json(400, {"error": "proposal_id is required"})
            return
        raw_mentions = body.get("entity_mentions") or []
        if not isinstance(raw_mentions, list):
            self._send_json(400, {"error": "entity_mentions must be a list"})
            return
        mentions = [
            str(m).strip().lower() for m in raw_mentions
            if isinstance(m, str) and m.strip()
        ]

        home = self._research_home()
        # Find the proposal in pending
        pending = list_proposals(home=home, status="pending")
        prop = next((p for p in pending if p.proposal_id == proposal_id), None)
        if prop is None:
            self._send_json(404, {"error": f"proposal {proposal_id!r} not in pending"})
            return

        try:
            card = MechanismCard(
                id=prop.proposal_id,
                ts=datetime.now(timezone.utc),
                paper_title=prop.paper_title,
                paper_source=prop.paper_source,
                mechanism=prop.mechanism,
                invariant=prop.invariant,
                prediction=prop.prediction,
                failure_mode=prop.failure_mode,
                thesis_id=prop.thesis_id,
                entity_mentions=mentions,
                first_principle=prop.first_principle,
                anti_pattern=prop.anti_pattern,
                transferability_test=prop.transferability_test,
                verdict=prop.verdict,
                one_sentence_compression=prop.one_sentence_compression,
                framework_alignment=list(prop.framework_alignment),
            )
        except Exception as e:
            self._send_json(400, {"error": f"failed to build MechanismCard: {e}"})
            return

        write_mechanism_card(card=card, home=home)
        transition_proposal(
            prop.proposal_id, home=home,
            from_status="pending", to_status="accepted",
        )

        for slug in mentions:
            try:
                upsert_entity(
                    slug=slug,
                    kind="topic",
                    title=slug.replace("-", " ").title(),
                    source_vertical="research",
                    compiled_truth=(
                        f"Mentioned in MechanismCard {card.id} "
                        f"({card.paper_title!r})."
                    ),
                    mentioned_in_note_id=card.id,
                )
            except Exception:
                # entity propagation is best-effort; don't fail the accept
                pass

        self._send_json(200, {
            "accepted_proposal_id": proposal_id,
            "card_id": card.id,
            "entity_mentions": mentions,
        })

    def _research_review_reject(self) -> None:
        from agent.research.proposals import list_proposals, transition_proposal

        body = self._read_json_body()
        proposal_id = body.get("proposal_id")
        if not proposal_id:
            self._send_json(400, {"error": "proposal_id is required"})
            return

        home = self._research_home()
        pending = list_proposals(home=home, status="pending")
        if not any(p.proposal_id == proposal_id for p in pending):
            self._send_json(404, {"error": f"proposal {proposal_id!r} not in pending"})
            return
        try:
            transition_proposal(
                proposal_id, home=home,
                from_status="pending", to_status="rejected",
            )
        except (FileNotFoundError, ValueError) as e:
            self._send_json(400, {"error": str(e)})
            return
        self._send_json(200, {"rejected_proposal_id": proposal_id})

    def _queues_restore(self) -> None:
        """Restore queue files from a client-side snapshot. The /queues
        chat surface keeps a snapshot before each AI-triggered mutation
        and POSTs it here when the user clicks Undo. Atomic per-file."""
        body = self._read_json_body()
        out: Dict[str, Any] = {}
        for q in ("bookmarks_queue", "social_queue", "rubber_duck_venues"):
            if q not in body:
                continue
            target = self.config.queues_dir / f"{q}.json"
            tmp = target.with_suffix(".json.tmp")
            try:
                payload = body[q]
                if not isinstance(payload, list):
                    self._send_json(400, {
                        "error": f"{q} must be a JSON list, got {type(payload).__name__}",
                    })
                    return
                tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                tmp.replace(target)
                out[q] = len(payload)
            except OSError as e:
                self._send_json(500, {"error": f"failed to restore {q}: {e}"})
                return
        self._send_json(200, {"restored": out})

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
    research_home: Optional[Path] = None,
) -> ThreadingHTTPServer:
    """Start the daemon. Returns the server (already listening).

    ``tick_interval_min``: if > 0, daemon runs ``loop.tick()`` every N
    minutes in a background thread. v0 default is 0 (cron-driven).
    ``research_home``: override the research vertical's data dir (useful
    for tests that need an isolated, empty research home).
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
        research_home=research_home,
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
