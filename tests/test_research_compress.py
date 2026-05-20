"""
Tests for the 3-level hierarchical compression layer
(``agent/research/compress.py``).

Strategy: hand-build SynthesisRun fixtures (cheap, deterministic, no LLM
calls) and verify the compression algorithm produces the expected
hierarchy shape. Storage tests use ``tmp_path`` as the home dir to keep
fixtures isolated from a real ``~/.neuro_os_research``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

import pytest
from pydantic import ValidationError

from agent.research.compress import (
    CompressedNode,
    HierarchicalCompression,
    compress_from_synthesis,
    compress_latest_synthesis,
    list_compressions,
    read_compression,
    write_compression,
)
from agent.research.synthesis import MechanismCluster, SynthesisRun, write_synthesis_run


def _make_cluster(
    cluster_id: str,
    label: str,
    cards: Tuple[str, ...],
    axes: Tuple[str, ...] = (),
) -> MechanismCluster:
    return MechanismCluster(
        cluster_id=cluster_id,
        label=label,
        mechanism_summary=f"summary of {label}",
        member_card_ids=cards,
        framework_axes_touched=axes,
    )


def _make_run(
    *,
    run_id: str = "syn-test001",
    clusters: List[MechanismCluster],
) -> SynthesisRun:
    return SynthesisRun(
        run_id=run_id,
        generated_at=datetime.now(timezone.utc),
        window_days=30,
        min_cluster_size=2,
        method="fallback-heuristic",
        framework_name="(none)",
        input_card_count=sum(len(c.member_card_ids) for c in clusters),
        clusters=tuple(clusters),
        unclustered_card_ids=(),
    )


# ---------------------------------------------------------------------------
# Algorithm: shape of the produced hierarchy
# ---------------------------------------------------------------------------


def test_compress_with_no_clusters_raises():
    """A synthesis run with zero clusters has nothing to compress."""
    run = SynthesisRun(
        run_id="syn-empty",
        generated_at=datetime.now(timezone.utc),
        window_days=30,
        min_cluster_size=2,
        method="fallback-heuristic",
        framework_name="(none)",
        input_card_count=0,
        clusters=(),
        unclustered_card_ids=(),
    )
    with pytest.raises(ValueError, match="no clusters"):
        compress_from_synthesis(run)


def test_compress_one_cluster_produces_minimal_hierarchy():
    """Single cluster: L0=1, L1=1, L2=N(cards)."""
    run = _make_run(clusters=[
        _make_cluster("c1", "Replay buffer", ("card-1", "card-2", "card-3")),
    ])
    c = compress_from_synthesis(run)
    assert len(c.level_0_nodes) == 1
    assert len(c.level_1_nodes) == 1
    assert len(c.level_2_nodes) == 3
    assert c.level_0_nodes[0].level == 0
    assert c.level_1_nodes[0].level == 1
    assert all(n.level == 2 for n in c.level_2_nodes)


def test_compress_three_clusters_one_per_level_0_node():
    """≤5 clusters → each cluster maps 1:1 to an L0 node (no rollup)."""
    run = _make_run(clusters=[
        _make_cluster("c1", "Replay", ("card-1", "card-2")),
        _make_cluster("c2", "Distillation", ("card-3", "card-4")),
        _make_cluster("c3", "Sparsity", ("card-5", "card-6")),
    ])
    c = compress_from_synthesis(run)
    assert len(c.level_0_nodes) == 3
    assert len(c.level_1_nodes) == 3
    assert len(c.level_2_nodes) == 6
    # Each L0 references exactly one L1
    for l0 in c.level_0_nodes:
        assert len(l0.references) == 1
        assert l0.references[0].startswith("l1-")


def test_compress_seven_clusters_collapses_to_five_level_0():
    """>5 clusters → grouped to ≤5 L0 nodes."""
    run = _make_run(clusters=[
        _make_cluster(f"c{i}", f"Cluster {i}", (f"card-{i}-a", f"card-{i}-b"))
        for i in range(7)
    ])
    c = compress_from_synthesis(run)
    assert len(c.level_0_nodes) <= 5, (
        f"L0 should be ≤5, got {len(c.level_0_nodes)}"
    )
    assert len(c.level_1_nodes) == 7
    # Every L1 must have a parent in L0
    l0_ids = {n.node_id for n in c.level_0_nodes}
    for l1 in c.level_1_nodes:
        assert l1.parent_id in l0_ids, (
            f"L1 {l1.node_id} has parent {l1.parent_id!r} not in L0 set"
        )


def test_compress_groups_by_framework_axes_when_oversized():
    """Clusters sharing framework_axes_touched should group together."""
    # 8 clusters, two share axis 'plasticity', two share 'distillation',
    # four share 'memory' (so framework grouping yields 3 bins, ≤5).
    run = _make_run(clusters=[
        _make_cluster("c1", "L1-A", ("k1",), axes=("plasticity",)),
        _make_cluster("c2", "L1-B", ("k2",), axes=("plasticity",)),
        _make_cluster("c3", "L1-C", ("k3",), axes=("distillation",)),
        _make_cluster("c4", "L1-D", ("k4",), axes=("distillation",)),
        _make_cluster("c5", "L1-E", ("k5",), axes=("memory",)),
        _make_cluster("c6", "L1-F", ("k6",), axes=("memory",)),
        _make_cluster("c7", "L1-G", ("k7",), axes=("memory",)),
        _make_cluster("c8", "L1-H", ("k8",), axes=("memory",)),
    ])
    c = compress_from_synthesis(run)
    # Three axis-based groups → 3 L0 nodes
    assert len(c.level_0_nodes) == 3


def test_level_2_nodes_reference_their_parent_l1():
    """Every L2 node must point at the L1 that owns its card_id."""
    run = _make_run(clusters=[
        _make_cluster("c1", "A", ("card-x", "card-y")),
        _make_cluster("c2", "B", ("card-z",)),
    ])
    c = compress_from_synthesis(run)
    l2_parents = {n.label: n.parent_id for n in c.level_2_nodes}
    assert l2_parents["card-x"] == "l1-c1"
    assert l2_parents["card-y"] == "l1-c1"
    assert l2_parents["card-z"] == "l1-c2"


def test_compress_idempotent_structure():
    """Same synthesis input → same node IDs (modulo compression_id)
    and identical edge structure."""
    run = _make_run(clusters=[
        _make_cluster("c1", "A", ("k1", "k2")),
        _make_cluster("c2", "B", ("k3",)),
    ])
    c1 = compress_from_synthesis(run)
    c2 = compress_from_synthesis(run)

    # compression_id and created_at differ; structure is identical
    def _strip_meta(c: HierarchicalCompression):
        return (
            tuple((n.node_id, n.label, n.references) for n in c.level_0_nodes),
            tuple((n.node_id, n.label, n.parent_id, n.references) for n in c.level_1_nodes),
            tuple((n.node_id, n.label, n.parent_id) for n in c.level_2_nodes),
        )

    assert _strip_meta(c1) == _strip_meta(c2)


def test_level_0_max_size_invariant_holds_at_boundary():
    """Exactly 5 clusters → 5 L0 nodes (no rollup needed)."""
    run = _make_run(clusters=[
        _make_cluster(f"c{i}", f"L{i}", (f"k{i}",))
        for i in range(5)
    ])
    c = compress_from_synthesis(run)
    assert len(c.level_0_nodes) == 5


def test_compress_rejects_zero_max_level_0():
    run = _make_run(clusters=[_make_cluster("c1", "A", ("k1",))])
    with pytest.raises(ValueError, match="max_level_0"):
        compress_from_synthesis(run, max_level_0=0)


# ---------------------------------------------------------------------------
# Schema: frozen + bounded
# ---------------------------------------------------------------------------


def test_compressed_node_is_frozen():
    n = CompressedNode(
        node_id="l0-00",
        level=0,
        label="x",
        one_sentence="y",
        parent_id=None,
        references=("a",),
    )
    with pytest.raises(ValidationError):
        n.label = "mutated"  # type: ignore[misc]


def test_hierarchical_compression_rejects_six_level_0_nodes():
    """Schema-level bound: max 5 L0 nodes."""
    nodes = tuple(
        CompressedNode(node_id=f"l0-{i}", level=0, label="x", one_sentence="y")
        for i in range(6)
    )
    l1 = (
        CompressedNode(node_id="l1-1", level=1, label="x", one_sentence="y"),
    )
    with pytest.raises(ValidationError):
        HierarchicalCompression(
            compression_id="cmp-test",
            created_at=datetime.now(timezone.utc),
            source_synthesis_id="syn-1",
            level_0_nodes=nodes,
            level_1_nodes=l1,
            level_2_nodes=(),
        )


# ---------------------------------------------------------------------------
# Storage: write, read, list
# ---------------------------------------------------------------------------


def test_write_and_read_round_trip(tmp_path):
    run = _make_run(clusters=[_make_cluster("c1", "A", ("k1",))])
    c = compress_from_synthesis(run)
    path = write_compression(c, home=tmp_path)
    assert path.exists()
    loaded = read_compression(c.compression_id, home=tmp_path)
    assert loaded.compression_id == c.compression_id
    assert loaded.source_synthesis_id == c.source_synthesis_id


def test_list_compressions_returns_newest_first(tmp_path):
    import time

    run = _make_run(clusters=[_make_cluster("c1", "A", ("k1",))])
    c1 = compress_from_synthesis(run)
    write_compression(c1, home=tmp_path)
    time.sleep(0.02)
    c2 = compress_from_synthesis(run)
    write_compression(c2, home=tmp_path)

    listed = list_compressions(home=tmp_path)
    assert len(listed) == 2
    assert listed[0].compression_id == c2.compression_id


def test_compress_latest_synthesis_loads_from_disk(tmp_path):
    """End-to-end disk: write a synthesis run, then compress-latest."""
    run = _make_run(
        run_id="syn-disk-001",
        clusters=[_make_cluster("c1", "A", ("k1", "k2"))],
    )
    write_synthesis_run(run, home=tmp_path)
    c = compress_latest_synthesis(home=tmp_path)
    assert c.source_synthesis_id == "syn-disk-001"
    # The compression should also be on disk
    listed = list_compressions(home=tmp_path)
    assert len(listed) == 1
    assert listed[0].compression_id == c.compression_id


def test_compress_latest_synthesis_raises_when_no_synthesis(tmp_path):
    with pytest.raises(ValueError, match="no synthesis runs"):
        compress_latest_synthesis(home=tmp_path)
