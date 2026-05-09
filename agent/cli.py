"""
Neuro-OS command-line interface.

Subcommands:

* ``extract`` — run a single document through the pipeline and print
  the result as JSON.
* ``ingest`` — feed one or more documents (positional args or paths via
  ``--from-file``) through the full self-evolving loop.
* ``build-ontology`` — convert a source-index file to a JSON ontology.
* ``evolve`` — alias for ``ingest`` with sandbox validation enabled.
* ``self-modify`` — run the closed self-modification loop against a
  registered domain. With ``--list`` it prints registered domains.

Run ``python -m agent --help`` for usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from agent.api import ingest_documents, process_text
from agent.ontology_builder import build_ontology


def _read_texts(args: argparse.Namespace) -> List[str]:
    texts: List[str] = list(args.text or [])
    for path in args.from_file or []:
        texts.append(Path(path).read_text(encoding="utf-8"))
    if not texts and not sys.stdin.isatty():
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            texts.append(stdin_text)
    return texts


def _cmd_extract(args: argparse.Namespace) -> int:
    texts = _read_texts(args)
    if not texts:
        print("error: provide at least one text via positional arg, --from-file, or stdin", file=sys.stderr)
        return 2
    if len(texts) > 1:
        print("error: extract takes a single document; use ingest for multiple", file=sys.stderr)
        return 2
    result = process_text(texts[0], ontology=args.ontology)
    print(json.dumps(result, indent=2))
    return 0


def _cmd_ingest(args: argparse.Namespace, *, sandbox_default: bool = False) -> int:
    texts = _read_texts(args)
    if not texts:
        print("error: provide at least one text via positional arg, --from-file, or stdin", file=sys.stderr)
        return 2
    sandbox = args.sandbox if args.sandbox is not None else sandbox_default
    report = ingest_documents(
        texts,
        ontology=args.ontology,
        ontology_path=args.ontology_out,
        run_in_sandbox=sandbox,
        enable_merge=not args.no_merge,
    )
    print(json.dumps(report, indent=2, default=str))
    return 0


def _cmd_build_ontology(args: argparse.Namespace) -> int:
    ontology = build_ontology(args.source, args.output)
    summary = {
        "primitives": list(ontology["primitives"].keys()),
        "source_count": ontology["source_count"],
        "relation_count": ontology["relation_count"],
        "wrote": args.output,
    }
    print(json.dumps(summary, indent=2))
    return 0


def _cmd_self_modify(args: argparse.Namespace) -> int:
    # Local imports so a failure inside the self-modification stack doesn't
    # break the rest of the CLI when the user just runs --help.
    from agent.domains import get_domain, list_domains
    from agent.self_modification import run_self_modification

    if args.list:
        print(json.dumps({"domains": list_domains()}, indent=2))
        return 0
    try:
        domain = get_domain(args.domain)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = run_self_modification(domain, max_patches=args.max_patches)
    print(json.dumps(report, indent=2, default=str))
    return 0


def _resolve_workflowx_path(
    explicit: Optional[str],
    *,
    fallback: Path,
    quiet: bool = False,
) -> Path:
    """Run the auto-detect chain when ``explicit`` is None.

    Returns the path the daemon / loop should read. Always logs the
    detection result (one line) so the user knows whether real data is
    flowing — unless ``quiet=True`` (used by ``loop workflowx-detect``
    which prints structured JSON instead).
    """
    from agent.founder_loop.workflowx_detect import detect_workflowx_export

    if explicit is not None:
        result = detect_workflowx_export(
            explicit=Path(explicit).expanduser(),
            fallback=fallback,
        )
    else:
        result = detect_workflowx_export(fallback=fallback)
    if not quiet:
        print(result.note, file=sys.stderr)
    return result.path


def _cmd_loop_workflowx_detect(args: argparse.Namespace) -> int:
    """Read-only: run detection and print the structured result as JSON."""
    from agent.founder_loop.workflowx_detect import detect_workflowx_export

    fallback = Path(args.fallback).expanduser()
    explicit = Path(args.workflowx_fixture).expanduser() if args.workflowx_fixture else None
    result = detect_workflowx_export(explicit=explicit, fallback=fallback)
    print(json.dumps(
        {
            "path": str(result.path),
            "source": result.source,
            "is_real": result.is_real,
            "note": result.note,
        },
        indent=2,
    ))
    return 0


def _cmd_loop_morning(args: argparse.Namespace) -> int:
    from agent.founder_loop import FounderLoop, Priority

    raw = json.loads(Path(args.priorities_file).read_text(encoding="utf-8"))
    priorities = [Priority.model_validate(p) for p in raw]

    # Morning ritual doesn't need an adapter — but FounderLoop's constructor
    # currently requires one. Use a fixture adapter pointed at /dev/null
    # equivalent (a path that doesn't exist) so the loop is well-formed
    # but no events are read.
    from agent.founder_loop.observe import FixtureWorkflowxAdapter
    loop = FounderLoop(
        registry_path=args.registry,
        contract_path=args.contracts,
        adapter=FixtureWorkflowxAdapter("/dev/null"),
    )
    contract = loop.morning_ritual(
        priorities=priorities,
        entertainment_ration_min=args.ration,
        threshold_pct=args.threshold,
    )
    print(json.dumps(json.loads(contract.model_dump_json()), indent=2))
    return 0


def _cmd_loop_tick(args: argparse.Namespace) -> int:
    from datetime import datetime
    from agent.founder_loop import FounderLoop

    home_default = Path.home() / ".founder_loop"
    workflowx_path = _resolve_workflowx_path(
        args.workflowx_fixture,
        fallback=home_default / "workflowx.jsonl",
    )
    loop = FounderLoop(
        registry_path=args.registry,
        contract_path=args.contracts,
        workflowx_export_path=workflowx_path,
        events_path=getattr(args, "events", None),
        use_llm=bool(args.use_llm),
    )
    now = datetime.fromisoformat(args.at) if args.at else None
    result = loop.tick(intent=args.intent, now=now, dry_run=args.dry_run)
    print(json.dumps(json.loads(result.model_dump_json()), indent=2))
    return 0


def _cmd_loop_urge(args: argparse.Namespace) -> int:
    from datetime import datetime
    from agent.founder_loop import FounderLoop
    from agent.founder_loop.observe import FixtureWorkflowxAdapter

    loop = FounderLoop(
        registry_path=args.registry,
        contract_path=args.contracts,
        events_path=getattr(args, "events", None),
        adapter=FixtureWorkflowxAdapter("/dev/null"),
    )
    when = datetime.fromisoformat(args.at) if args.at else None
    event = loop.log_urge(
        args.urge_type,
        context=args.context or "",
        when=when,
    )
    print(json.dumps(json.loads(event.model_dump_json()), indent=2))
    return 0


def _cmd_autostart_install(args: argparse.Namespace) -> int:
    from agent.founder_loop import install as _install
    ok, msg = _install.install(dry_run=bool(args.dry_run))
    print(msg)
    return 0 if ok else 1


def _cmd_autostart_uninstall(args: argparse.Namespace) -> int:
    from agent.founder_loop import install as _install
    ok, msg = _install.uninstall(dry_run=bool(args.dry_run))
    print(msg)
    return 0 if ok else 1


def _cmd_autostart_status(args: argparse.Namespace) -> int:
    from agent.founder_loop import install as _install
    ok, msg = _install.status()
    print(msg)
    return 0 if ok else 1


def _cmd_loop_serve(args: argparse.Namespace) -> int:
    import logging
    import threading
    import webbrowser
    from agent.founder_loop.server import serve
    from agent.founder_loop.workflowx_detect import detect_workflowx_export

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    registry = Path(args.registry).expanduser()
    contracts = Path(args.contracts).expanduser()

    # Auto-detect workflowx unless an explicit path was provided.
    fallback_workflowx = registry.parent / "workflowx.jsonl"
    if args.workflowx_fixture is None:
        detection = detect_workflowx_export(fallback=fallback_workflowx)
    else:
        detection = detect_workflowx_export(
            explicit=Path(args.workflowx_fixture).expanduser(),
            fallback=fallback_workflowx,
        )
    workflowx = detection.path
    logging.info(detection.note)

    # First-run convenience: create the data dir and (only when we're
    # using the fallback) an empty workflowx file so the daemon can
    # boot. Real-detected paths are read-only — we never write into a
    # user's external workflowx export directory.
    for p in (registry.parent, contracts.parent, workflowx.parent):
        p.mkdir(parents=True, exist_ok=True)
    if detection.source == "fallback" and not workflowx.exists():
        workflowx.write_text("", encoding="utf-8")
        logging.info("created empty workflowx fallback: %s", workflowx)
    onboard_url = f"http://{args.host}:{args.port}/onboard"
    print(f"\n  Open {onboard_url} in your browser\n")
    if getattr(args, "open_browser", False):
        # Open after the daemon is listening — give it a beat.
        def _open():
            import time
            time.sleep(0.6)
            try:
                webbrowser.open(onboard_url)
            except Exception:  # pragma: no cover
                pass
        threading.Thread(target=_open, daemon=True).start()
    serve(
        host=args.host,
        port=args.port,
        registry_path=registry,
        contract_path=contracts,
        workflowx_fixture=workflowx,
        events_path=Path(args.events).expanduser() if args.events else None,
        use_llm=bool(args.use_llm),
        tick_interval_min=int(getattr(args, "tick_interval_min", 0) or 0),
        block=True,
    )
    return 0


def _cmd_loop_nightly(args: argparse.Namespace) -> int:
    from datetime import datetime
    from agent.founder_loop import FounderLoop

    home_default = Path.home() / ".founder_loop"
    workflowx_path = _resolve_workflowx_path(
        args.workflowx_fixture,
        fallback=home_default / "workflowx.jsonl",
    )
    loop = FounderLoop(
        registry_path=args.registry,
        contract_path=args.contracts,
        workflowx_export_path=workflowx_path,
    )
    when = datetime.fromisoformat(args.at) if args.at else None
    summary = loop.nightly(day=when)
    print(json.dumps(json.loads(summary.model_dump_json()), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="neuro-os", description="Neuro-OS CLI")
    sub = p.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="run one doc through the pipeline")
    extract.add_argument("text", nargs="*", help="document text (or use --from-file / stdin)")
    extract.add_argument("--from-file", action="append", help="read text from file (repeatable)")
    extract.add_argument("--ontology", help="JSON ontology path")
    extract.set_defaults(func=_cmd_extract)

    ingest = sub.add_parser("ingest", help="run docs through the self-evolving loop")
    ingest.add_argument("text", nargs="*", help="document texts (or use --from-file / stdin)")
    ingest.add_argument("--from-file", action="append", help="read text from file (repeatable)")
    ingest.add_argument("--ontology", help="JSON ontology path")
    ingest.add_argument("--ontology-out", help="write updated ontology to this path")
    ingest.add_argument("--sandbox", action="store_true", default=None, help="run sandbox import smoke test")
    ingest.add_argument("--no-merge", action="store_true", help="evaluate but do not mutate the ontology")
    ingest.set_defaults(func=lambda a: _cmd_ingest(a, sandbox_default=False))

    evolve = sub.add_parser("evolve", help="ingest with sandbox validation enabled by default")
    evolve.add_argument("text", nargs="*")
    evolve.add_argument("--from-file", action="append")
    evolve.add_argument("--ontology")
    evolve.add_argument("--ontology-out")
    evolve.add_argument("--sandbox", action="store_true", default=None)
    evolve.add_argument("--no-merge", action="store_true")
    evolve.set_defaults(func=lambda a: _cmd_ingest(a, sandbox_default=True))

    build = sub.add_parser("build-ontology", help="convert a source index to JSON ontology")
    build.add_argument("source", help="source-index text file")
    build.add_argument("output", help="output JSON path")
    build.set_defaults(func=_cmd_build_ontology)

    selfmod = sub.add_parser(
        "self-modify",
        help="run the closed self-modification loop against a registered domain",
    )
    selfmod.add_argument("--domain", default="neuro_os_self_v1", help="domain name (default: neuro_os_self_v1)")
    selfmod.add_argument("--list", action="store_true", help="list registered domains and exit")
    selfmod.add_argument("--max-patches", type=int, default=1, help="cap on patches per loop tick (default: 1)")
    selfmod.set_defaults(func=_cmd_self_modify)

    loop_p = sub.add_parser(
        "loop",
        help="founder_loop: daily reward-economy + sublimation control loop",
    )
    loop_sub = loop_p.add_subparsers(dest="loop_command", required=True)

    loop_morning = loop_sub.add_parser(
        "morning", help="bind today's contract (Ulysses pact)"
    )
    loop_morning.add_argument("--registry", required=True, help="JSONL registry path")
    loop_morning.add_argument("--contracts", required=True, help="JSONL contract store path")
    loop_morning.add_argument(
        "--priorities-file",
        required=True,
        help="JSON file with the day's priorities (list of Priority objects)",
    )
    loop_morning.add_argument(
        "--ration", type=int, default=60,
        help="entertainment ration in minutes (default: 60)"
    )
    loop_morning.add_argument(
        "--threshold", type=int, default=90,
        help="tank threshold percent (default: 90)"
    )
    loop_morning.add_argument("--dry-run", action="store_true")
    loop_morning.set_defaults(func=_cmd_loop_morning)

    loop_tick = loop_sub.add_parser(
        "tick", help="run one hourly tick"
    )
    loop_tick.add_argument("--registry", required=True)
    loop_tick.add_argument("--contracts", required=True)
    loop_tick.add_argument("--workflowx-fixture", default=None,
                           help="JSONL fixture file. When omitted, "
                                "auto-detect platform paths + WORKFLOWX_EXPORTS_PATH; "
                                "fall back to ~/.founder_loop/workflowx.jsonl.")
    loop_tick.add_argument("--events", default=None,
                           help="user-logged urge events path "
                                "(default: registry sibling founder_events.jsonl)")
    loop_tick.add_argument("--intent", help="optional: override last_intent")
    loop_tick.add_argument("--at", help="ISO timestamp to tick at (default: now)")
    loop_tick.add_argument("--use-llm", action="store_true",
                           help="route predict.py + sublimate.py through Anthropic API")
    loop_tick.add_argument("--dry-run", action="store_true",
                           help="produce a TickResult without writing the registry")
    loop_tick.set_defaults(func=_cmd_loop_tick)

    loop_urge = loop_sub.add_parser(
        "urge",
        help=(
            "log a user-reported urge event. The next tick honors it "
            "as ground truth over the predictor."
        ),
    )
    loop_urge.add_argument("--registry", required=True)
    loop_urge.add_argument("--contracts", required=True)
    loop_urge.add_argument("--events", default=None,
                           help="urge events path "
                                "(default: registry sibling founder_events.jsonl)")
    loop_urge.add_argument(
        "urge_type",
        choices=["entertainment", "escape", "novelty", "none"],
        help="kind of urge that fired",
    )
    loop_urge.add_argument("--context", default="",
                           help="short free-text context (≤400 chars)")
    loop_urge.add_argument("--at", help="ISO timestamp (default: now)")
    loop_urge.set_defaults(func=_cmd_loop_urge)

    loop_serve = loop_sub.add_parser(
        "serve",
        help=(
            "start the local HTTP daemon for browser extension + tray app + "
            "/onboard webapp (defaults to ~/.founder_loop/* paths so the "
            "first-time user can just run `neuro-os loop serve`)"
        ),
    )
    _home_default = str(Path.home() / ".founder_loop")
    loop_serve.add_argument(
        "--registry",
        default=str(Path(_home_default) / "registry.jsonl"),
        help=f"default: {_home_default}/registry.jsonl",
    )
    loop_serve.add_argument(
        "--contracts",
        default=str(Path(_home_default) / "contracts.jsonl"),
        help=f"default: {_home_default}/contracts.jsonl",
    )
    loop_serve.add_argument(
        "--workflowx-fixture",
        default=None,
        help=(
            "explicit JSONL fixture / export path. When omitted, the "
            "daemon auto-detects via known platform paths "
            "(macOS Application Support, Linux ~/.config, etc.) and the "
            "WORKFLOWX_EXPORTS_PATH env var. Falls back to "
            f"{_home_default}/workflowx.jsonl (auto-created empty)."
        ),
    )
    loop_serve.add_argument(
        "--events",
        help="events log path (default: registry sibling events.jsonl)",
    )
    loop_serve.add_argument("--host", default="127.0.0.1")
    loop_serve.add_argument("--port", type=int, default=8765)
    loop_serve.add_argument(
        "--use-llm", action="store_true",
        help="route /chat through Anthropic API (requires ANTHROPIC_API_KEY)",
    )
    loop_serve.add_argument(
        "--open-browser", action="store_true",
        help="open /onboard in the default browser after the daemon starts",
    )
    loop_serve.add_argument(
        "--tick-interval-min", type=int, default=0,
        help=(
            "if set > 0, daemon runs `loop.tick()` every N minutes in a "
            "background thread; default 0 = disabled (use cron / launchd)"
        ),
    )
    loop_serve.set_defaults(func=_cmd_loop_serve)

    # Top-level `neuro-os start` — the human-friendly alias.
    start_p = sub.add_parser(
        "start",
        help=(
            "one-shot: start the daemon with sensible defaults AND open "
            "the /onboard page in your browser. Equivalent to "
            "`loop serve --open-browser --tick-interval-min 60` with "
            "~/.founder_loop/* defaults."
        ),
    )
    start_p.add_argument(
        "--registry",
        default=str(Path(_home_default) / "registry.jsonl"),
    )
    start_p.add_argument(
        "--contracts",
        default=str(Path(_home_default) / "contracts.jsonl"),
    )
    start_p.add_argument(
        "--workflowx-fixture",
        default=None,
        help=(
            "explicit JSONL fixture / export path. When omitted, "
            "auto-detect runs (see `loop workflowx-detect`)."
        ),
    )
    start_p.add_argument("--events", default=None)
    start_p.add_argument("--host", default="127.0.0.1")
    start_p.add_argument("--port", type=int, default=8765)
    start_p.add_argument("--use-llm", action="store_true")
    start_p.add_argument(
        "--no-open", dest="open_browser", action="store_false", default=True,
        help="don't open the browser (useful for headless / SSH sessions)",
    )
    start_p.add_argument(
        "--tick-interval-min", type=int, default=60,
        help="default 60 — internal scheduler runs `tick()` every hour",
    )
    start_p.set_defaults(func=_cmd_loop_serve)

    # Top-level autostart subcommand — install the launchd / systemd /
    # Task Scheduler unit so the daemon runs at login.
    auto = sub.add_parser(
        "autostart",
        help=(
            "install / uninstall / status the auto-start-on-login unit "
            "(launchd plist, systemd-user service, or Task Scheduler XML "
            "depending on platform)"
        ),
    )
    auto_sub = auto.add_subparsers(dest="autostart_command", required=True)
    auto_install = auto_sub.add_parser(
        "install", help="install the autostart unit and enable it"
    )
    auto_install.add_argument("--dry-run", action="store_true")
    auto_install.set_defaults(func=_cmd_autostart_install)
    auto_uninstall = auto_sub.add_parser(
        "uninstall", help="disable the autostart unit and remove it"
    )
    auto_uninstall.add_argument("--dry-run", action="store_true")
    auto_uninstall.set_defaults(func=_cmd_autostart_uninstall)
    auto_status = auto_sub.add_parser(
        "status", help="show whether the autostart unit is installed/active"
    )
    auto_status.set_defaults(func=_cmd_autostart_status)

    loop_nightly = loop_sub.add_parser(
        "nightly", help="end-of-day rollup: MAE, contract-honor, goldens"
    )
    loop_nightly.add_argument("--registry", required=True)
    loop_nightly.add_argument("--contracts", required=True)
    loop_nightly.add_argument("--workflowx-fixture", default=None,
                              help="explicit fixture path; omit to auto-detect")
    loop_nightly.add_argument("--at", help="ISO timestamp to roll up at (default: now)")
    loop_nightly.set_defaults(func=_cmd_loop_nightly)

    loop_detect = loop_sub.add_parser(
        "workflowx-detect",
        help=(
            "show where the daemon would read workflowx export from. "
            "Read-only — no side effects. Useful to verify a clean install "
            "without starting the daemon."
        ),
    )
    loop_detect.add_argument(
        "--workflowx-fixture", default=None,
        help="if given, mark this as the explicit path and skip detection",
    )
    loop_detect.add_argument(
        "--fallback",
        default=str(Path(_home_default) / "workflowx.jsonl"),
        help=f"path returned when nothing else is found (default: {_home_default}/workflowx.jsonl)",
    )
    loop_detect.set_defaults(func=_cmd_loop_workflowx_detect)

    # ---------------------------------------------------------------------
    # Top-level vertical subcommands (research / invest / startup).
    # founder_loop keeps its `loop ...` subtree above for backwards compat.
    # The 3 new verticals are top-level because neuro-os is now a
    # 4-vertical platform, not a single-product project.
    # ---------------------------------------------------------------------
    _add_vertical_subcommands(
        sub,
        vertical_name="research",
        description="research vertical: turn paper-collecting into recursive world-model refinement",
        drift_choices=[
            "paper_collector", "topic_hopper", "memorizer",
            "authority_acceptor", "overloaded", "forgetting",
        ],
        needs_thesis_id=True,
        needs_hypothesis_id=False,
    )
    _add_vertical_subcommands(
        sub,
        vertical_name="invest",
        description="investment vertical (advisory-only): epistemic calibration, no trade execution",
        drift_choices=[
            "emotional", "narrative_following", "price_obsessed",
            "overconfident", "social_proof_following", "ego_attached",
        ],
        needs_thesis_id=False,
        needs_hypothesis_id=False,
    )
    _add_vertical_subcommands(
        sub,
        vertical_name="startup",
        description="startup vertical: market-aligned convergence via tight OEC loops",
        drift_choices=[
            "idea_chaos", "broadcasting", "feature_creep",
            "vision_intoxicated", "vanity_metrics", "random_execution",
        ],
        needs_thesis_id=False,
        needs_hypothesis_id=True,
    )

    return p


# ---------------------------------------------------------------------------
# Vertical CLI helpers (research / invest / startup)
# ---------------------------------------------------------------------------


def _vertical_onboard_handler(*, vertical_name: str):
    """Build a handler that signs a contract from a JSON priorities file.

    Each vertical's priorities have a slightly different shape, so the
    handler imports the right factory + Pydantic schema lazily and
    forwards the parsed list to the morning_ritual hook.
    """
    def handler(args: argparse.Namespace) -> int:
        priorities_raw = json.loads(Path(args.priorities_file).read_text())
        if vertical_name == "research":
            from agent.research import ResearchPriority, make_research_app
            priorities = [ResearchPriority.model_validate(p) for p in priorities_raw]
            app = make_research_app(home=Path(args.home).expanduser() if args.home else None)
            contract = app.morning_ritual(
                active_thesis_id=args.active_thesis_id,
                priorities=priorities,
                primary_resource_budget=args.budget,
                threshold_pct=args.threshold,
            )
        elif vertical_name == "invest":
            from agent.investment import InvestmentPriority, make_investment_app
            priorities = [InvestmentPriority.model_validate(p) for p in priorities_raw]
            app = make_investment_app(home=Path(args.home).expanduser() if args.home else None)
            contract = app.morning_ritual(
                priorities=priorities,
                primary_resource_budget=args.budget,
                threshold_pct=args.threshold,
            )
        elif vertical_name == "startup":
            from agent.startup import StartupPriority, make_startup_app
            priorities = [StartupPriority.model_validate(p) for p in priorities_raw]
            app = make_startup_app(home=Path(args.home).expanduser() if args.home else None)
            contract = app.morning_ritual(
                active_hypothesis_id=args.active_hypothesis_id,
                priorities=priorities,
                primary_resource_budget=args.budget,
                threshold_pct=args.threshold,
            )
        else:
            raise SystemExit(f"unknown vertical: {vertical_name}")
        print(contract.model_dump_json(indent=2))
        return 0
    return handler


def _vertical_tick_handler(*, vertical_name: str):
    def handler(args: argparse.Namespace) -> int:
        if vertical_name == "research":
            from agent.research import make_research_app as factory
        elif vertical_name == "invest":
            from agent.investment import make_investment_app as factory
        elif vertical_name == "startup":
            from agent.startup import make_startup_app as factory
        else:
            raise SystemExit(f"unknown vertical: {vertical_name}")

        app = factory(home=Path(args.home).expanduser() if args.home else None)
        result = app.tick(
            observed_failure_mode=args.drift,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, indent=2, default=str))
        return 0
    return handler


def _vertical_nightly_handler(*, vertical_name: str):
    def handler(args: argparse.Namespace) -> int:
        if vertical_name == "research":
            from agent.research import make_research_app as factory
        elif vertical_name == "invest":
            from agent.investment import make_investment_app as factory
        elif vertical_name == "startup":
            from agent.startup import make_startup_app as factory
        else:
            raise SystemExit(f"unknown vertical: {vertical_name}")

        app = factory(home=Path(args.home).expanduser() if args.home else None)
        summary = app.nightly()
        print(summary.model_dump_json(indent=2))
        return 0
    return handler


def _add_vertical_subcommands(
    sub: "argparse._SubParsersAction",
    *,
    vertical_name: str,
    description: str,
    drift_choices: List[str],
    needs_thesis_id: bool,
    needs_hypothesis_id: bool,
) -> None:
    """Add `<vertical_name> onboard / tick / nightly` to the top-level
    parser. Used 3 times: once per new vertical."""
    top = sub.add_parser(vertical_name, help=description)
    top_sub = top.add_subparsers(dest=f"{vertical_name}_command", required=True)

    # research-only: ingestion + review (Lane 1).
    if vertical_name == "research":
        _add_research_ingest_subcommands(top_sub)

    # onboard
    onb = top_sub.add_parser(
        "onboard",
        help=f"sign today's {vertical_name} contract from a JSON priorities file",
    )
    onb.add_argument("--priorities-file", required=True,
                     help="JSON file with the vertical's priority list")
    onb.add_argument("--home", default=None,
                     help=f"vertical home dir (default: ~/.neuro_os_{vertical_name}/)")
    onb.add_argument("--budget", type=int, default=1,
                     help="primary_resource_budget for today (papers / position-edits / pivots)")
    onb.add_argument("--threshold", type=int, default=90,
                     help="tank-threshold percent (default 90)")
    if needs_thesis_id:
        onb.add_argument("--active-thesis-id", required=True,
                         help="The active research-thesis id (single-thesis enforcement)")
    if needs_hypothesis_id:
        onb.add_argument("--active-hypothesis-id", required=True,
                         help="The active startup-hypothesis id (single-thesis enforcement)")
    onb.set_defaults(func=_vertical_onboard_handler(vertical_name=vertical_name))

    # tick
    tk = top_sub.add_parser(
        "tick",
        help=f"run one {vertical_name} tick (optionally with --drift <mode>)",
    )
    tk.add_argument("--home", default=None)
    tk.add_argument(
        "--drift",
        choices=drift_choices,
        default=None,
        help="if set, the failure mode the user observed; substrate "
             "produces a propose_constructive_expression action",
    )
    tk.add_argument("--dry-run", action="store_true",
                    help="produce the action without writing the registry")
    tk.set_defaults(func=_vertical_tick_handler(vertical_name=vertical_name))

    # nightly
    ngt = top_sub.add_parser(
        "nightly",
        help=f"print today's {vertical_name} 4-metric summary",
    )
    ngt.add_argument("--home", default=None)
    ngt.set_defaults(func=_vertical_nightly_handler(vertical_name=vertical_name))


# ---------------------------------------------------------------------------
# Research-vertical ingestion subcommands (Lane 1: gbrain adapter / Plan B).
#
# `research ingest --from-gbrain --export-file <path>`
#     Read a gbrain export JSON, translate gbrain entities to
#     MechanismCardProposal rows, write to ~/.neuro_os_research/proposals/pending/.
# `research review --cli`
#     Minimal REPL: shows next pending proposal, prompts a/r/s, calls
#     write_mechanism_card on accept (Law 7 — every accept is an explicit user act).
# ---------------------------------------------------------------------------


def _add_research_ingest_subcommands(top_sub: "argparse._SubParsersAction") -> None:
    """Add `research ingest` + `research review` to the research subtree."""

    # ingest
    ing = top_sub.add_parser(
        "ingest",
        help="ingest a corpus into the proposals queue (Lane 1: gbrain adapter)",
    )
    ing.add_argument(
        "--from-gbrain", action="store_true",
        help="hard-require gbrain (raises if not installed)",
    )
    ing.add_argument(
        "--export-file", default=None,
        help="path to a gbrain export JSON file. v0 reads from a file rather "
             "than calling gbrain MCP live; the MCP wiring is a follow-up. "
             "Required when --from-gbrain is passed.",
    )
    ing.add_argument(
        "--query", default="mechanism candidates",
        help="natural-language query recorded in the IngestionRun (audit only "
             "in v0; gbrain MCP path will use this for live retrieval)",
    )
    ing.add_argument(
        "--limit", type=int, default=25,
        help="cap on entities pulled from gbrain (default 25)",
    )
    ing.add_argument(
        "--home", default=None,
        help="vertical home dir (default: ~/.neuro_os_research/)",
    )
    ing.set_defaults(func=_research_ingest_handler)

    # review
    rev = top_sub.add_parser(
        "review",
        help="review pending proposals (Lane 1: minimal CLI REPL; chat surface is a follow-up)",
    )
    rev.add_argument(
        "--cli", action="store_true",
        help="interactive CLI REPL (a/r/s for accept/reject/skip)",
    )
    rev.add_argument(
        "--list", action="store_true",
        help="just list pending proposals as JSON, no prompts",
    )
    rev.add_argument(
        "--home", default=None,
        help="vertical home dir (default: ~/.neuro_os_research/)",
    )
    rev.set_defaults(func=_research_review_handler)

    # dashboard (Lane 5)
    dash = top_sub.add_parser(
        "dashboard",
        help="rollup of the last N days (compound curve + drift modes + queue health)",
    )
    dash.add_argument(
        "--window", type=int, default=40,
        help="window in days (default 40)",
    )
    dash.add_argument(
        "--json", action="store_true",
        help="emit DashboardSummary as JSON (machine-readable)",
    )
    dash.add_argument(
        "--home", default=None,
        help="vertical home dir (default: ~/.neuro_os_research/)",
    )
    dash.set_defaults(func=_research_dashboard_handler)


def _research_ingest_handler(args: argparse.Namespace) -> int:
    from agent.research import GbrainQuerySpec
    from agent.research.gbrain_adapter import (
        append_run_log,
        fetch_from_export_file,
        ingest as gbrain_ingest,
    )
    from agent.research.ingest_router import (
        IngestRouterError,
        detect_extraction_method,
    )

    home = Path(args.home).expanduser() if args.home else None

    try:
        method = detect_extraction_method(
            prefer="gbrain" if args.from_gbrain else "auto",
        )
    except IngestRouterError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if method != "gbrain-mcp":
        # Future: dispatch to Plan A here.
        print(
            f"error: extraction method {method!r} not implemented in Lane 1",
            file=sys.stderr,
        )
        return 2

    if not args.export_file:
        print(
            "error: --export-file <path> is required in Lane 1 (gbrain MCP "
            "live wiring is a follow-up PR)",
            file=sys.stderr,
        )
        return 2

    export_path = Path(args.export_file).expanduser()
    if not export_path.exists():
        print(f"error: gbrain export file not found: {export_path}", file=sys.stderr)
        return 2

    spec = GbrainQuerySpec(query=args.query, limit=args.limit)
    run = gbrain_ingest(
        spec=spec,
        call_gbrain=fetch_from_export_file(export_path),
        home=home,
    )
    append_run_log(run, home=home)
    print(run.model_dump_json(indent=2))
    return 0


def _research_review_handler(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone

    from agent.research import MechanismCard
    from agent.research.config import write_mechanism_card
    from agent.research.proposals import list_proposals, transition_proposal

    home = Path(args.home).expanduser() if args.home else None
    pending = list_proposals(home=home, status="pending")

    if args.list:
        print(json.dumps([p.model_dump(mode="json") for p in pending], indent=2, default=str))
        return 0

    if not pending:
        print("(no pending proposals)")
        return 0

    if not args.cli:
        # Default: print the count and first 3 IDs so the user knows what's there.
        print(f"{len(pending)} pending proposal(s):")
        for p in pending[:3]:
            print(f"  {p.proposal_id}  conf={p.confidence}  source={p.source_id}")
        if len(pending) > 3:
            print(f"  ... and {len(pending) - 3} more. Run with --cli to review interactively.")
        return 0

    # Minimal interactive REPL.
    for prop in pending:
        print("\n" + "=" * 72)
        print(f"id:         {prop.proposal_id}")
        print(f"confidence: {prop.confidence}")
        print(f"source:     {prop.source_id}")
        print(f"title:      {prop.paper_title}")
        print(f"\nmechanism:    {prop.mechanism}")
        print(f"invariant:    {prop.invariant}")
        print(f"prediction:   {prop.prediction}")
        print(f"failure_mode: {prop.failure_mode}")
        print(f"\nexcerpt:    {prop.source_excerpt[:300]}{'...' if len(prop.source_excerpt) > 300 else ''}")
        try:
            choice = input("\n[a]ccept / [r]eject / [s]kip / [q]uit ? ").strip().lower()
        except EOFError:
            print("\n(stdin closed; stopping)")
            return 0
        if choice == "q":
            print("(stopped)")
            return 0
        if choice == "s" or choice == "":
            continue
        if choice == "r":
            transition_proposal(
                prop.proposal_id, home=home,
                from_status="pending", to_status="rejected",
            )
            print(f"  rejected: {prop.proposal_id}")
            continue
        if choice == "a":
            # Build a frozen MechanismCard from the proposal.
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
            )
            write_mechanism_card(card=card, home=home)
            transition_proposal(
                prop.proposal_id, home=home,
                from_status="pending", to_status="accepted",
            )
            print(f"  accepted: {prop.proposal_id}")
            continue
        print(f"  (unknown choice {choice!r}; skipping)")
    print("\n(end of queue)")
    return 0


def _research_dashboard_handler(args: argparse.Namespace) -> int:
    from agent.research.dashboard import build_dashboard_summary, render_text

    if args.window < 1 or args.window > 365:
        print(
            f"error: --window must be between 1 and 365 (got {args.window})",
            file=sys.stderr,
        )
        return 2

    home = Path(args.home).expanduser() if args.home else None
    summary = build_dashboard_summary(home=home, window_days=args.window)
    if args.json:
        print(summary.model_dump_json(indent=2))
    else:
        print(render_text(summary))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
