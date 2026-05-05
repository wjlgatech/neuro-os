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

    loop = FounderLoop(
        registry_path=args.registry,
        contract_path=args.contracts,
        workflowx_export_path=args.workflowx_fixture,
        use_llm=bool(args.use_llm),
    )
    now = datetime.fromisoformat(args.at) if args.at else None
    result = loop.tick(intent=args.intent, now=now, dry_run=args.dry_run)
    print(json.dumps(json.loads(result.model_dump_json()), indent=2))
    return 0


def _cmd_loop_serve(args: argparse.Namespace) -> int:
    import logging
    from agent.founder_loop.server import serve

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    serve(
        host=args.host,
        port=args.port,
        registry_path=Path(args.registry),
        contract_path=Path(args.contracts),
        workflowx_fixture=Path(args.workflowx_fixture),
        events_path=Path(args.events) if args.events else None,
        use_llm=bool(args.use_llm),
        block=True,
    )
    return 0


def _cmd_loop_nightly(args: argparse.Namespace) -> int:
    from datetime import datetime
    from agent.founder_loop import FounderLoop

    loop = FounderLoop(
        registry_path=args.registry,
        contract_path=args.contracts,
        workflowx_export_path=args.workflowx_fixture,
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
    loop_tick.add_argument("--workflowx-fixture", required=True,
                           help="JSONL fixture file (v0 always uses fixture adapter)")
    loop_tick.add_argument("--intent", help="optional: override last_intent")
    loop_tick.add_argument("--at", help="ISO timestamp to tick at (default: now)")
    loop_tick.add_argument("--use-llm", action="store_true",
                           help="route predict.py + sublimate.py through Anthropic API")
    loop_tick.add_argument("--dry-run", action="store_true",
                           help="produce a TickResult without writing the registry")
    loop_tick.set_defaults(func=_cmd_loop_tick)

    loop_serve = loop_sub.add_parser(
        "serve", help="start the local HTTP daemon for browser extension + tray app"
    )
    loop_serve.add_argument("--registry", required=True)
    loop_serve.add_argument("--contracts", required=True)
    loop_serve.add_argument("--workflowx-fixture", required=True)
    loop_serve.add_argument("--events", help="events log path (default: registry sibling events.jsonl)")
    loop_serve.add_argument("--host", default="127.0.0.1")
    loop_serve.add_argument("--port", type=int, default=8765)
    loop_serve.add_argument("--use-llm", action="store_true")
    loop_serve.set_defaults(func=_cmd_loop_serve)

    loop_nightly = loop_sub.add_parser(
        "nightly", help="end-of-day rollup: MAE, contract-honor, goldens"
    )
    loop_nightly.add_argument("--registry", required=True)
    loop_nightly.add_argument("--contracts", required=True)
    loop_nightly.add_argument("--workflowx-fixture", required=True)
    loop_nightly.add_argument("--at", help="ISO timestamp to roll up at (default: now)")
    loop_nightly.set_defaults(func=_cmd_loop_nightly)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
