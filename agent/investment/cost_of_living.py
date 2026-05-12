"""
Cost-of-living target (advisory-only).

A single-current-target Pydantic record persisted at
``~/.neuro_os_investment/cost_of_living.json``. Sets the headline
anchor the dashboard uses to compute a premium-run-rate coverage %.

v0 keeps history out of scope — latest write wins. When the user
revises the target a second time, the file is overwritten. A future
``cost_of_living/history.jsonl`` is parked in the plan doc.

⚠️ PRIVATE: this number is sensitive personal info. No cross_vertical
note is emitted on write. Other verticals cannot read it.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def _investment_home(home: Optional[Path]) -> Path:
    return home or (Path.home() / ".neuro_os_investment")


class CostOfLivingTarget(BaseModel):
    """The user's monthly cash target.

    Frozen — overwriting means writing a NEW record to the same path,
    not mutating the existing object.
    """

    model_config = ConfigDict(frozen=True)

    monthly_target: float = Field(
        gt=0.0,
        le=1_000_000.0,
        description="Monthly cash target in USD.",
    )
    region: str = Field(
        min_length=1,
        max_length=80,
        description="Free-text region label, e.g. 'Bay Area'.",
    )
    ts: datetime
    notes: Optional[str] = Field(default=None, max_length=400)


def write_cost_of_living_target(
    target: CostOfLivingTarget,
    *,
    home: Optional[Path] = None,
) -> Path:
    """Overwrite ``cost_of_living.json`` with ``target``.

    Returns the path written to (for test assertions).
    """
    base = _investment_home(home)
    base.mkdir(parents=True, exist_ok=True)
    path = base / "cost_of_living.json"
    path.write_text(target.model_dump_json(indent=2))
    return path


def read_cost_of_living_target(
    *,
    home: Optional[Path] = None,
) -> Optional[CostOfLivingTarget]:
    """Return the current target, or None if no file exists yet.

    Malformed files raise — silent fallback would mask a real bug.
    """
    path = _investment_home(home) / "cost_of_living.json"
    if not path.exists():
        return None
    body = json.loads(path.read_text(encoding="utf-8"))
    return CostOfLivingTarget.model_validate(body)


def make_cost_of_living_target(
    *,
    monthly_target: float,
    region: str,
    notes: Optional[str] = None,
    ts: Optional[datetime] = None,
) -> CostOfLivingTarget:
    """Convenience builder — fills ``ts`` with now-UTC if absent."""
    return CostOfLivingTarget(
        monthly_target=monthly_target,
        region=region,
        notes=notes,
        ts=ts or datetime.now(timezone.utc),
    )


__all__ = [
    "CostOfLivingTarget",
    "write_cost_of_living_target",
    "read_cost_of_living_target",
    "make_cost_of_living_target",
]
