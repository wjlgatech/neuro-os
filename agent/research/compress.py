"""
3-level hierarchical compression for the research vertical.

The Layer-2 synthesizer (``synthesis.py``) clusters MechanismCards by
mechanism. That gives one level of abstraction. TRUE-E3's living-knowledge
loop asks for *three* levels so an agent or human can query at any
granularity and walk between them:

  Level 0 — Core schema. 3-5 nodes. Highest abstraction. Each L0 node
            rolls up one or more L1 clusters.
  Level 1 — Decomposition. One node per MechanismCluster (≤30).
  Level 2 — Full detail. One node per accepted MechanismCard.

The hierarchy is FROZEN once written. A new synthesis run + a new
compression replaces nothing; old compressions stay on disk as audit
of how interpretation evolved over time.

Storage: ``~/.neuro_os_research/compressions/<compression_id>.json``

Why we don't pull in graphify or KG-Compression: the substrate is
``stdlib + pydantic + the existing synthesis output``. Anything richer
(graph-theoretic backbone extraction, LLM-driven re-summarization) is a
plug-in point, not a v0 requirement. The deterministic rollup here is
enough to validate the compress→express loop end-to-end.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Literal

from agent.research.synthesis import (
    MechanismCluster,
    SynthesisRun,
    list_synthesis_runs,
    read_synthesis_run,
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CompressedNode(BaseModel):
    """One node in the compressed hierarchy. Frozen."""

    model_config = ConfigDict(frozen=True)

    node_id: str = Field(min_length=1, max_length=64)
    level: Literal[0, 1, 2]
    label: str = Field(min_length=1, max_length=200)
    one_sentence: str = Field(min_length=1, max_length=600)
    parent_id: Optional[str] = Field(default=None, max_length=64)
    references: Tuple[str, ...] = Field(default_factory=tuple, max_length=200)


class HierarchicalCompression(BaseModel):
    """A 3-level snapshot built from one SynthesisRun. Frozen."""

    model_config = ConfigDict(frozen=True)

    compression_id: str = Field(min_length=1, max_length=64)
    created_at: datetime
    source_synthesis_id: str = Field(min_length=1, max_length=64)
    level_0_nodes: Tuple[CompressedNode, ...] = Field(min_length=1, max_length=5)
    level_1_nodes: Tuple[CompressedNode, ...] = Field(min_length=1, max_length=30)
    level_2_nodes: Tuple[CompressedNode, ...] = Field(default_factory=tuple)
    note: Optional[str] = Field(default=None, max_length=1000)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def compressions_dir(home: Optional[Path] = None) -> Path:
    base = home if home is not None else Path.home() / ".neuro_os_research"
    d = base / "compressions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_compression_id() -> str:
    return f"cmp-{uuid.uuid4().hex[:10]}"


def write_compression(
    compression: HierarchicalCompression,
    *,
    home: Optional[Path] = None,
) -> Path:
    """Atomic-write a compression to its canonical path."""
    path = compressions_dir(home) / f"{compression.compression_id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(compression.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def read_compression(
    compression_id: str,
    *,
    home: Optional[Path] = None,
) -> HierarchicalCompression:
    path = compressions_dir(home) / f"{compression_id}.json"
    return HierarchicalCompression.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def list_compressions(
    *,
    home: Optional[Path] = None,
    limit: int = 50,
) -> List[HierarchicalCompression]:
    d = compressions_dir(home)
    paths = sorted(
        d.glob("cmp-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out: List[HierarchicalCompression] = []
    for p in paths[:limit]:
        try:
            out.append(
                HierarchicalCompression.model_validate_json(
                    p.read_text(encoding="utf-8")
                )
            )
        except Exception:
            continue
    return out


def latest_compression(
    *,
    home: Optional[Path] = None,
) -> Optional[HierarchicalCompression]:
    runs = list_compressions(home=home, limit=1)
    return runs[0] if runs else None


# ---------------------------------------------------------------------------
# Compression algorithm
# ---------------------------------------------------------------------------


def compress_from_synthesis(
    run: SynthesisRun,
    *,
    max_level_0: int = 5,
) -> HierarchicalCompression:
    """Build a 3-level hierarchy from a synthesis run.

    Level 1: one CompressedNode per MechanismCluster (1:1).
    Level 2: one CompressedNode per unique member_card_id.
    Level 0: ≤max_level_0 nodes rolled up from L1 by framework-axes
             overlap, then smallest-pair merge until ≤max_level_0.

    Pure function — does not touch disk. Caller writes via
    ``write_compression`` if persistence is desired.
    """
    if not run.clusters:
        raise ValueError(
            f"synthesis run {run.run_id!r} has no clusters — nothing to compress"
        )
    if max_level_0 < 1:
        raise ValueError(f"max_level_0 must be ≥1, got {max_level_0}")

    # Level 1 — one node per cluster
    l1_nodes_unwired: List[CompressedNode] = []
    for cluster in run.clusters:
        l1_nodes_unwired.append(
            CompressedNode(
                node_id=f"l1-{cluster.cluster_id}",
                level=1,
                label=cluster.label[:200],
                one_sentence=cluster.mechanism_summary[:600],
                parent_id=None,
                references=tuple(cluster.member_card_ids),
            )
        )

    # Level 0 — group L1 clusters into ≤max_level_0 groups
    l0_groups = _group_clusters_to_l0(run.clusters, max_level_0)
    l0_nodes: List[CompressedNode] = []
    cluster_id_to_l0: Dict[str, str] = {}
    for group_idx, group in enumerate(l0_groups):
        l0_id = f"l0-{group_idx:02d}"
        l0_nodes.append(
            CompressedNode(
                node_id=l0_id,
                level=0,
                label=_l0_label_from_group(group)[:200],
                one_sentence=_l0_summary_from_group(group)[:600],
                parent_id=None,
                references=tuple(f"l1-{c.cluster_id}" for c in group),
            )
        )
        for c in group:
            cluster_id_to_l0[c.cluster_id] = l0_id

    # Wire L1 parents
    l1_nodes: List[CompressedNode] = []
    for cluster, node in zip(run.clusters, l1_nodes_unwired):
        parent = cluster_id_to_l0.get(cluster.cluster_id)
        l1_nodes.append(node.model_copy(update={"parent_id": parent}))

    # Level 2 — one node per unique card; parent is the first L1 that owns it
    card_to_parent: Dict[str, str] = {}
    for cluster in run.clusters:
        for card_id in cluster.member_card_ids:
            if card_id not in card_to_parent:
                card_to_parent[card_id] = f"l1-{cluster.cluster_id}"

    l2_nodes: List[CompressedNode] = []
    for card_id, parent_l1 in card_to_parent.items():
        l2_nodes.append(
            CompressedNode(
                node_id=f"l2-{card_id}",
                level=2,
                label=card_id[:200],
                one_sentence=f"Mechanism card {card_id} (look up via `research review` or proposals)"[:600],
                parent_id=parent_l1,
                references=(),
            )
        )

    return HierarchicalCompression(
        compression_id=new_compression_id(),
        created_at=datetime.now(timezone.utc),
        source_synthesis_id=run.run_id,
        level_0_nodes=tuple(l0_nodes),
        level_1_nodes=tuple(l1_nodes),
        level_2_nodes=tuple(l2_nodes),
        note=(
            f"Compressed from synthesis {run.run_id} — "
            f"{len(run.clusters)} clusters, {len(l2_nodes)} cards, "
            f"{len(l0_nodes)} L0 nodes."
        ),
    )


def compress_latest_synthesis(
    *,
    home: Optional[Path] = None,
    max_level_0: int = 5,
) -> HierarchicalCompression:
    """Convenience: load the most recent synthesis run, compress it,
    write the result to disk. Returns the persisted compression."""
    runs = list_synthesis_runs(home=home, limit=1)
    if not runs:
        raise ValueError(
            "no synthesis runs found — run `research synthesize` first"
        )
    compression = compress_from_synthesis(runs[0], max_level_0=max_level_0)
    write_compression(compression, home=home)
    return compression


def compress_synthesis_by_id(
    synthesis_id: str,
    *,
    home: Optional[Path] = None,
    max_level_0: int = 5,
) -> HierarchicalCompression:
    """Compress a specific synthesis run by id."""
    run = read_synthesis_run(synthesis_id, home=home)
    compression = compress_from_synthesis(run, max_level_0=max_level_0)
    write_compression(compression, home=home)
    return compression


# ---------------------------------------------------------------------------
# Helpers — Level 0 rollup
# ---------------------------------------------------------------------------


def _group_clusters_to_l0(
    clusters: Sequence[MechanismCluster],
    max_groups: int,
) -> List[List[MechanismCluster]]:
    """Bin clusters into ≤max_groups groups for L0 rollup.

    Strategy:
      1. If len(clusters) ≤ max_groups, each cluster gets its own group.
      2. Else group by overlapping framework_axes_touched (clusters that
         share any axis go in the same bin).
      3. If still >max_groups, repeatedly merge the two smallest groups
         until ≤max_groups remain.
    """
    if len(clusters) <= max_groups:
        return [[c] for c in clusters]

    # Build axis-key buckets
    axes_buckets: Dict[frozenset, List[MechanismCluster]] = {}
    for c in clusters:
        key = (
            frozenset(c.framework_axes_touched)
            if c.framework_axes_touched
            else frozenset({f"__solo__:{c.cluster_id}"})
        )
        axes_buckets.setdefault(key, []).append(c)

    groups: List[List[MechanismCluster]] = list(axes_buckets.values())

    while len(groups) > max_groups:
        groups.sort(key=len)
        merged = groups[0] + groups[1]
        groups = [merged] + groups[2:]

    return groups


def _l0_label_from_group(group: Sequence[MechanismCluster]) -> str:
    """Label for an L0 node summarizing its constituent L1 clusters."""
    if len(group) == 1:
        return group[0].label
    axes_sets = [
        set(c.framework_axes_touched or ())
        for c in group
        if c.framework_axes_touched
    ]
    if axes_sets:
        shared = set.intersection(*axes_sets) if len(axes_sets) > 1 else axes_sets[0]
        if shared:
            return f"{', '.join(sorted(shared))} ({len(group)} sub-clusters)"
    first_label = group[0].label[:60]
    return f"{first_label} + {len(group) - 1} related"


def _l0_summary_from_group(group: Sequence[MechanismCluster]) -> str:
    """One-sentence summary for an L0 node."""
    if len(group) == 1:
        return group[0].mechanism_summary
    parts = [c.mechanism_summary.split(".")[0][:100] for c in group[:3]]
    suffix = f" (+{len(group) - 3} more)" if len(group) > 3 else ""
    return " | ".join(parts) + suffix


__all__ = [
    "CompressedNode",
    "HierarchicalCompression",
    "compress_from_synthesis",
    "compress_latest_synthesis",
    "compress_synthesis_by_id",
    "compressions_dir",
    "new_compression_id",
    "write_compression",
    "read_compression",
    "list_compressions",
    "latest_compression",
]
