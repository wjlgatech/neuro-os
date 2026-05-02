"""
Graphify -> neuro-os bridge.

`graphify` (https://github.com/safishamsi/graphify) extracts a
NetworkX-shaped knowledge graph from any folder — code, docs, papers,
images, video. Its output ``graph.json`` is the natural upstream feed
for neuro-os: every node is a candidate piece of knowledge, every link
is structural context, and every edge carries a confidence label
(``EXTRACTED`` / ``INFERRED`` / ``AMBIGUOUS``) that maps cleanly onto
neuro-os's ``evidence_strength`` axis.

This module bridges the formats. It does not depend on the ``graphify``
package being installed — it only reads the on-disk ``graph.json`` it
produces.

Public API:

* ``load_graph(path)`` — read graphify's ``graph.json`` schema.
* ``graphify_node_to_text(node, graph)`` — synthesize a context-aware
  text representation of a single node + its neighborhood.
* ``confidence_to_evidence_strength(confidences)`` — aggregate one or
  more graphify confidence labels into a neuro-os ``evidence_strength``
  label (``"strong" | "moderate" | "weak"``).
* ``process_graphify_graph(path, ontology=None, max_nodes=None,
  min_incoming_edges=0)`` — pump every node through neuro-os's
  ``run_pipeline`` and return a structured per-node report plus a
  decision histogram.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from agent.ingestion_pipeline import _canonical_ontology, run_pipeline


_CONFIDENCE_RANK: Dict[str, int] = {
    "EXTRACTED": 3,
    "INFERRED": 2,
    "AMBIGUOUS": 1,
}


def load_graph(path: Union[str, Path]) -> Dict[str, Any]:
    """Read a graphify ``graph.json`` from disk."""
    with Path(path).open("r", encoding="utf-8") as f:
        graph = json.load(f)
    if not isinstance(graph, dict) or "nodes" not in graph:
        raise ValueError(
            f"file at {path!s} does not look like a graphify graph "
            f"(no 'nodes' key)"
        )
    return graph


def confidence_to_evidence_strength(
    confidences: Iterable[Optional[str]],
) -> str:
    """Aggregate graphify confidence labels into an evidence_strength.

    Heuristic: take the strongest label present.

    * Any ``EXTRACTED`` → ``"strong"``
    * Any ``INFERRED`` (no extracted) → ``"moderate"``
    * Any ``AMBIGUOUS`` (no inferred or extracted) → ``"weak"``
    * Empty / unrecognized → ``"weak"``
    """
    best = 0
    for c in confidences:
        if c is None:
            continue
        rank = _CONFIDENCE_RANK.get(c.upper(), 0)
        if rank > best:
            best = rank
    if best == 3:
        return "strong"
    if best == 2:
        return "moderate"
    return "weak"


def _edges_for(node_id: str, graph: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out_edges: List[Dict[str, Any]] = []
    in_edges: List[Dict[str, Any]] = []
    for link in graph.get("links", []) or []:
        if link.get("source") == node_id:
            out_edges.append(link)
        elif link.get("target") == node_id:
            in_edges.append(link)
    return {"out": out_edges, "in": in_edges}


def _label_for(node_id: str, by_id: Dict[str, Dict[str, Any]]) -> str:
    """Return a human-meaningful label for a node id; fall back to id."""
    node = by_id.get(node_id, {})
    return str(node.get("label") or node_id)


def graphify_node_to_text(
    node: Dict[str, Any],
    graph: Dict[str, Any],
    max_neighbors: int = 5,
) -> str:
    """Synthesize a text representation of a node + its immediate context.

    Uses neighbor *labels* (not ids) so internal id naming never leaks
    classifier-relevant tokens into the synthesized text. The text is
    what neuro-os's ingestion pipeline classifies.
    """
    label = str(node.get("label", node.get("id", "")))
    file_type = node.get("file_type", "unknown")
    edges = _edges_for(node.get("id", ""), graph)
    by_id = {n.get("id"): n for n in graph.get("nodes", []) if n.get("id")}
    parts: List[str] = [f"{label} ({file_type})"]
    if edges["out"]:
        rels = ", ".join(
            f"{(e.get('relation') or 'related').replace('_', ' ')} {_label_for(e.get('target', ''), by_id)}"
            for e in edges["out"][:max_neighbors]
        )
        parts.append(f"uses {rels}")
    if edges["in"]:
        rels = ", ".join(
            f"{(e.get('relation') or 'related').replace('_', ' ')} from {_label_for(e.get('source', ''), by_id)}"
            for e in edges["in"][:max_neighbors]
        )
        parts.append(f"used by {rels}")
    return ". ".join(parts)


def _node_confidences(node_id: str, graph: Dict[str, Any]) -> List[str]:
    confidences: List[str] = []
    for link in graph.get("links", []) or []:
        if link.get("source") == node_id or link.get("target") == node_id:
            c = link.get("confidence")
            if c:
                confidences.append(c)
    return confidences


def _classification_text(node: Dict[str, Any]) -> str:
    """The short text used to classify a node.

    Uses the node's own label only — neighbor context is intentionally
    excluded so a strongly-classified neighbor doesn't leak its mechanism
    into the synthesized text of an adjacent node.
    """
    label = str(node.get("label", node.get("id", "")))
    file_type = node.get("file_type", "unknown")
    return f"{label} ({file_type})"


def process_graphify_graph(
    path: Union[str, Path],
    ontology: Optional[Dict[str, Any]] = None,
    max_nodes: Optional[int] = None,
    min_incoming_edges: int = 0,
    with_neighbor_context: bool = False,
) -> Dict[str, Any]:
    """Pump a graphify ``graph.json`` through neuro-os's ingestion pipeline.

    Each node is converted to a text representation, classified by
    ``run_pipeline``, and tagged with graphify provenance (confidence
    aggregation, source_file, file_type).

    Parameters
    ----------
    path : str | Path
        Path to ``graph.json`` produced by graphify.
    ontology : dict, optional
        Ontology to classify against. Defaults to the canonical
        neuroscience ontology.
    max_nodes : int, optional
        Cap on the number of nodes processed (useful for large graphs).
    min_incoming_edges : int
        Skip nodes with fewer than this many incoming edges. Filters
        out "lonely" nodes that are typically extraction noise.
    with_neighbor_context : bool
        When True, classify against text that includes neighbor labels
        and relations. Useful when labels alone are ambiguous, but
        risks leaking a strongly-classified neighbor's mechanism into
        an adjacent node. Default False.

    Returns
    -------
    dict
        ``{node_count, processed, summary, results}`` where ``results``
        is a list of per-node records and ``summary`` is a histogram of
        pipeline decisions and predicted mechanisms.
    """
    graph = load_graph(path)
    nodes = list(graph.get("nodes", []))
    ont = ontology if ontology is not None else _canonical_ontology()

    decisions: Counter = Counter()
    mechanisms: Counter = Counter()
    results: List[Dict[str, Any]] = []
    processed = 0

    for node in nodes:
        if max_nodes is not None and processed >= max_nodes:
            break
        edges = _edges_for(node.get("id", ""), graph)
        if len(edges["in"]) < min_incoming_edges:
            continue

        if with_neighbor_context:
            text = graphify_node_to_text(node, graph)
        else:
            text = _classification_text(node)
        pipeline_result = run_pipeline(text, ont)
        confidences = _node_confidences(node.get("id", ""), graph)
        evidence = confidence_to_evidence_strength(confidences)

        decisions[pipeline_result.get("decision", "UNKNOWN")] += 1
        mechanisms[pipeline_result["knowledge"].get("mechanism", "unknown")] += 1

        results.append(
            {
                "node_id": node.get("id"),
                "label": node.get("label"),
                "file_type": node.get("file_type"),
                "source_file": node.get("source_file"),
                "graphify_confidences": confidences,
                "graphify_evidence_strength": evidence,
                "neuro_os_decision": pipeline_result.get("decision"),
                "neuro_os_mechanism": pipeline_result["knowledge"].get("mechanism"),
                "neuro_os_true_score": pipeline_result["true_validation"]["scores"]["TRUE"],
                "synthesized_text": text,
            }
        )
        processed += 1

    return {
        "node_count": len(nodes),
        "processed": processed,
        "summary": {
            "decisions": dict(decisions),
            "mechanisms": dict(mechanisms),
        },
        "results": results,
    }


__all__ = [
    "load_graph",
    "graphify_node_to_text",
    "confidence_to_evidence_strength",
    "process_graphify_graph",
]
