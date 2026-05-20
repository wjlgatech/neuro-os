"""
Tests for the expression layer (``agent/research/expression.py``).

Each test seeds a compression via the real compress module, then
exercises record / reveal / list against it. tmp_path keeps the test's
home directory isolated.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agent.research.compress import (
    compress_from_synthesis,
    write_compression,
)
from agent.research.expression import (
    EXPRESSION_MODALITIES,
    Expression,
    list_expressions,
    read_expression,
    record_expression,
    reveal_expression,
)
from agent.research.synthesis import MechanismCluster, SynthesisRun


def _seed_compression(tmp_path):
    """Build + persist a small compression for tests to express against."""
    cluster = MechanismCluster(
        cluster_id="c1",
        label="Replay buffer",
        mechanism_summary="Selective rehearsal of past experience prevents forgetting.",
        member_card_ids=("card-1", "card-2"),
    )
    run = SynthesisRun(
        run_id="syn-001",
        generated_at=datetime.now(timezone.utc),
        window_days=30,
        min_cluster_size=2,
        method="fallback-heuristic",
        framework_name="(none)",
        input_card_count=2,
        clusters=(cluster,),
        unclustered_card_ids=(),
    )
    compression = compress_from_synthesis(run)
    write_compression(compression, home=tmp_path)
    return compression


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


def test_expression_is_frozen(tmp_path):
    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    e = record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="narrative",
        title="x",
        content="y",
        home=tmp_path,
    )
    with pytest.raises(ValidationError):
        e.title = "mutated"  # type: ignore[misc]


def test_modality_must_be_in_allowlist():
    assert "narrative" in EXPRESSION_MODALITIES
    assert "musical" in EXPRESSION_MODALITIES
    assert len(EXPRESSION_MODALITIES) == 7
    # Schema-level rejection of unknown modality
    with pytest.raises(ValidationError):
        Expression(
            expression_id="exp-1",
            created_at=datetime.now(timezone.utc),
            compression_id="cmp-1",
            source_node_id="l0-00",
            modality="taste",  # type: ignore[arg-type]
            title="x",
            content="y",
        )


# ---------------------------------------------------------------------------
# record_expression
# ---------------------------------------------------------------------------


def test_record_expression_round_trip(tmp_path):
    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    e = record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="narrative",
        title="The librarian who forgets selectively",
        content="A short story: every night the library burns the day's "
                "newest books unless a small flame in the wall has read them.",
        tool_hint="markdown",
        home=tmp_path,
    )
    assert e.expression_id.startswith("exp-")
    assert e.modality == "narrative"
    assert e.reveals is None
    loaded = read_expression(e.expression_id, home=tmp_path)
    assert loaded.expression_id == e.expression_id
    assert loaded.content.startswith("A short story")


def test_record_expression_rejects_unknown_modality(tmp_path):
    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    with pytest.raises(ValueError, match="modality"):
        record_expression(
            compression_id=compression.compression_id,
            source_node_id=l0.node_id,
            modality="sonic",
            title="x",
            content="y",
            home=tmp_path,
        )


def test_record_expression_rejects_missing_compression(tmp_path):
    with pytest.raises(FileNotFoundError):
        record_expression(
            compression_id="cmp-does-not-exist",
            source_node_id="l0-00",
            modality="narrative",
            title="x",
            content="y",
            home=tmp_path,
        )


def test_record_expression_rejects_unknown_source_node(tmp_path):
    compression = _seed_compression(tmp_path)
    with pytest.raises(ValueError, match="not found in compression"):
        record_expression(
            compression_id=compression.compression_id,
            source_node_id="l0-fakenode",
            modality="narrative",
            title="x",
            content="y",
            home=tmp_path,
        )


def test_record_expression_accepts_any_level(tmp_path):
    """L0, L1, and L2 nodes are all valid expression targets."""
    compression = _seed_compression(tmp_path)
    for target in (
        compression.level_0_nodes[0].node_id,
        compression.level_1_nodes[0].node_id,
        compression.level_2_nodes[0].node_id,
    ):
        e = record_expression(
            compression_id=compression.compression_id,
            source_node_id=target,
            modality="narrative",
            title=f"expression of {target}",
            content="content",
            home=tmp_path,
        )
        assert e.source_node_id == target


# ---------------------------------------------------------------------------
# reveal_expression — the feedback loop
# ---------------------------------------------------------------------------


def test_reveal_expression_updates_in_place(tmp_path):
    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    e = record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="narrative",
        title="x",
        content="y",
        home=tmp_path,
    )
    revealed = reveal_expression(
        expression_id=e.expression_id,
        reveals="Replay needs emotional safety to function in human teams.",
        feeds_back_to_node_id=l0.node_id,
        home=tmp_path,
    )
    assert revealed.expression_id == e.expression_id, (
        "reveal must update in place, not create a new expression id"
    )
    assert "emotional safety" in (revealed.reveals or "")
    assert revealed.feeds_back_to_node_id == l0.node_id

    loaded = read_expression(e.expression_id, home=tmp_path)
    assert loaded.reveals == revealed.reveals


def test_reveal_expression_rejects_empty_insight(tmp_path):
    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    e = record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="narrative",
        title="x",
        content="y",
        home=tmp_path,
    )
    with pytest.raises(ValueError, match="non-empty"):
        reveal_expression(
            expression_id=e.expression_id,
            reveals="   ",
            home=tmp_path,
        )


def test_reveal_expression_validates_feedback_target(tmp_path):
    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    e = record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="narrative",
        title="x",
        content="y",
        home=tmp_path,
    )
    with pytest.raises(ValueError, match="not in compression"):
        reveal_expression(
            expression_id=e.expression_id,
            reveals="some insight",
            feeds_back_to_node_id="l0-fakefeedback",
            home=tmp_path,
        )


# ---------------------------------------------------------------------------
# list_expressions — filtering + ordering
# ---------------------------------------------------------------------------


def test_list_expressions_newest_first(tmp_path):
    import time

    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    e1 = record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="narrative",
        title="first",
        content="c1",
        home=tmp_path,
    )
    time.sleep(0.02)
    e2 = record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="musical",
        title="second",
        content="c2",
        home=tmp_path,
    )
    listed = list_expressions(home=tmp_path)
    assert [x.expression_id for x in listed] == [e2.expression_id, e1.expression_id]


def test_list_expressions_filters_by_modality(tmp_path):
    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="narrative",
        title="n",
        content="c",
        home=tmp_path,
    )
    record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="musical",
        title="m",
        content="c",
        home=tmp_path,
    )
    only_musical = list_expressions(home=tmp_path, modality="musical")
    assert len(only_musical) == 1
    assert only_musical[0].modality == "musical"


def test_list_expressions_filters_by_compression_id(tmp_path):
    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="narrative",
        title="x",
        content="y",
        home=tmp_path,
    )
    listed_match = list_expressions(home=tmp_path, compression_id=compression.compression_id)
    listed_miss = list_expressions(home=tmp_path, compression_id="cmp-other")
    assert len(listed_match) == 1
    assert len(listed_miss) == 0


# ---------------------------------------------------------------------------
# Soft delete + restore (Fix 9 from design audit)
# ---------------------------------------------------------------------------


def test_soft_delete_moves_to_trash(tmp_path):
    from agent.research.expression import soft_delete_expression, trash_dir

    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    e = record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="narrative",
        title="x",
        content="y",
        home=tmp_path,
    )
    trash_path = soft_delete_expression(e.expression_id, home=tmp_path)
    assert trash_path.exists()
    assert trash_path.parent == trash_dir(home=tmp_path)
    # list_expressions must no longer return it
    assert list_expressions(home=tmp_path) == []


def test_restore_undoes_soft_delete(tmp_path):
    from agent.research.expression import restore_expression, soft_delete_expression

    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    e = record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="narrative",
        title="x",
        content="y",
        home=tmp_path,
    )
    soft_delete_expression(e.expression_id, home=tmp_path)
    restored = restore_expression(e.expression_id, home=tmp_path)
    assert restored.exists()
    # list_expressions must return it again
    listed = list_expressions(home=tmp_path)
    assert len(listed) == 1 and listed[0].expression_id == e.expression_id


def test_soft_delete_unknown_raises(tmp_path):
    from agent.research.expression import soft_delete_expression

    with pytest.raises(FileNotFoundError):
        soft_delete_expression("exp-fake", home=tmp_path)


def test_restore_when_not_in_trash_raises(tmp_path):
    from agent.research.expression import restore_expression

    with pytest.raises(FileNotFoundError):
        restore_expression("exp-fake", home=tmp_path)


def test_delete_then_restore_preserves_content(tmp_path):
    from agent.research.expression import (
        read_expression,
        restore_expression,
        soft_delete_expression,
    )

    compression = _seed_compression(tmp_path)
    l0 = compression.level_0_nodes[0]
    e = record_expression(
        compression_id=compression.compression_id,
        source_node_id=l0.node_id,
        modality="narrative",
        title="round-trip survivor",
        content="exact bytes must survive",
        home=tmp_path,
    )
    soft_delete_expression(e.expression_id, home=tmp_path)
    restore_expression(e.expression_id, home=tmp_path)
    loaded = read_expression(e.expression_id, home=tmp_path)
    assert loaded.title == "round-trip survivor"
    assert loaded.content == "exact bytes must survive"
