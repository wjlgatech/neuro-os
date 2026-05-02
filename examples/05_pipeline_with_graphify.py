"""
Example 05 — End-to-end pipeline: graphify → neuro-os.

Reads a ``graph.json`` produced by ``graphify`` (the upstream knowledge-
graph extractor at https://github.com/safishamsi/graphify) and pumps
every node through neuro-os's ingestion pipeline. Each result carries
both graphify's structural provenance (file_type, edge confidences) and
neuro-os's TRUE evaluation.

Usage::

    python examples/05_pipeline_with_graphify.py path/to/graph.json
    # or, with no argument, falls back to the bundled fixture
    python examples/05_pipeline_with_graphify.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.integrations.graphify import process_graphify_graph  # noqa: E402


def main() -> None:
    if len(sys.argv) > 1:
        graph_path = Path(sys.argv[1])
    else:
        graph_path = (
            Path(__file__).resolve().parent.parent
            / "tests"
            / "fixtures"
            / "graphify_sample.json"
        )
    print(f"reading: {graph_path}")
    report = process_graphify_graph(graph_path)
    print(f"  nodes:     {report['node_count']}")
    print(f"  processed: {report['processed']}")
    print(f"  decisions: {report['summary']['decisions']}")
    print(f"  mechanism histogram: {report['summary']['mechanisms']}")
    print()
    print("per-node breakdown:")
    for r in report["results"]:
        print(
            f"  {r['label']:50s}  "
            f"mech={r['neuro_os_mechanism']:25s}  "
            f"decision={r['neuro_os_decision']:6s}  "
            f"evidence={r['graphify_evidence_strength']}"
        )


if __name__ == "__main__":
    main()
