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

    # Lane 2 auto-emission: when --override-of is set, also write a
    # skillify OverrideEvent so the catalog-evolution loop gets data.
    # Without this flag, the user has to run two commands per override.
    override_event = None
    override_of = getattr(args, "override_of", None)
    if override_of:
        from agent.skillify import write_override_event
        override_event = write_override_event(
            vertical=getattr(args, "override_vertical", "founder_loop"),
            drift_mode=override_of,
            user_action=args.context or args.urge_type,
            suggested_action=None,
            notes=f"Auto-emitted from `loop urge {args.urge_type}`",
            ts=when,
        )

    payload = json.loads(event.model_dump_json())
    if override_event is not None:
        payload["override_event"] = json.loads(override_event.model_dump_json())
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_loop_anchor(args: argparse.Namespace) -> int:
    from datetime import datetime
    from agent.founder_loop.anchors import write_anchor

    home = Path(args.home).expanduser() if args.home else None
    when = datetime.fromisoformat(args.at) if args.at else None
    anchor = write_anchor(
        kind=args.kind,
        context=args.context,
        home=home,
        ts=when,
    )
    print(anchor.model_dump_json(indent=2))
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
    loop_urge.add_argument(
        "--override-of", default=None,
        help=(
            "drift mode label this urge represents an override of (one "
            "of the substrate's named modes for any vertical). When set, "
            "in addition to logging the UrgeEvent, also emit a skillify "
            "OverrideEvent so the catalog-evolution loop (Lane 2) gets "
            "data automatically. Without this flag the user has to run "
            "two commands per override; with it, one."
        ),
    )
    loop_urge.add_argument(
        "--override-vertical", default="founder_loop",
        choices=["founder_loop", "research", "investment", "startup"],
        help=(
            "vertical the --override-of mode belongs to (default: founder_loop)."
        ),
    )
    loop_urge.set_defaults(func=_cmd_loop_urge)

    # loop anchor (Paul's week PR-2 — faith / relational pillars)
    loop_anchor = loop_sub.add_parser(
        "anchor",
        help="log a daily faith or relational anchor (typed, append-only)",
    )
    loop_anchor.add_argument(
        "--kind", required=True, choices=["faith", "relational"],
        help="anchor kind",
    )
    loop_anchor.add_argument(
        "--context", required=True,
        help="short free-text marker for what happened (≤400 chars)",
    )
    loop_anchor.add_argument(
        "--at", default=None,
        help="ISO timestamp (default: now)",
    )
    loop_anchor.add_argument(
        "--home", default=None,
        help="founder_loop home dir (default: ~/.founder_loop/)",
    )
    loop_anchor.set_defaults(func=_cmd_loop_anchor)

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

    _add_skillify_subcommands(sub)
    _add_cross_vertical_subcommands(sub)

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
        help="ingest a corpus into the proposals queue (gbrain adapter OR native LLM extractor)",
    )
    ing.add_argument(
        "--prefer", default="auto", choices=["auto", "gbrain", "local"],
        help=(
            "extractor preference. 'auto' (default) prefers gbrain when "
            "installed, falls back to native LLM. 'gbrain' hard-requires "
            "gbrain (raises if absent). 'local' forces the native LLM "
            "extractor (Plan A) on .txt/.md/.pdf source files."
        ),
    )
    # gbrain-only flags:
    ing.add_argument(
        "--from-gbrain", action="store_true",
        help="alias for --prefer gbrain (kept for backwards compat)",
    )
    ing.add_argument(
        "--export-file", default=None,
        help="(gbrain only) path to a gbrain export JSON file. Required "
             "when the chosen extractor is gbrain-mcp.",
    )
    ing.add_argument(
        "--query", default="mechanism candidates",
        help="(gbrain only) natural-language query recorded in IngestionRun.",
    )
    ing.add_argument(
        "--limit", type=int, default=25,
        help="(gbrain only) cap on entities pulled from gbrain (default 25)",
    )
    # Plan A (local) flags:
    ing.add_argument(
        "--source-dir", default=None,
        help="(local extractor) directory of .txt/.md/.pdf source files. "
             "Required when the chosen extractor is llm-anthropic.",
    )
    ing.add_argument(
        "--no-llm", action="store_true",
        help="(local extractor) skip LLM calls; use the regex heuristic. "
             "Fast + free + offline; produces low-confidence proposals.",
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

    # entity-list (Lane 4)
    elist = top_sub.add_parser(
        "entity-list",
        help="list entities visible to the research vertical (Lane 4)",
    )
    elist.add_argument(
        "--kind", default=None,
        choices=["person", "company", "topic", "mechanism", "other"],
        help="filter by entity kind",
    )
    elist.add_argument(
        "--reader", default="research",
        choices=["research", "investment", "startup", "founder_loop"],
        help=(
            "vertical issuing the read (default: research). Useful to test "
            "cross-vertical visibility from another vertical's perspective."
        ),
    )
    elist.add_argument(
        "--store", default=None,
        help="cross-vertical store path (default: ~/.neuro_os/cross_vertical.jsonl)",
    )
    elist.set_defaults(func=_research_entity_list_handler)

    # entity-read (Lane 4)
    eread = top_sub.add_parser(
        "entity-read",
        help="read a single entity's latest visible snapshot (Lane 4)",
    )
    eread.add_argument("--slug", required=True, help="entity slug to read")
    eread.add_argument(
        "--reader", default="research",
        choices=["research", "investment", "startup", "founder_loop"],
    )
    eread.add_argument(
        "--store", default=None,
        help="cross-vertical store path (default: ~/.neuro_os/cross_vertical.jsonl)",
    )
    eread.set_defaults(func=_research_entity_read_handler)

    # synthesize (Layer 2): cluster accepted MechanismCards by mechanism.
    syn = top_sub.add_parser(
        "synthesize",
        help="Layer-2: cluster accepted MechanismCards by mechanism (not topic)",
    )
    syn.add_argument(
        "--window", type=int, default=30,
        help="window in days over which to gather accepted cards (default 30)",
    )
    syn.add_argument(
        "--min-cluster-size", type=int, default=2,
        help="minimum members per emitted cluster (default 2)",
    )
    syn.add_argument(
        "--no-llm", action="store_true",
        help="force the heuristic Jaccard clusterer; skip LLM call",
    )
    syn.add_argument(
        "--json", action="store_true",
        help="emit the SynthesisRun as JSON (machine-readable)",
    )
    syn.add_argument(
        "--home", default=None,
        help="vertical home dir (default: ~/.neuro_os_research/)",
    )
    syn.set_defaults(func=_research_synthesize_handler)

    # brief (Layer 3): decision-ready brief grounded in a ProjectContext.
    brf = top_sub.add_parser(
        "brief",
        help="Layer-3: generate a decision-ready brief for one cluster",
    )
    brf.add_argument(
        "--cluster-id", required=True,
        help="cluster_id from a prior `research synthesize` run",
    )
    brf.add_argument(
        "--context-file", required=True,
        help="path to a ProjectContext JSON file (project_name, "
             "current_questions, collaborators, pending_decisions)",
    )
    brf.add_argument(
        "--no-llm", action="store_true",
        help="force the templated brief; skip LLM call",
    )
    brf.add_argument(
        "--json", action="store_true",
        help="emit DecisionBrief as JSON (default: markdown to stdout)",
    )
    brf.add_argument(
        "--home", default=None,
        help="vertical home dir (default: ~/.neuro_os_research/)",
    )
    brf.set_defaults(func=_research_brief_handler)

    # checkpoint: stop-condition gate (did the system actually converge?)
    chk = top_sub.add_parser(
        "checkpoint",
        help="Log a stop-condition checkpoint (brief produced? mental model clearer?)",
    )
    chk.add_argument(
        "--brief-produced", choices=["yes", "no"], required=True,
        help="did the last synthesis cycle produce a brief that you used?",
    )
    chk.add_argument(
        "--clearer", choices=["yes", "no"], required=True,
        help="did your mental model on the active thesis get clearer?",
    )
    chk.add_argument("--note", default=None, help="freeform note (≤ 600 chars)")
    chk.add_argument(
        "--home", default=None,
        help="vertical home dir (default: ~/.neuro_os_research/)",
    )
    chk.set_defaults(func=_research_checkpoint_handler)


def _research_ingest_handler(args: argparse.Namespace) -> int:
    from agent.research.ingest_router import (
        IngestRouterError,
        detect_extraction_method,
    )

    home = Path(args.home).expanduser() if args.home else None

    # --from-gbrain is an alias for --prefer gbrain (back-compat).
    prefer = "gbrain" if args.from_gbrain else args.prefer

    try:
        method = detect_extraction_method(prefer=prefer)
    except IngestRouterError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if method == "gbrain-mcp":
        return _research_ingest_gbrain(args, home)
    elif method == "llm-anthropic":
        return _research_ingest_local(args, home)
    else:
        print(f"error: unknown extraction method {method!r}", file=sys.stderr)
        return 2


def _research_ingest_gbrain(args: argparse.Namespace, home: Optional[Path]) -> int:
    from agent.research import GbrainQuerySpec
    from agent.research.gbrain_adapter import (
        append_run_log,
        fetch_from_export_file,
        ingest as gbrain_ingest,
    )

    if not args.export_file:
        print(
            "error: --export-file <path> is required when the gbrain "
            "extractor is chosen (live MCP wiring is a follow-up).",
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


def _research_ingest_local(args: argparse.Namespace, home: Optional[Path]) -> int:
    """Plan A: native LLM extractor on a directory of source files."""
    from agent.research.gbrain_adapter import append_run_log
    from agent.research.ingest import ingest as local_ingest

    if not args.source_dir:
        print(
            "error: --source-dir <path> is required when the local "
            "extractor is chosen. Pass a directory of .txt/.md/.pdf files.",
            file=sys.stderr,
        )
        return 2
    source_dir = Path(args.source_dir).expanduser()
    if not source_dir.exists():
        print(f"error: source dir not found: {source_dir}", file=sys.stderr)
        return 2
    if not source_dir.is_dir():
        print(f"error: not a directory: {source_dir}", file=sys.stderr)
        return 2

    llm_fn = None
    if not args.no_llm:
        llm_fn = _make_anthropic_llm_fn()

    run = local_ingest(source_dir=source_dir, llm_fn=llm_fn, home=home)
    append_run_log(run, home=home)
    print(run.model_dump_json(indent=2))
    return 0


def _make_anthropic_llm_fn():
    """Build an LLM callable wired to Anthropic Haiku, OR None if no key.

    Returning None tells ``ingest`` to use the regex heuristic — same
    contract as ``--no-llm``. Honest fallback so users without API keys
    still get a working pipeline (with low-confidence proposals).
    """
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None

    client = anthropic.Anthropic()

    def llm_fn(system_prompt: str, user_text: str) -> List[dict]:
        # Single Haiku call per source. Trim user_text upstream of this.
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_text}],
        )
        # Expect a JSON array of objects in the first text block.
        body = "".join(
            getattr(b, "text", "") for b in resp.content
            if getattr(b, "type", None) == "text"
        )
        # Crude JSON extraction: find the first '[' through the last ']'.
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
            # Lane-4 entity propagation: ask the user to name entities this
            # card mentions. Format is comma-separated kebab-case slugs;
            # blank input = no propagation. v0 is opt-in (no auto-extract).
            try:
                mentions_raw = input(
                    "  entity mentions (comma-separated kebab slugs, blank = none): "
                ).strip()
            except EOFError:
                mentions_raw = ""
            mentions = [
                m.strip().lower()
                for m in mentions_raw.split(",")
                if m.strip()
            ] if mentions_raw else []

            # Build a frozen MechanismCard from the proposal — inheriting
            # the optional Layer-1 deepening fields (first_principle /
            # anti_pattern / transferability_test / verdict /
            # one_sentence_compression / framework_alignment) so Layer 2
            # synthesis and Layer 3 briefs can read them post-accept.
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
            write_mechanism_card(card=card, home=home)
            transition_proposal(
                prop.proposal_id, home=home,
                from_status="pending", to_status="accepted",
            )

            # Lane-4: upsert each mentioned entity. Default-PRIVATE to research.
            if mentions:
                from agent.cross_vertical import upsert_entity
                # The card was just persisted via write_mechanism_card, which
                # also wrote a cross_vertical note (kind="mechanism_card").
                # We don't have the note id back, so we use the card's own id
                # as the originating reference.
                for slug in mentions:
                    upsert_entity(
                        slug=slug,
                        kind="topic",   # v0 default; richer kinds are a follow-up
                        title=slug.replace("-", " ").title(),
                        source_vertical="research",
                        compiled_truth=(
                            f"Mentioned in MechanismCard {card.id} "
                            f"({card.paper_title!r})."
                        ),
                        mentioned_in_note_id=card.id,
                    )
                print(f"  accepted: {prop.proposal_id} (with {len(mentions)} entity mention(s))")
            else:
                print(f"  accepted: {prop.proposal_id}")
            continue
        print(f"  (unknown choice {choice!r}; skipping)")
    print("\n(end of queue)")
    return 0


def _research_entity_list_handler(args: argparse.Namespace) -> int:
    from agent.cross_vertical import list_entities

    store = Path(args.store).expanduser() if args.store else None
    entities = list_entities(reader=args.reader, kind=args.kind, store=store)
    print(json.dumps(
        [e.model_dump(mode="json") for e in entities],
        indent=2, default=str,
    ))
    return 0


def _research_entity_read_handler(args: argparse.Namespace) -> int:
    from agent.cross_vertical import read_entity

    store = Path(args.store).expanduser() if args.store else None
    entity = read_entity(slug=args.slug, reader=args.reader, store=store)
    if entity is None:
        print(f"(no entity {args.slug!r} visible to {args.reader!r})")
        return 0
    print(entity.model_dump_json(indent=2))
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


def _research_synthesize_handler(args: argparse.Namespace) -> int:
    from agent.research.synthesis import run_synthesis

    home = Path(args.home).expanduser() if args.home else None
    if args.window < 1 or args.window > 365:
        print(
            f"error: --window must be between 1 and 365 (got {args.window})",
            file=sys.stderr,
        )
        return 2
    if args.min_cluster_size < 1 or args.min_cluster_size > 20:
        print(
            f"error: --min-cluster-size must be between 1 and 20 (got "
            f"{args.min_cluster_size})",
            file=sys.stderr,
        )
        return 2

    llm_fn = None
    if not args.no_llm:
        llm_fn = _make_anthropic_cluster_fn()

    run = run_synthesis(
        home=home,
        window_days=args.window,
        min_cluster_size=args.min_cluster_size,
        llm_fn=llm_fn,
    )
    if args.json:
        print(run.model_dump_json(indent=2))
        return 0
    # Human-readable summary.
    print(f"synthesis run: {run.run_id}")
    print(f"  method:   {run.method}")
    print(f"  window:   {run.window_days}d   cards in window: {run.input_card_count}")
    print(f"  clusters: {len(run.clusters)}")
    for cluster in run.clusters:
        print(f"\n  • {cluster.label} ({len(cluster.member_card_ids)} cards)")
        print(f"    summary: {cluster.mechanism_summary[:200]}")
        if cluster.shared_first_principle:
            print(f"    first principle: {cluster.shared_first_principle[:200]}")
        if cluster.recurring_anti_pattern:
            print(f"    anti-pattern:    {cluster.recurring_anti_pattern[:200]}")
        if cluster.frontier_position:
            print(f"    frontier:        {cluster.frontier_position}")
        if cluster.framework_axes_touched:
            print(f"    axes touched:    {', '.join(cluster.framework_axes_touched)}")
    if run.unclustered_card_ids:
        print(f"\n  unclustered: {len(run.unclustered_card_ids)} cards")
    if run.note:
        print(f"\n  note: {run.note}")
    return 0


def _research_brief_handler(args: argparse.Namespace) -> int:
    from agent.research.briefs import (
        ProjectContext,
        generate_brief,
        write_brief,
    )
    from agent.research.synthesis import list_synthesis_runs

    home = Path(args.home).expanduser() if args.home else None

    ctx_path = Path(args.context_file).expanduser()
    if not ctx_path.exists():
        print(f"error: context file not found: {ctx_path}", file=sys.stderr)
        return 2
    try:
        ctx = ProjectContext.model_validate_json(ctx_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"error: invalid ProjectContext in {ctx_path}: {e}", file=sys.stderr)
        return 2

    # Find the cluster across all recent synthesis runs.
    target_cluster = None
    target_run = None
    for run in list_synthesis_runs(home=home, limit=20):
        for c in run.clusters:
            if c.cluster_id == args.cluster_id:
                target_cluster = c
                target_run = run
                break
        if target_cluster is not None:
            break
    if target_cluster is None:
        print(
            f"error: cluster_id {args.cluster_id!r} not found in the 20 "
            f"most recent synthesis runs. Run `research synthesize` first.",
            file=sys.stderr,
        )
        return 2

    llm_fn = None
    if not args.no_llm:
        llm_fn = _make_anthropic_brief_fn()

    brief = generate_brief(
        cluster=target_cluster,
        context=ctx,
        synthesis_run_id=target_run.run_id,
        llm_fn=llm_fn,
    )
    write_brief(brief, home=home)
    if args.json:
        print(brief.model_dump_json(indent=2))
    else:
        from agent.research.briefs import render_markdown
        print(render_markdown(brief, cluster=target_cluster))
    return 0


def _research_checkpoint_handler(args: argparse.Namespace) -> int:
    import uuid
    from datetime import datetime, timezone

    from agent.research.checkpoints import (
        ResearchCheckpoint,
        recent_no_streak,
        write_checkpoint,
    )

    home = Path(args.home).expanduser() if args.home else None
    note = (args.note or "").strip()[:600] or None
    checkpoint = ResearchCheckpoint(
        checkpoint_id=f"chk-{uuid.uuid4().hex[:10]}",
        ts=datetime.now(timezone.utc),
        brief_produced=(args.brief_produced == "yes"),
        mental_model_clearer=(args.clearer == "yes"),
        note=note,
    )
    write_checkpoint(checkpoint, home=home)
    print(f"checkpoint logged: {checkpoint.checkpoint_id}")
    streak = recent_no_streak(home=home, k=5)
    if streak >= 2:
        print(
            f"WARNING: {streak} consecutive non-converging checkpoint(s). "
            f"System not converting; redesign before adding more inputs."
        )
    return 0


def _make_anthropic_cluster_fn():
    """LLM callable for synthesis. Same shape + key check as ingest's
    Haiku callable; returns None if no key."""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    client = anthropic.Anthropic()

    def llm_fn(system_prompt: str, user_text: str) -> List[dict]:
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


def _make_anthropic_brief_fn():
    """LLM callable for brief generation. Same shape as cluster_fn but
    expects a single JSON object response (not an array)."""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    client = anthropic.Anthropic()

    def llm_fn(system_prompt: str, user_text: str) -> Optional[dict]:
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
        if not isinstance(parsed, dict):
            return None
        return parsed

    return llm_fn


# ---------------------------------------------------------------------------
# Skillify CLI tree (Lane 2)
# ---------------------------------------------------------------------------


def _add_skillify_subcommands(sub: "argparse._SubParsersAction") -> None:
    """Top-level `skillify` subcommands: log-override / extract /
    proposals / review."""
    top = sub.add_parser(
        "skillify",
        help="meta-skill: turn repeated overrides into catalog-revision proposals (Lane 2)",
    )
    top_sub = top.add_subparsers(dest="skillify_command", required=True)

    # log-override
    lo = top_sub.add_parser(
        "log-override",
        help="log one OverrideEvent (the user picked something other than the proposed CE)",
    )
    lo.add_argument(
        "--vertical", required=True,
        choices=["founder_loop", "research", "investment", "startup"],
    )
    lo.add_argument(
        "--drift", required=True,
        help="the drift mode that fired (must match the vertical's catalog)",
    )
    lo.add_argument(
        "--user-action", required=True,
        help="what you did instead of the proposed constructive expression",
    )
    lo.add_argument("--suggested-action", default=None,
                    help="optional: what the substrate proposed (the CE you rejected)")
    lo.add_argument("--notes", default=None,
                    help="optional one-paragraph: WHY you chose your alternative")
    lo.add_argument("--home", default=None,
                    help="skillify home (default: ~/.neuro_os_skillified/)")
    lo.set_defaults(func=_skillify_log_override_handler)

    # extract
    ex = top_sub.add_parser(
        "extract",
        help="run pattern extraction over the override log; emit SkillProposals",
    )
    ex.add_argument("--vertical", default=None,
                    choices=["founder_loop", "research", "investment", "startup"],
                    help="filter by vertical (default: all)")
    ex.add_argument("--threshold", type=int, default=5,
                    help="minimum events per (vertical, drift_mode) bucket to propose (default 5)")
    ex.add_argument("--window-days", type=int, default=30,
                    help="only consider events within this window (default 30)")
    ex.add_argument("--no-skip-existing", action="store_true",
                    help="re-propose buckets that already have pending/accepted proposals")
    ex.add_argument("--home", default=None)
    ex.set_defaults(func=_skillify_extract_handler)

    # proposals
    pl = top_sub.add_parser(
        "proposals",
        help="list SkillProposals in a status directory",
    )
    pl.add_argument("--status", default="pending",
                    choices=["pending", "accepted", "rejected"])
    pl.add_argument("--home", default=None)
    pl.set_defaults(func=_skillify_proposals_handler)

    # review
    rv = top_sub.add_parser(
        "review",
        help="review pending SkillProposals (CLI REPL: a/r/s/q)",
    )
    rv.add_argument("--cli", action="store_true",
                    help="interactive REPL (default just prints count)")
    rv.add_argument("--home", default=None)
    rv.set_defaults(func=_skillify_review_handler)


def _skillify_log_override_handler(args: argparse.Namespace) -> int:
    from agent.skillify import write_override_event

    home = Path(args.home).expanduser() if args.home else None
    event = write_override_event(
        vertical=args.vertical,
        drift_mode=args.drift,
        user_action=args.user_action,
        suggested_action=args.suggested_action,
        notes=args.notes,
        home=home,
    )
    print(event.model_dump_json(indent=2))
    return 0


def _skillify_extract_handler(args: argparse.Namespace) -> int:
    from agent.skillify import run_extraction

    if args.threshold < 1:
        print(f"error: --threshold must be >= 1 (got {args.threshold})", file=sys.stderr)
        return 2
    if args.window_days < 1:
        print(f"error: --window-days must be >= 1 (got {args.window_days})", file=sys.stderr)
        return 2

    home = Path(args.home).expanduser() if args.home else None
    written = run_extraction(
        vertical=args.vertical,
        threshold=args.threshold,
        window_days=args.window_days,
        home=home,
        skip_already_proposed=not args.no_skip_existing,
    )
    print(json.dumps(
        [p.model_dump(mode="json") for p in written],
        indent=2, default=str,
    ))
    print(f"\n{len(written)} new SkillProposal(s) written to "
          f"{home or Path.home() / '.neuro_os_skillified'}/proposals/pending/",
          file=sys.stderr)
    return 0


def _skillify_proposals_handler(args: argparse.Namespace) -> int:
    from agent.skillify import list_skill_proposals

    home = Path(args.home).expanduser() if args.home else None
    proposals = list_skill_proposals(home=home, status=args.status)
    print(json.dumps(
        [p.model_dump(mode="json") for p in proposals],
        indent=2, default=str,
    ))
    return 0


def _skillify_review_handler(args: argparse.Namespace) -> int:
    from agent.skillify import (
        list_skill_proposals,
        transition_skill_proposal,
    )

    home = Path(args.home).expanduser() if args.home else None
    pending = list_skill_proposals(home=home, status="pending")

    if not pending:
        print("(no pending skill proposals)")
        return 0

    if not args.cli:
        print(f"{len(pending)} pending skill proposal(s):")
        for p in pending[:5]:
            print(f"  {p.proposal_id}  {p.vertical}/{p.drift_mode}  "
                  f"(based on {p.based_on_event_count} events)")
        if len(pending) > 5:
            print(f"  ... and {len(pending) - 5} more. Run with --cli to review.")
        return 0

    for prop in pending:
        print("\n" + "=" * 72)
        print(f"id:               {prop.proposal_id}")
        print(f"vertical/drift:   {prop.vertical} / {prop.drift_mode}")
        print(f"candidate action: {prop.candidate_action}")
        print(f"duration_min:     {prop.candidate_duration_min}")
        print(f"tank_credit_pct:  {prop.candidate_tank_credit_pct}")
        print(f"based_on_events:  {prop.based_on_event_count} "
              f"({', '.join(prop.based_on_event_ids[:3])}{'...' if len(prop.based_on_event_ids) > 3 else ''})")
        if prop.notes:
            print(f"notes:            {prop.notes[:300]}")
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
            transition_skill_proposal(
                prop.proposal_id, home=home,
                from_status="pending", to_status="rejected",
            )
            print(f"  rejected: {prop.proposal_id}")
            continue
        if choice == "a":
            transition_skill_proposal(
                prop.proposal_id, home=home,
                from_status="pending", to_status="accepted",
            )
            print(f"  accepted: {prop.proposal_id}  (catalog mutation is a "
                  f"separate human-authored commit — Law 7)")
            continue
        print(f"  (unknown choice {choice!r}; skipping)")
    print("\n(end of queue)")
    return 0


# ---------------------------------------------------------------------------
# Cross-vertical CLI tree (Paul's week PR-2)
# ---------------------------------------------------------------------------


def _add_cross_vertical_subcommands(sub: "argparse._SubParsersAction") -> None:
    """Top-level `cross-vertical` subcommand: share-note / query."""
    top = sub.add_parser(
        "cross-vertical",
        help=(
            "cross-vertical store ops (share notes across verticals, query "
            "with visibility-aware reads)"
        ),
    )
    top_sub = top.add_subparsers(dest="cross_vertical_command", required=True)

    # share-note
    sn = top_sub.add_parser(
        "share-note",
        help="broaden a note's visibility to one or more verticals",
    )
    sn.add_argument("--note-id", required=True, help="VerticalNote id to share")
    sn.add_argument(
        "--with", dest="with_verticals", required=True,
        help=(
            "comma-separated vertical names (founder_loop / research / "
            "investment / startup) OR the special token __all__"
        ),
    )
    sn.add_argument("--store", default=None,
                    help="cross-vertical store path (default: ~/.neuro_os/cross_vertical.jsonl)")
    sn.set_defaults(func=_cross_vertical_share_note_handler)

    # query
    q = top_sub.add_parser(
        "query",
        help="read notes a vertical is allowed to see",
    )
    q.add_argument(
        "--reader", required=True,
        choices=["founder_loop", "research", "investment", "startup"],
        help="vertical issuing the read",
    )
    q.add_argument(
        "--kind", default=None, action="append",
        help="filter by note_kind (repeatable)",
    )
    q.add_argument(
        "--source", default=None, action="append",
        choices=["founder_loop", "research", "investment", "startup"],
        help="filter by source vertical (repeatable)",
    )
    q.add_argument(
        "--store", default=None,
        help="cross-vertical store path",
    )
    q.set_defaults(func=_cross_vertical_query_handler)


def _cross_vertical_share_note_handler(args: argparse.Namespace) -> int:
    from agent.cross_vertical import query as cv_query, share_note

    store = Path(args.store).expanduser() if args.store else None

    add_visible = [v.strip() for v in args.with_verticals.split(",") if v.strip()]
    if not add_visible:
        print("error: --with must be a non-empty comma-separated list", file=sys.stderr)
        return 2
    valid = {"founder_loop", "research", "investment", "startup", "__all__"}
    bad = [v for v in add_visible if v not in valid]
    if bad:
        print(
            f"error: unknown vertical(s) in --with: {bad!r} "
            f"(allowed: {sorted(valid)})",
            file=sys.stderr,
        )
        return 2

    # Verify the note exists by querying as the founder_loop reader
    # (the source vertical is allowed to see its own; we use that to
    # confirm existence in the store).
    found_id = None
    for source in ("founder_loop", "research", "investment", "startup"):
        for n in cv_query(reader=source, store=store):
            if n.id == args.note_id:
                found_id = n.id
                break
        if found_id:
            break
    if found_id is None:
        print(f"error: note id {args.note_id!r} not found in store", file=sys.stderr)
        return 2

    share_note(note_id=args.note_id, add_visible=add_visible, store=store)
    print(json.dumps({
        "shared": True,
        "note_id": args.note_id,
        "add_visible": add_visible,
    }, indent=2))
    return 0


def _cross_vertical_query_handler(args: argparse.Namespace) -> int:
    from agent.cross_vertical import query as cv_query

    store = Path(args.store).expanduser() if args.store else None
    notes = cv_query(
        reader=args.reader,
        kinds=args.kind,
        sources=args.source,
        store=store,
    )
    print(json.dumps(
        [n.model_dump(mode="json") for n in notes],
        indent=2, default=str,
    ))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
