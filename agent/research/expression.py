"""
Expression layer for the research vertical (TRUE-E3's E3).

A compressed principle (one ``CompressedNode`` from
``compress.HierarchicalCompression``) gets instantiated in a chosen
modality (visual / musical / physical / organizational / game /
biological / narrative). The instantiation gets recorded here as an
``Expression``, then — separately — the user reflects on what the
expression *revealed* and writes that insight back. That second step
closes the compress→express→refine loop.

We deliberately do NOT integrate rendering tools (Tone.js for music,
p5.js for visuals, Isaac Sim for robotics, Stable Diffusion for images).
The ``content`` field stores text — a prompt, code, pseudocode,
markdown spec — and ``tool_hint`` names the renderer the user (or an
agent) can pipe it through. neuro-os is the schema-keeper; rendering
lives at the edges.

Storage: ``~/.neuro_os_research/expressions/<expression_id>.json``
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Literal

from agent.research.compress import (
    HierarchicalCompression,
    read_compression,
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


EXPRESSION_MODALITIES: Tuple[str, ...] = (
    "visual",
    "musical",
    "physical",
    "organizational",
    "game",
    "biological",
    "narrative",
)

ExpressionModality = Literal[
    "visual",
    "musical",
    "physical",
    "organizational",
    "game",
    "biological",
    "narrative",
]


class Expression(BaseModel):
    """One expression of a compressed principle in a chosen modality.

    Frozen. The ``reveal`` operation produces a new file (same id) with
    ``reveals`` and ``feeds_back_to_node_id`` filled in — we don't
    mutate; we re-write atomically. Old content is replaced on disk
    because expressions are interpretive snapshots, not append-only
    history (the compression + the source paper are the audit trail).
    """

    model_config = ConfigDict(frozen=True)

    expression_id: str = Field(min_length=1, max_length=64)
    created_at: datetime

    # Source — what compressed node is this an expression of?
    compression_id: str = Field(min_length=1, max_length=64)
    source_node_id: str = Field(min_length=1, max_length=64)

    # The expression itself
    modality: ExpressionModality
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    tool_hint: Optional[str] = Field(default=None, max_length=200)

    # The feedback loop (filled in by `reveal_expression`)
    reveals: Optional[str] = Field(default=None, max_length=2000)
    feeds_back_to_node_id: Optional[str] = Field(default=None, max_length=64)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def expressions_dir(home: Optional[Path] = None) -> Path:
    base = home if home is not None else Path.home() / ".neuro_os_research"
    d = base / "expressions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_expression_id() -> str:
    return f"exp-{uuid.uuid4().hex[:10]}"


def _write_expression(
    expression: Expression,
    *,
    home: Optional[Path] = None,
) -> Path:
    """Atomic-write an expression to its canonical path."""
    path = expressions_dir(home) / f"{expression.expression_id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(expression.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def read_expression(
    expression_id: str,
    *,
    home: Optional[Path] = None,
) -> Expression:
    path = expressions_dir(home) / f"{expression_id}.json"
    return Expression.model_validate_json(path.read_text(encoding="utf-8"))


def list_expressions(
    *,
    home: Optional[Path] = None,
    modality: Optional[str] = None,
    compression_id: Optional[str] = None,
    source_node_id: Optional[str] = None,
    limit: int = 200,
) -> List[Expression]:
    """Newest-first list with optional filters. Invalid files are
    silently skipped (defensive read)."""
    d = expressions_dir(home)
    paths = sorted(
        d.glob("exp-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out: List[Expression] = []
    for p in paths:
        if len(out) >= limit:
            break
        try:
            e = Expression.model_validate_json(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if modality and e.modality != modality:
            continue
        if compression_id and e.compression_id != compression_id:
            continue
        if source_node_id and e.source_node_id != source_node_id:
            continue
        out.append(e)
    return out


# ---------------------------------------------------------------------------
# Operations — record (compress→express) and reveal (express→refine)
# ---------------------------------------------------------------------------


def record_expression(
    *,
    compression_id: str,
    source_node_id: str,
    modality: str,
    title: str,
    content: str,
    tool_hint: Optional[str] = None,
    home: Optional[Path] = None,
) -> Expression:
    """Record a new expression. Validates that the compression exists
    and that ``source_node_id`` is one of its nodes (any level)."""
    if modality not in EXPRESSION_MODALITIES:
        raise ValueError(
            f"modality must be one of {EXPRESSION_MODALITIES}, got {modality!r}"
        )
    compression = read_compression(compression_id, home=home)
    if not _node_exists(compression, source_node_id):
        raise ValueError(
            f"source_node_id {source_node_id!r} not found in compression "
            f"{compression_id} (checked L0, L1, L2)"
        )
    expression = Expression(
        expression_id=new_expression_id(),
        created_at=datetime.now(timezone.utc),
        compression_id=compression_id,
        source_node_id=source_node_id,
        modality=modality,  # type: ignore[arg-type]  # validated above
        title=title,
        content=content,
        tool_hint=tool_hint,
    )
    _write_expression(expression, home=home)
    return expression


def reveal_expression(
    *,
    expression_id: str,
    reveals: str,
    feeds_back_to_node_id: Optional[str] = None,
    home: Optional[Path] = None,
) -> Expression:
    """Close the feedback loop: record what the expression revealed.

    If ``feeds_back_to_node_id`` is set, it must be a node in the same
    compression as the source. Returns the updated Expression and
    rewrites the file atomically."""
    if not reveals or not reveals.strip():
        raise ValueError("reveals must be a non-empty string")
    existing = read_expression(expression_id, home=home)
    if feeds_back_to_node_id is not None:
        compression = read_compression(existing.compression_id, home=home)
        if not _node_exists(compression, feeds_back_to_node_id):
            raise ValueError(
                f"feeds_back_to_node_id {feeds_back_to_node_id!r} not in "
                f"compression {existing.compression_id}"
            )
    updated = existing.model_copy(update={
        "reveals": reveals.strip(),
        "feeds_back_to_node_id": feeds_back_to_node_id,
    })
    _write_expression(updated, home=home)
    return updated


def _node_exists(
    compression: HierarchicalCompression,
    node_id: str,
) -> bool:
    """True if any of L0/L1/L2 has the given node_id."""
    for tier in (
        compression.level_0_nodes,
        compression.level_1_nodes,
        compression.level_2_nodes,
    ):
        for node in tier:
            if node.node_id == node_id:
                return True
    return False


__all__ = [
    "EXPRESSION_MODALITIES",
    "Expression",
    "expressions_dir",
    "new_expression_id",
    "read_expression",
    "list_expressions",
    "record_expression",
    "reveal_expression",
]
