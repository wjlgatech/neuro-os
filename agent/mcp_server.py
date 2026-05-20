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
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    "neuro-os exposes Three-Layer Research OS, founder-loop, "
    "investment-vertical (Phase 1 options income + Phase 2 mega-trend "
    "sleeve + cost-of-living gap), and cross-vertical primitives as "
    "MCP tools. The tool surface mirrors the CLI subcommands. All "
    "persistence goes through the same on-disk queues the CLI uses "
    "(~/.neuro_os_research/, ~/.neuro_os_investment/, ~/.founder_loop/, "
    "~/.neuro_os/cross_vertical.jsonl), so anything written here is "
    "visible to subsequent `neuro-os ...` CLI runs and vice versa. "
    "Each tool call surfaces a permission prompt in the host client "
    "(Claude Code, Cursor, mcp-cli) — this is the human-in-the-loop "
    "(HITL) gate for transaction-shaped operations. Tools that propose "
    "orders never execute on a real broker; the broker MCP for "
    "execution is a separate, future server."
)


def build_server() -> FastMCP:
    """Build and return a configured FastMCP server. Public for tests
    so they can introspect the tool list without spawning a process."""
    mcp = FastMCP(name=_SERVER_NAME, instructions=_SERVER_INSTRUCTIONS)
    _register_research_tools(mcp)
    _register_founder_loop_tools(mcp)
    _register_cross_vertical_tools(mcp)
    _register_investment_tools(mcp)
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
# Path-allowlist gate for tools that read arbitrary host filesystem paths
# (``research_ingest`` is the main one — it walks .txt/.md/.pdf files and
# ships their contents to the Anthropic API if a key is configured).
#
# Threat model: in autonomous-mode hosts (Claude Code with
# ``--dangerously-skip-permissions``, Cursor full-agent), the per-tool
# confirmation prompt is suppressed. A prompt-injection payload that
# convinces the agent to call ``research_ingest(source_dir="/etc")`` or
# ``~/Library/Mail`` would otherwise succeed without the user seeing it.
# The gate refuses obviously sensitive system / $HOME-dotfile paths and
# allowlists the rest (under $HOME minus the sensitive set, plus tmp).
# ---------------------------------------------------------------------------


def _is_under(child: Path, parent: Path) -> bool:
    """True if ``child`` is ``parent`` or a descendant of it. Both must
    already be resolved (absolute, symlinks followed)."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


# System paths we never let an agent ingest from. Narrower than just
# ``/var`` because macOS resolves $TMPDIR (pytest's tmp_path) to
# ``/private/var/folders/...`` — a blanket ``/var`` deny would block
# every test fixture. We list the actual sensitive ``/var`` subpaths
# instead (logs, db, mail, spool, etc.).
_SYSTEM_DENY_PREFIXES: Tuple[Path, ...] = (
    Path("/etc"), Path("/private/etc"),
    Path("/var/log"), Path("/private/var/log"),
    Path("/var/db"), Path("/private/var/db"),
    Path("/var/mail"), Path("/private/var/mail"),
    Path("/var/spool"), Path("/private/var/spool"),
    Path("/var/root"), Path("/private/var/root"),
    Path("/var/audit"), Path("/private/var/audit"),
    Path("/usr"),
    Path("/System"),
    Path("/Library"),
    Path("/sys"),
    Path("/proc"),
    Path("/dev"),
    Path("/root"),
    Path("/boot"),
)


def _sensitive_home_subdirs() -> Tuple[Path, ...]:
    """$HOME subdirectories that hold credentials, keys, mail, IDE
    config, and other sensitive content. Resolved per-call because
    ``Path.home()`` is process-cwd-independent but a test that
    monkeypatches HOME via env var benefits from re-resolution."""
    home = Path.home().resolve()
    return (
        home / "Library",
        home / ".ssh",
        home / ".gnupg",
        home / ".aws",
        home / ".config",
        home / ".anthropic",
        home / ".docker",
        home / ".kube",
        home / ".npm",
        home / ".cargo",
        home / ".password-store",
        home / ".thunderbird",
    )


def _is_safe_ingest_path(path: Path) -> Tuple[bool, str]:
    """Gate the path passed to MCP file-reading tools. Returns
    ``(allowed, reason)`` — ``reason`` is shown to the agent on reject
    so it can ask the user to set ``NEURO_OS_MCP_INGEST_ALLOWED_PATHS``
    if the path is legitimate.

    Order:
      1. Sensitive ``$HOME`` subdirs (deny). Wins over tmp so a test
         that monkeypatches ``HOME`` into ``$TMPDIR`` still rejects
         ``$HOME/.ssh`` correctly.
      2. System denylist (deny). Narrow ``/var`` paths only so macOS
         pytest ``/private/var/folders/...`` isn't caught.
      3. Env-var user allowlist (allow).
      4. Tmp roots (allow).
      5. Default ``$HOME`` (allow).
      6. Default deny."""
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as e:
        return False, f"path cannot be resolved: {e}"

    # 1. Sensitive $HOME subdirs — hard deny. Catches ~/.ssh even when
    # HOME is monkeypatched into a tmp location.
    for prefix in _sensitive_home_subdirs():
        if _is_under(resolved, prefix):
            return False, (
                f"refusing to ingest from sensitive $HOME path {prefix}: "
                "this directory typically holds keys, mail, or IDE "
                "config. Move the files you want to ingest somewhere "
                "outside the sensitive set, e.g. ~/Documents."
            )

    # 2. System denylist — hard deny.
    for prefix in _SYSTEM_DENY_PREFIXES:
        try:
            prefix_resolved = prefix.resolve(strict=False)
        except OSError:
            continue
        if _is_under(resolved, prefix_resolved):
            return False, (
                f"refusing to ingest from system path {prefix}: this "
                "is on the hard denylist (system dirs are dense with "
                "credentials / secrets)."
            )

    # 3. Explicit user allowlist via env var (colon-separated). After
    # the deny lists so a user can't accidentally re-enable ~/.ssh or
    # /var/log; before the default allowlists so this is the place to
    # add unusual paths (e.g. ``/opt/corpus``, ``/data/papers``).
    env_allow = os.environ.get("NEURO_OS_MCP_INGEST_ALLOWED_PATHS", "")
    for raw in env_allow.split(os.pathsep):
        raw = raw.strip()
        if not raw:
            continue
        try:
            prefix = Path(raw).expanduser().resolve(strict=False)
        except (OSError, RuntimeError):
            continue
        if _is_under(resolved, prefix):
            return True, f"allowed via NEURO_OS_MCP_INGEST_ALLOWED_PATHS ({prefix})"

    # 4. Tmp roots — allow. Lets pytest tmp_path work and lets the
    # user ingest a `/tmp/papers/` staging dir.
    tmp_roots: List[Path] = []
    tmpdir = os.environ.get("TMPDIR", "")
    if tmpdir:
        try:
            tmp_roots.append(Path(tmpdir).resolve(strict=False))
        except OSError:
            pass
    for raw in ("/tmp", "/private/tmp", "/var/folders", "/private/var/folders"):
        try:
            tmp_roots.append(Path(raw).resolve(strict=False))
        except OSError:
            continue
    for tmp_root in tmp_roots:
        if _is_under(resolved, tmp_root):
            return True, f"under tmp ({tmp_root})"

    # 5. Default: anywhere else under $HOME (sensitive subdirs already
    # filtered above).
    home = Path.home().resolve()
    if _is_under(resolved, home):
        return True, "under $HOME"

    return False, (
        f"path {path} is outside the default ingest allowlist ($HOME "
        "minus sensitive dotfile subdirs, plus tmp). To allow it, set "
        "the env var NEURO_OS_MCP_INGEST_ALLOWED_PATHS=<colon-separated "
        "paths> before starting the MCP server."
    )


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
        # Path-allowlist gate: refuse system dirs (/etc, /var, ...) and
        # sensitive $HOME subdirs (~/.ssh, ~/Library, ...). This is the
        # defense against prompt-injection-driven arbitrary-file reads
        # in autonomous-mode hosts that skip the per-tool confirmation.
        ok, reason = _is_safe_ingest_path(src)
        if not ok:
            return _err(reason)
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
# Investment-vertical tools
#
# 6 thin wrappers around existing CLI surfaces + 2 reasoning tools
# (propose_order / next_action) that close the talk-to-your-portfolio
# loop. Per the eval in docs/plans/voice-pilot-and-broker-mcp.md, these
# tools do NOT execute on a real broker; they propose, record, and
# rollup. Execution belongs to a separate broker MCP (Alpaca / IBKR /
# Schwab) — out of scope here.
# ---------------------------------------------------------------------------


def _register_investment_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def invest_dashboard(
        window_days: int = 30,
        home: Optional[str] = None,
    ) -> str:
        """Read-only rollup of the investment vertical (Phase 1 options
        income + Phase 1↔life income gap + Phase 2 mega-trend sleeve +
        5 sample-size-guarded health flags).

        Args:
            window_days: lookback (1-365). Default 30.
            home: override the default ~/.neuro_os_investment/.

        Returns: InvestmentDashboardSummary as JSON.
        """
        from agent.investment.config import read_position_theses
        from agent.investment.dashboard import build_dashboard_summary

        if not 1 <= window_days <= 365:
            return _err("window_days must be 1..365")
        home_path = _expanded_path(home)
        try:
            theses = [
                t for t in read_position_theses(home=home_path)
                if t.status == "active"
            ]
        except Exception:
            theses = []
        summary = build_dashboard_summary(
            theses=theses, home=home_path, window_days=window_days,
        )
        return _ok(json.loads(summary.model_dump_json()))

    @mcp.tool()
    def invest_cost_of_living_set(
        monthly_target: float,
        region: Optional[str] = None,
        breakdown: Optional[str] = None,
        home: Optional[str] = None,
    ) -> str:
        """Set the monthly cost-of-living target — the Phase-1 headline
        metric the dashboard measures income against.

        Args:
            monthly_target: dollar amount per month (e.g. 14000 for Bay
                            Area realistic).
            region: optional region label.
            breakdown: optional human-readable breakdown.
            home: override ~/.neuro_os_investment/.

        Returns: the saved CostOfLivingProfile as JSON.
        """
        from datetime import datetime, timezone

        from agent.investment.cost_of_living import (
            CostOfLivingProfile, save_profile,
        )

        if monthly_target <= 0.0:
            return _err("monthly_target must be > 0")
        profile = CostOfLivingProfile(
            monthly_target=monthly_target,
            region=region,
            breakdown=breakdown,
            source="direct",
            written_at=datetime.now(timezone.utc),
        )
        save_profile(profile, home=_expanded_path(home))
        return _ok(json.loads(profile.model_dump_json()))

    @mcp.tool()
    def invest_cost_of_living_read(
        money_os_profile_path: Optional[str] = None,
        home: Optional[str] = None,
    ) -> str:
        """Read the current cost-of-living target, optionally importing
        from money-os's ``profile/financial-identity.md`` via best-effort
        regex parse.

        Args:
            money_os_profile_path: optional path to money-os's
                                   profile/financial-identity.md to
                                   import from. If absent, reads the
                                   current saved profile.
            home: override ~/.neuro_os_investment/.

        Returns: CostOfLivingProfile JSON, or `{}` if nothing's set.
        """
        from agent.investment.cost_of_living import (
            load_profile, read_from_money_os_profile, save_profile,
        )

        home_path = _expanded_path(home)
        if money_os_profile_path:
            src = _expanded_path(money_os_profile_path)
            if src is None or not src.exists():
                return _err(f"money-os profile not found: {money_os_profile_path}")
            imported = read_from_money_os_profile(src)
            if imported is None:
                return _err(
                    "could not parse a monthly cost number from the "
                    "money-os profile — use invest_cost_of_living_set."
                )
            save_profile(imported, home=home_path)
            return _ok(json.loads(imported.model_dump_json()))
        current = load_profile(home=home_path)
        if current is None:
            return _ok({})
        return _ok(json.loads(current.model_dump_json()))

    @mcp.tool()
    def invest_trade_log(
        strategy: str,
        ticker: str,
        underlying_price: float,
        expiry: str,
        strikes: List[float],
        premium: float,
        max_loss: float,
        win_probability: float,
        contracts: int = 1,
        assignment_probability: Optional[float] = None,
        notes: Optional[str] = None,
        home: Optional[str] = None,
    ) -> str:
        """Log a new option trade. Computes expected_value from
        (win_probability, premium, max_loss) at log time so the EV is
        visible BEFORE you act — the discipline gate against the
        "high win-rate but losing money" failure mode.

        Args:
            strategy: one of cash_secured_put / covered_call / wheel /
                      credit_spread / iron_condor / naked / other.
            ticker: e.g. "NVDA".
            underlying_price: stock price at open.
            expiry: ISO date YYYY-MM-DD.
            strikes: list of strike prices (one for CSP/CC; two for
                     spreads; four for iron condor).
            premium: net premium received (per contract × contracts).
            max_loss: REQUIRED worst-case capital at risk.
            win_probability: 0.0..1.0; used to compute EV.
            contracts: default 1.
            assignment_probability: optional 0.0..1.0.
            notes: optional free-text.
            home: override ~/.neuro_os_investment/.

        Returns: the recorded OptionTrade as JSON (with computed EV).
        """
        from datetime import datetime, timezone

        from agent.investment.options_income import (
            OptionTrade, compute_expected_value, new_trade_id, write_trade,
        )

        if not 0.0 <= win_probability <= 1.0:
            return _err("win_probability must be in [0, 1]")
        if not strikes:
            return _err("strikes must contain ≥1 value")
        valid_strategies = {
            "cash_secured_put", "covered_call", "wheel",
            "credit_spread", "iron_condor", "naked", "other",
        }
        if strategy not in valid_strategies:
            return _err(f"strategy must be one of {sorted(valid_strategies)}")
        try:
            ev = compute_expected_value(
                win_probability=win_probability,
                premium_received=premium,
                max_loss=max_loss,
            )
            trade = OptionTrade(
                trade_id=new_trade_id(),
                opened_at=datetime.now(timezone.utc),
                strategy=strategy,
                ticker=ticker.upper(),
                underlying_price_at_open=underlying_price,
                expiry=expiry,
                strikes=strikes,
                contracts=contracts,
                premium_received=premium,
                max_loss=max_loss,
                expected_value=ev,
                assignment_probability=assignment_probability,
                notes=notes,
            )
        except Exception as e:
            return _err(f"OptionTrade validation failed: {e}")
        write_trade(trade, home=_expanded_path(home))
        return _ok(json.loads(trade.model_dump_json()))

    @mcp.tool()
    def invest_trade_close(
        trade_id: str,
        realized_pnl: float,
        outcome: str,
        notes: Optional[str] = None,
        home: Optional[str] = None,
    ) -> str:
        """Record the close of an open trade. Writes a NEW row pointing
        at the original via parent_trade_id (original stays frozen —
        immutable audit trail).

        Args:
            trade_id: trade_id of the open row to close.
            realized_pnl: signed dollar amount (negative = loss).
            outcome: 'won' / 'lost' / 'assigned' / 'rolled'.
            notes: optional free-text.
            home: override ~/.neuro_os_investment/.

        Returns: the close row as JSON.
        """
        from datetime import datetime, timezone

        from agent.investment.options_income import (
            OptionTrade, list_open_trades, new_trade_id, write_trade,
        )

        valid_outcomes = {"won", "lost", "assigned", "rolled"}
        if outcome not in valid_outcomes:
            return _err(f"outcome must be one of {sorted(valid_outcomes)}")
        home_path = _expanded_path(home)
        open_trades = list_open_trades(home=home_path)
        parent = next((t for t in open_trades if t.trade_id == trade_id), None)
        if parent is None:
            return _err(
                f"trade {trade_id!r} not found in open trades. Use "
                f"invest_trade_list with open_only=true to see what's open."
            )
        close_row = OptionTrade(
            trade_id=new_trade_id(),
            opened_at=parent.opened_at,
            strategy=parent.strategy,
            ticker=parent.ticker,
            underlying_price_at_open=parent.underlying_price_at_open,
            expiry=parent.expiry,
            strikes=parent.strikes,
            contracts=parent.contracts,
            premium_received=parent.premium_received,
            max_loss=parent.max_loss,
            expected_value=parent.expected_value,
            assignment_probability=parent.assignment_probability,
            outcome=outcome,
            closed_at=datetime.now(timezone.utc),
            realized_pnl=realized_pnl,
            parent_trade_id=parent.trade_id,
            notes=notes,
        )
        write_trade(close_row, home=home_path)
        return _ok(json.loads(close_row.model_dump_json()))

    @mcp.tool()
    def invest_sleeve_balance(
        home: Optional[str] = None,
    ) -> str:
        """Show mega-trend sleeve allocation across active PositionTheses.
        Surfaces concentration warnings when any sleeve > 40% of capital.

        Args:
            home: override ~/.neuro_os_investment/.

        Returns: SleeveBalance as JSON.
        """
        from agent.investment.config import read_position_theses
        from agent.investment.megatrend import compute_sleeve_balance

        home_path = _expanded_path(home)
        try:
            theses = [
                t for t in read_position_theses(home=home_path)
                if t.status == "active"
            ]
        except Exception:
            theses = []
        balance = compute_sleeve_balance(theses)
        return _ok(json.loads(balance.model_dump_json()))

    @mcp.tool()
    def invest_propose_order(
        strategy: str,
        ticker: str,
        underlying_price: float,
        expiry: str,
        strikes: List[float],
        premium: float,
        max_loss: float,
        win_probability: float,
        contracts: int = 1,
        rationale: Optional[str] = None,
    ) -> str:
        """Propose an order WITHOUT executing or recording it. Returns a
        rich proposal (EV math + risk math + recommendation banner) so a
        voice / chat loop can read it back and the user explicitly
        authorizes. This is the HITL surface for transaction-shaped
        actions.

        After the user authorizes, the agent calls ``invest_trade_log``
        to RECORD the trade (assumes the user executes on their broker
        manually OR via a future broker MCP). The propose step never
        writes to disk.

        Args:
            strategy / ticker / underlying_price / expiry / strikes /
            premium / max_loss / win_probability / contracts: same shape
            as invest_trade_log.
            rationale: optional one-sentence thesis explaining WHY this
                       order is proposed (e.g. "AAPL CSP at 0.20 delta
                       to harvest premium against my cash sleeve").

        Returns: proposal JSON with computed expected_value, risk
        banner, and a recommendation field.
        """
        from agent.investment.options_income import compute_expected_value

        if not 0.0 <= win_probability <= 1.0:
            return _err("win_probability must be in [0, 1]")
        if not strikes:
            return _err("strikes must contain ≥1 value")
        try:
            ev = compute_expected_value(
                win_probability=win_probability,
                premium_received=premium,
                max_loss=max_loss,
            )
        except Exception as e:
            return _err(f"compute_expected_value failed: {e}")

        # Classify the proposal's risk profile for the user-facing banner.
        if ev < 0:
            risk_banner = "NEGATIVE_EV — math says don't take this trade as parameterized."
            recommendation = "reject"
        elif premium / max(max_loss, 1.0) < 0.01:
            risk_banner = "POOR_RATIO — premium is < 1% of max-loss; small EV per unit of risk."
            recommendation = "review"
        elif win_probability >= 0.85 and max_loss / max(premium, 1.0) > 30:
            risk_banner = "DEEP_OTM — high win-rate but max-loss is >30x premium; high tail risk."
            recommendation = "review"
        else:
            risk_banner = "OK — EV positive; premium-to-risk ratio reasonable."
            recommendation = "authorize_then_log"
        return _ok({
            "kind": "order_proposal",
            "strategy": strategy,
            "ticker": ticker.upper(),
            "underlying_price": underlying_price,
            "expiry": expiry,
            "strikes": strikes,
            "contracts": contracts,
            "premium_received": premium,
            "max_loss": max_loss,
            "win_probability": win_probability,
            "expected_value": ev,
            "risk_banner": risk_banner,
            "recommendation": recommendation,
            "rationale": rationale,
            "next_step": (
                "If you authorize, call invest_trade_log with these "
                "exact parameters to record the trade after executing on "
                "your broker. Execution itself is NOT performed by this "
                "tool — there is no broker connection."
            ),
        })

    @mcp.tool()
    def invest_next_action(
        window_days: int = 30,
        home: Optional[str] = None,
    ) -> str:
        """Given the current dashboard state, return the single
        highest-leverage next action. Used by a voice / chat loop to
        answer "what should I do next?" without the user reading the
        full dashboard.

        Args:
            window_days: lookback for the dashboard read (1-365).
            home: override ~/.neuro_os_investment/.

        Returns: JSON with `action`, `reason`, `cli_hint`,
        `priority` ∈ {high, medium, low}.
        """
        from agent.investment.config import read_position_theses
        from agent.investment.dashboard import build_dashboard_summary

        if not 1 <= window_days <= 365:
            return _err("window_days must be 1..365")
        home_path = _expanded_path(home)
        try:
            theses = [
                t for t in read_position_theses(home=home_path)
                if t.status == "active"
            ]
        except Exception:
            theses = []
        summary = build_dashboard_summary(
            theses=theses, home=home_path, window_days=window_days,
        )

        # Priority-ordered decision tree. The first matching condition
        # wins; later conditions only fire if earlier ones don't apply.
        # This is intentionally simple — voice loops want ONE answer,
        # not a list.
        flags = set(summary.system_health_flags)

        if "no_cost_of_living_target" in flags:
            return _ok({
                "action": "Set your monthly cost-of-living target.",
                "reason": (
                    "Without a target, the Phase-1 income gap is "
                    "undefined; you can't tell if you're winning or "
                    "losing this month."
                ),
                "cli_hint": (
                    "neuro-os invest cost-of-living set "
                    "--monthly-target 14000 --region 'Bay Area'"
                ),
                "priority": "high",
            })

        if "options_loss_concentration" in flags:
            return _ok({
                "action": (
                    "Stop opening new options positions; audit the "
                    "strategy that's losing money."
                ),
                "reason": (
                    "≥20 closed trades show negative realized PNL "
                    "despite the win-rate. This is the 'high win-rate "
                    "but losing money' failure mode. Adding more "
                    "trades makes it worse."
                ),
                "cli_hint": "neuro-os invest trade list --outcome lost",
                "priority": "high",
            })

        if "single_sleeve_concentration" in flags:
            return _ok({
                "action": (
                    "Rebalance: trim the over-concentrated sleeve OR "
                    "add to the under-represented ones."
                ),
                "reason": (
                    f"At least one sleeve holds > 40% of capital: "
                    f"{', '.join(summary.sleeve_balance.sleeves_concentrated)}. "
                    f"You're betting on one trend, not a basket."
                ),
                "cli_hint": "neuro-os invest sleeve-balance",
                "priority": "high",
            })

        if "no_thesis_invalidation" in flags:
            return _ok({
                "action": (
                    "Audit your active theses; mark the ones whose "
                    "invalidation_condition has actually fired."
                ),
                "reason": (
                    "≥10 active theses with zero invalidations means "
                    "either perfect foresight (unlikely) or no "
                    "discipline. The whole point of "
                    "invalidation_condition is that you act on it."
                ),
                "cli_hint": "neuro-os invest sleeve-balance",
                "priority": "medium",
            })

        if "phase1_income_gap_unmet" in flags:
            gap = summary.income_gap
            return _ok({
                "action": (
                    "Open one new income-generating trade this week "
                    "(cash-secured put or covered call at 0.20-0.30 "
                    "delta, 30-45 DTE)."
                ),
                "reason": (
                    f"Last month's net options income covers "
                    f"{int((1 - gap.gap_pct) * 100) if gap else 0}% "
                    f"of your "
                    f"${int(summary.cost_of_living_target or 0):,}/mo "
                    f"target. You're "
                    f"${int(gap.gap_dollars) if gap else 0:,} short."
                ),
                "cli_hint": (
                    "neuro-os invest trade log --strategy "
                    "cash_secured_put --ticker AAPL ..."
                ),
                "priority": "high",
            })

        # No flags fired — recommend the maintenance action.
        return _ok({
            "action": (
                "Tag any new PositionThesis with its mega-trend "
                "`sleeve` field and file an invalidation_condition you "
                "can falsify."
            ),
            "reason": (
                "No health flags are firing — the substrate is healthy. "
                "The maintenance discipline is to keep filing theses "
                "WITH invalidation conditions so the dashboard stays "
                "honest as you scale."
            ),
            "cli_hint": "neuro-os invest dashboard --window 30",
            "priority": "low",
        })


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
