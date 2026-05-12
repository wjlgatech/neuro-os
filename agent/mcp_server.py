"""
neuro-os MCP server — exposes the high-leverage CLI surface as Model
Context Protocol tools so MCP-compatible clients (Claude Code, Cursor,
mcp-cli, anything that speaks MCP stdio) can drive neuro-os directly.

Design choices:

* **Stdio transport only.** The neuro-os daemon already exposes HTTP on
  127.0.0.1:8765 for browser-extension / tray integration. This MCP
  server is for AI-agent integration; AI agents run it as a subprocess
  and speak MCP over stdio. No new network surface, no auth concerns.
* **Thin wrappers, no business logic.** Each tool calls an existing
  ``agent.*`` function and returns the result. The substrate is the
  single source of truth; the MCP layer is just a different envelope.
* **Optional dependency.** ``mcp`` is in ``pyproject.toml`` extras
  (``pip install -e ".[mcp]"``) so the core neuro-os install stays
  small. Importing this module raises a clean error when the SDK is
  absent.
* **No telemetry, no remote calls beyond what the wrapped tools
  already do.** If a tool would call Anthropic Haiku (e.g.
  ``research_synthesize`` with LLM mode), the call originates from the
  wrapped function, not the MCP layer.

Tool surface (9 tools, mirrors the load-bearing CLI subcommands):

  Research (Three-Layer Research OS):
    - research_ingest       — Lane 1 corpus ingestion
    - research_synthesize   — Layer 2 cluster-by-mechanism
    - research_brief        — Layer 3 decision-ready brief
    - research_checkpoint   — stop-condition convergence gate
    - research_dashboard    — rollup + health flags

  Founder loop (anchors + override log):
    - loop_anchor           — faith / relational anchor log
    - loop_urge             — urge event + optional skillify auto-emission

  Cross-vertical:
    - cross_vertical_share_note   — make a note visible to another vertical
    - cross_vertical_query        — read what's visible to a given vertical
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover - import guard
    raise ImportError(
        "The 'mcp' extra is not installed. Run "
        "`pip install -e \".[mcp]\"` (from a checkout of neuro-os) or "
        "`pip install neuro-os[mcp]` (once published)."
    ) from e


_SERVER_NAME = "neuro-os"
_SERVER_INSTRUCTIONS = (
    "neuro-os exposes Three-Layer Research OS, founder-loop, and "
    "cross-vertical primitives as MCP tools. The tool surface mirrors "
    "the CLI subcommands. All persistence goes through the same on-disk "
    "queues the CLI uses (~/.neuro_os_research/, ~/.founder_loop/, "
    "~/.neuro_os/cross_vertical.jsonl), so anything written here is "
    "visible to subsequent `neuro-os ...` CLI runs and vice versa."
)


def build_server() -> FastMCP:
    """Build and return a configured FastMCP server. Public for tests
    so they can introspect the tool list without spawning a process."""
    mcp = FastMCP(name=_SERVER_NAME, instructions=_SERVER_INSTRUCTIONS)
    _register_research_tools(mcp)
    _register_founder_loop_tools(mcp)
    _register_cross_vertical_tools(mcp)
    return mcp


# ---------------------------------------------------------------------------
# Helpers shared across tool wrappers
# ---------------------------------------------------------------------------


def _expanded_path(s: Optional[str]) -> Optional[Path]:
    """Treat None/empty as 'use default home'; expand ~ and env vars."""
    if not s:
        return None
    return Path(s).expanduser()


def _ok(payload: Any) -> str:
    """Render a tool result as a JSON string. MCP tools return plain
    strings; we choose JSON so structured fields round-trip cleanly."""
    return json.dumps(payload, indent=2, default=str)


def _err(message: str) -> str:
    return json.dumps({"error": message})


# ---------------------------------------------------------------------------
# Research vertical tools
# ---------------------------------------------------------------------------


def _register_research_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def research_ingest(
        source_dir: str,
        prefer: str = "auto",
        no_llm: bool = False,
        home: Optional[str] = None,
    ) -> str:
        """Run Lane 1 corpus ingestion against a directory of source files.

        Walks `.txt` / `.md` / `.pdf` files in source_dir, extracts
        MechanismCardProposals, writes them to the pending queue.

        Args:
            source_dir: directory containing .txt / .md / .pdf files.
            prefer: extractor choice — 'auto' / 'gbrain' / 'local'.
            no_llm: if True, force the regex heuristic (no API call).
            home: override the default ~/.neuro_os_research/ home.

        Returns: IngestionRun summary as JSON.
        """
        from agent.research.ingest import ingest

        src = _expanded_path(source_dir)
        if src is None or not src.exists():
            return _err(f"source_dir not found: {source_dir}")
        if not src.is_dir():
            return _err(f"source_dir is not a directory: {source_dir}")
        # prefer=local is the MCP default behavior; the 'auto/gbrain'
        # paths require subprocess wiring out of scope for v0.
        if prefer not in ("auto", "gbrain", "local"):
            return _err(f"invalid prefer={prefer!r}")
        llm_fn = None if no_llm else _make_anthropic_llm_fn()
        run = ingest(source_dir=src, llm_fn=llm_fn, home=_expanded_path(home))
        return _ok(json.loads(run.model_dump_json()))

    @mcp.tool()
    def research_synthesize(
        window_days: int = 30,
        min_cluster_size: int = 2,
        no_llm: bool = False,
        home: Optional[str] = None,
    ) -> str:
        """Layer 2 — cluster accepted MechanismCards by mechanism.

        Args:
            window_days: lookback for accepted cards (1-365).
            min_cluster_size: minimum members per cluster (1-20).
            no_llm: force the heuristic Jaccard clusterer.
            home: override the default ~/.neuro_os_research/.

        Returns: SynthesisRun summary as JSON.
        """
        from agent.research.synthesis import run_synthesis

        if not 1 <= window_days <= 365:
            return _err("window_days must be 1..365")
        if not 1 <= min_cluster_size <= 20:
            return _err("min_cluster_size must be 1..20")
        llm_fn = None if no_llm else _make_anthropic_cluster_fn()
        run = run_synthesis(
            home=_expanded_path(home),
            window_days=window_days,
            min_cluster_size=min_cluster_size,
            llm_fn=llm_fn,
        )
        return _ok(json.loads(run.model_dump_json()))

    @mcp.tool()
    def research_brief(
        cluster_id: str,
        context_json: str,
        no_llm: bool = False,
        home: Optional[str] = None,
    ) -> str:
        """Layer 3 — decision-ready brief for one cluster grounded in a
        user-supplied ProjectContext.

        Args:
            cluster_id: cluster_id from a prior research_synthesize run.
            context_json: JSON string of a ProjectContext (project_name,
                          current_questions, collaborators,
                          pending_decisions, framework_name).
            no_llm: force the templated heuristic brief.
            home: override the default ~/.neuro_os_research/.

        Returns: DecisionBrief as JSON.
        """
        from agent.research.briefs import (
            ProjectContext,
            generate_brief,
            write_brief,
        )
        from agent.research.synthesis import list_synthesis_runs

        try:
            ctx = ProjectContext.model_validate_json(context_json)
        except Exception as e:
            return _err(f"invalid ProjectContext: {e}")

        home_path = _expanded_path(home)
        target_cluster = None
        target_run = None
        for run in list_synthesis_runs(home=home_path, limit=50):
            for c in run.clusters:
                if c.cluster_id == cluster_id:
                    target_cluster = c
                    target_run = run
                    break
            if target_cluster is not None:
                break
        if target_cluster is None:
            return _err(
                f"cluster_id {cluster_id!r} not found in the 50 most "
                f"recent synthesis runs. Run research_synthesize first."
            )

        llm_fn = None if no_llm else _make_anthropic_brief_fn()
        brief = generate_brief(
            cluster=target_cluster,
            context=ctx,
            synthesis_run_id=target_run.run_id,
            llm_fn=llm_fn,
        )
        write_brief(brief, home=home_path)
        return _ok(json.loads(brief.model_dump_json()))

    @mcp.tool()
    def research_checkpoint(
        brief_produced: bool,
        mental_model_clearer: bool,
        note: Optional[str] = None,
        home: Optional[str] = None,
    ) -> str:
        """Log a stop-condition checkpoint.

        Args:
            brief_produced: did the last synthesis cycle produce a brief?
            mental_model_clearer: did your mental model on the active
                                   thesis get clearer?
            note: optional free-text note (≤ 600 chars).
            home: override the default ~/.neuro_os_research/.

        Returns: confirmation + current trailing non-converging streak.
        Two consecutive non-converging checkpoints fire
        `system_not_converging` on the dashboard.
        """
        import uuid
        from datetime import datetime, timezone

        from agent.research.checkpoints import (
            CONVERGENCE_WARNING_THRESHOLD,
            ResearchCheckpoint,
            recent_no_streak,
            write_checkpoint,
        )

        home_path = _expanded_path(home)
        clean_note = (note or "").strip()[:600] or None
        checkpoint = ResearchCheckpoint(
            checkpoint_id=f"chk-{uuid.uuid4().hex[:10]}",
            ts=datetime.now(timezone.utc),
            brief_produced=brief_produced,
            mental_model_clearer=mental_model_clearer,
            note=clean_note,
        )
        write_checkpoint(checkpoint, home=home_path)
        streak = recent_no_streak(home=home_path, k=10)
        return _ok({
            "checkpoint_id": checkpoint.checkpoint_id,
            "trailing_non_converging_streak": streak,
            "convergence_warning_fires_at": CONVERGENCE_WARNING_THRESHOLD,
            "warning": streak >= CONVERGENCE_WARNING_THRESHOLD,
        })

    @mcp.tool()
    def research_dashboard(
        window_days: int = 30,
        home: Optional[str] = None,
    ) -> str:
        """Read-only rollup of the research vertical.

        Args:
            window_days: lookback (1-365). Default 30.
            home: override the default ~/.neuro_os_research/.

        Returns: DashboardSummary as JSON (compound curve, drift
        histogram, stick-rate, tier_balance, verdict_histogram,
        system_health_flags, checkpoint convergence).
        """
        from agent.research.dashboard import build_dashboard_summary

        if not 1 <= window_days <= 365:
            return _err("window_days must be 1..365")
        summary = build_dashboard_summary(
            home=_expanded_path(home), window_days=window_days,
        )
        return _ok(json.loads(summary.model_dump_json()))


# ---------------------------------------------------------------------------
# Founder-loop tools
# ---------------------------------------------------------------------------


def _register_founder_loop_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def loop_anchor(
        kind: str,
        context: str,
        home: Optional[str] = None,
    ) -> str:
        """Log a faith or relational anchor.

        Args:
            kind: 'faith' or 'relational'.
            context: short freeform context (≤ 400 chars).
            home: override ~/.founder_loop/.

        Returns: Anchor record as JSON. Anchors are used by the nightly
        rollup ('faith: 5/7' style) and by the dashboard.
        """
        from agent.founder_loop.anchors import write_anchor

        if kind not in ("faith", "relational"):
            return _err("kind must be 'faith' or 'relational'")
        clean = (context or "").strip()[:400]
        if not clean:
            return _err("context is required (≥ 1 char)")
        anchor = write_anchor(
            kind=kind, context=clean, home=_expanded_path(home),
        )
        return _ok(json.loads(anchor.model_dump_json()))

    @mcp.tool()
    def loop_urge(
        urge_type: str,
        context: Optional[str] = None,
        override_of: Optional[str] = None,
        override_vertical: str = "founder_loop",
        events_path: Optional[str] = None,
    ) -> str:
        """Log an urge event and OPTIONALLY auto-emit a skillify
        OverrideEvent in the same call (mirrors `neuro-os loop urge
        --override-of <mode>`).

        Args:
            urge_type: urge label ('entertainment' / 'novelty' /
                       'escape' / 'social' / 'frustration' / 'other').
            context: short freeform context (≤ 400 chars).
            override_of: if set, the drift_mode the user overrode (e.g.
                         'authority_acceptor'). Triggers skillify
                         auto-emission so repeated overrides become
                         catalog-revision proposals.
            override_vertical: vertical that owns the drift_mode
                               ('founder_loop' default; or 'research' /
                               'investment' / 'startup').
            events_path: override the default
                         ~/.founder_loop/founder_events.jsonl.

        Returns: UrgeEvent + (optionally) OverrideEvent JSON.
        """
        from agent.founder_loop.urge_log import log_urge_event
        from agent.skillify import write_override_event

        valid_urges = {
            "entertainment", "novelty", "escape", "social", "frustration",
            "other",
        }
        if urge_type not in valid_urges:
            return _err(f"urge_type must be one of {sorted(valid_urges)}")
        clean_ctx = (context or "").strip()[:400]

        path = (
            _expanded_path(events_path)
            if events_path
            else Path.home() / ".founder_loop" / "founder_events.jsonl"
        )
        try:
            event = log_urge_event(
                urge_type=urge_type, context=clean_ctx, path=path,
            )
        except Exception as e:
            return _err(f"log_urge_event failed: {e}")

        payload: Dict[str, Any] = json.loads(event.model_dump_json())
        if override_of:
            try:
                override = write_override_event(
                    vertical=override_vertical,
                    drift_mode=override_of,
                    user_action=clean_ctx or urge_type,
                    suggested_action=None,
                    notes=f"Auto-emitted from MCP `loop_urge {urge_type}`",
                )
                payload["override_event"] = json.loads(override.model_dump_json())
            except Exception as e:
                payload["override_event_error"] = str(e)
        return _ok(payload)


# ---------------------------------------------------------------------------
# Cross-vertical tools
# ---------------------------------------------------------------------------


def _register_cross_vertical_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def cross_vertical_share_note(
        note_id: str,
        add_visible: List[str],
        store: Optional[str] = None,
    ) -> str:
        """Share a VerticalNote with additional verticals (or with
        '__all__'). Default visibility is the source vertical only;
        this is the explicit broadening event.

        Args:
            note_id: id of the VerticalNote to broaden.
            add_visible: list of vertical names to add to visibility
                         (e.g. ['investment', 'startup']) OR
                         ['__all__'] for full broadcast.
            store: override the cross_vertical.jsonl store path.

        Returns: confirmation JSON.
        """
        from agent.cross_vertical import share_note

        if not note_id:
            return _err("note_id is required")
        if not add_visible:
            return _err("add_visible must contain ≥1 vertical name")
        try:
            share_note(
                note_id=note_id,
                add_visible=add_visible,
                store=_expanded_path(store),
            )
        except Exception as e:
            return _err(f"share_note failed: {e}")
        return _ok({
            "note_id": note_id,
            "added_visible": add_visible,
        })

    @mcp.tool()
    def cross_vertical_query(
        reader: str,
        kinds: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        store: Optional[str] = None,
    ) -> str:
        """List VerticalNotes visible to the given reader vertical.

        Args:
            reader: vertical issuing the read ('research' / 'investment'
                    / 'startup' / 'founder_loop').
            kinds: optional filter — only notes with these note_kind values
                   (e.g. ['mechanism_card']).
            sources: optional filter — only notes from these source
                     verticals.
            store: override the cross_vertical.jsonl store path.

        Returns: list of VerticalNote dicts.
        """
        from agent.cross_vertical import query

        valid_verticals = {"research", "investment", "startup", "founder_loop"}
        if reader not in valid_verticals:
            return _err(f"reader must be one of {sorted(valid_verticals)}")
        notes = query(
            reader=reader,
            kinds=kinds,
            sources=sources,
            store=_expanded_path(store),
        )
        return _ok([json.loads(n.model_dump_json()) for n in notes])


# ---------------------------------------------------------------------------
# LLM callable factories (re-uses the same pattern as agent.cli)
# ---------------------------------------------------------------------------


def _make_anthropic_llm_fn():
    """Build an LLM callable wired to Anthropic Haiku for ingest. Returns
    None when ANTHROPIC_API_KEY is absent or the SDK is missing — the
    wrapped functions then fall back to their heuristic paths."""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    client = anthropic.Anthropic()

    def llm_fn(system_prompt: str, user_text: str):
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
        )
        body = "".join(
            getattr(b, "text", "") for b in resp.content
            if getattr(b, "type", None) == "text"
        )
        start = body.find("[")
        end = body.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return []
        try:
            parsed = json.loads(body[start:end + 1])
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [r for r in parsed if isinstance(r, dict)]

    return llm_fn


def _make_anthropic_cluster_fn():
    """Same shape as the ingest llm_fn — used by run_synthesis."""
    return _make_anthropic_llm_fn()


def _make_anthropic_brief_fn():
    """Brief LLM returns a single dict, not a list. Mirrors agent/cli.py."""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    client = anthropic.Anthropic()

    def llm_fn(system_prompt: str, user_text: str):
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
        )
        body = "".join(
            getattr(b, "text", "") for b in resp.content
            if getattr(b, "type", None) == "text"
        )
        start = body.find("{")
        end = body.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(body[start:end + 1])
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    return llm_fn


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Console-script entry point. Reads MCP messages on stdin, writes
    responses on stdout. Killed by the parent process or SIGINT."""
    server = build_server()
    server.run()  # stdio transport is the FastMCP default


if __name__ == "__main__":
    main()


__all__ = ["build_server", "main"]
