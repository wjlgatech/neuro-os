"""
Research-vertical: user-supplied framework.

The 3-layer Research OS asks every paper "where does this fit in YOUR
framework?". The substrate refuses to hard-code one framework (OEC, value
investing, founder rituals — these are all user-domain choices). Instead
this module loads a small, user-authored JSON file from
``~/.neuro_os_research/framework.json`` and exposes its axes to the LLM
extractor + Layer 2 synthesis + Layer 3 brief generator. If the file is
missing, ``load_framework`` returns ``EMPTY_FRAMEWORK`` and the framework
hooks become no-ops — the rest of the pipeline keeps working.

On-disk shape (JSON, hand-edited by the user):

    {
      "name": "OEC",
      "description": "Observation -> Evaluation -> Control -> Continual",
      "axes": [
        {"name": "Observation", "description": "What sensors / signals?"},
        {"name": "Evaluation",  "description": "What delta is detected?"},
        {"name": "Control",     "description": "What action is taken?"},
        {"name": "Continual",   "description": "What is learned over time?"}
      ],
      "signed_at": "2026-05-12T00:00:00+00:00"
    }

This is intentionally lightweight: no migration story, no versioning, no
LLM-managed framework. The user owns their framework; the substrate just
reads it.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FrameworkAxis(BaseModel):
    """One axis of the user's framework. Generic by design — the
    substrate never inspects ``name``; it just round-trips it."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=400)


class Framework(BaseModel):
    """The user's framework as a frozen Pydantic record. ``axes`` may be
    empty (which is exactly ``EMPTY_FRAMEWORK``) — the pipeline runs
    fine either way; framework-aware features just become no-ops."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=400)
    axes: List[FrameworkAxis] = Field(default_factory=list, max_length=12)
    signed_at: Optional[datetime] = None


EMPTY_FRAMEWORK = Framework(name="(none)", axes=[])


def framework_path(home: Optional[Path] = None) -> Path:
    base = home or (Path.home() / ".neuro_os_research")
    return base / "framework.json"


def load_framework(home: Optional[Path] = None) -> Framework:
    """Return the user's framework, or ``EMPTY_FRAMEWORK`` if missing.

    A malformed file is treated the same as missing — we'd rather the
    pipeline keep working than crash a daily ``research synthesize``
    run because of a stray comma. The user sees the empty framework in
    the dashboard and knows to fix the file.
    """
    path = framework_path(home)
    if not path.exists():
        return EMPTY_FRAMEWORK
    try:
        return Framework.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return EMPTY_FRAMEWORK


def save_framework(framework: Framework, *, home: Optional[Path] = None) -> Path:
    """Atomically write a Framework to ``framework_path(home)``."""
    target = framework_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = framework.model_dump_json(indent=2)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".framework.", suffix=".json.tmp", dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise
    return target


__all__ = [
    "FrameworkAxis",
    "Framework",
    "EMPTY_FRAMEWORK",
    "framework_path",
    "load_framework",
    "save_framework",
]
