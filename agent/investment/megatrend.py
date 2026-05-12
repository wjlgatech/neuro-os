"""
Phase-2 substrate: mega-trend sleeve balance + thesis-correct-rate.

Background: the user wants to invest in a basket of 6-7 mega trends
(AI / Crypto / Quantum / SynthBio / Space / Robotics / Energy storage).
The discipline that makes this work — vs being a list of feel-good
sector bets — is two things:

  1. **Sleeve balance:** track allocation per sleeve, surface
     concentration. A single sleeve > 40% is a warning sign; "I'm
     diversified across mega trends" while 70% of capital is in AI is
     not diversification.
  2. **Thesis-correct-rate:** count the fraction of theses whose
     invalidation_condition did NOT fire over a multi-month window. A
     mega-trend basket where most theses get invalidated isn't a
     mega-trend bet, it's a feel-good bet.

This module is pure aggregation over the existing PositionThesis rows
in ``agent/investment/ontology.py``. The new field — ``PositionThesis.
sleeve`` — is optional so existing rows back-compat.

money-os does NOT do this categorically; its profile markdown can
tag positions but doesn't roll up by sleeve. The neuro-os investment
dashboard adds this surface.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from agent.investment.ontology import MegaTrendSleeve, PositionThesis


# Sleeve concentration warning threshold. A sleeve holding > 40% of
# capital fires `single_sleeve_concentration` in the dashboard. 40% is
# arbitrary but defensible: above it, you're betting on one trend not
# a basket.
SLEEVE_CONCENTRATION_WARNING = 0.40


# "Other" bucket label for theses with sleeve=None (theses outside the
# 7-trend basket). Surfaced in the dashboard so the user sees how much
# capital is OUTSIDE the mega-trend thesis.
OTHER_BUCKET = "other"


class SleeveAllocation(BaseModel):
    """Per-sleeve allocation + thesis count + concentration flag."""

    model_config = ConfigDict(frozen=True)

    sleeve: str = Field(min_length=1, max_length=32)
    thesis_count: int = Field(ge=0)
    capital_fraction: float = Field(ge=0.0, le=1.0)
    over_concentration_warning: bool = False


class SleeveBalance(BaseModel):
    """The full balance snapshot — one entry per sleeve plus 'other'."""

    model_config = ConfigDict(frozen=True)

    allocations: List[SleeveAllocation] = Field(default_factory=list)
    sleeves_concentrated: List[str] = Field(default_factory=list)
    total_theses: int = Field(ge=0)


def compute_sleeve_balance(
    theses: List[PositionThesis],
    *,
    capital_weights: Optional[Dict[str, float]] = None,
) -> SleeveBalance:
    """Bucket theses by sleeve, compute capital fraction per sleeve.

    ``capital_weights``: optional dict mapping thesis_id → dollar
    allocation. If absent, every thesis is weighted equally (count
    of theses, not dollar capital). Equal-weight is the default
    because v0 doesn't track per-thesis dollar size (that would
    duplicate money-os's holdings.md).
    """
    if not theses:
        return SleeveBalance(allocations=[], sleeves_concentrated=[], total_theses=0)

    weights = capital_weights or {t.id: 1.0 for t in theses}
    total = sum(weights.get(t.id, 0.0) for t in theses)
    if total <= 0.0:
        return SleeveBalance(allocations=[], sleeves_concentrated=[], total_theses=len(theses))

    bucketed: Dict[str, Tuple[int, float]] = {}
    for t in theses:
        sleeve_label = str(t.sleeve) if t.sleeve else OTHER_BUCKET
        w = weights.get(t.id, 0.0)
        if sleeve_label in bucketed:
            count, agg_weight = bucketed[sleeve_label]
            bucketed[sleeve_label] = (count + 1, agg_weight + w)
        else:
            bucketed[sleeve_label] = (1, w)

    concentrated: List[str] = []
    allocations: List[SleeveAllocation] = []
    for sleeve_label, (count, agg) in sorted(bucketed.items()):
        frac = agg / total
        over = frac > SLEEVE_CONCENTRATION_WARNING
        if over:
            concentrated.append(sleeve_label)
        allocations.append(SleeveAllocation(
            sleeve=sleeve_label,
            thesis_count=count,
            capital_fraction=frac,
            over_concentration_warning=over,
        ))

    return SleeveBalance(
        allocations=allocations,
        sleeves_concentrated=concentrated,
        total_theses=len(theses),
    )


class ThesisCorrectRate(BaseModel):
    """Fraction of theses that did NOT get invalidated within the
    window. Surfaces whether the user's mega-trend thesis discipline
    is real.
    """

    model_config = ConfigDict(frozen=True)

    window_days: int = Field(ge=1, le=365)
    sleeve: Optional[str] = None
    total: int = Field(ge=0)
    invalidated: int = Field(ge=0)
    correct_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="None on empty samples. Caller decides what to do "
                    "(typically: render '—' when None).",
    )


def compute_thesis_correct_rate(
    theses: List[PositionThesis],
    *,
    window_days: int,
    now: Optional[datetime] = None,
    sleeve: Optional[MegaTrendSleeve] = None,
) -> ThesisCorrectRate:
    """Of theses FILED within the window, what fraction did NOT get
    invalidated? Optional sleeve filter.

    A thesis is 'correct' iff it's still ``active`` OR ``graduated``.
    'invalidated' is the failure signal.

    The metric is most useful with a long-enough window (90+ days) — a
    7-day window will mostly show 'still active' regardless of quality.
    """
    when = now or datetime.now(timezone.utc)
    cutoff = when - timedelta(days=window_days)
    in_window = [t for t in theses if t.ts >= cutoff]
    if sleeve is not None:
        in_window = [t for t in in_window if t.sleeve == sleeve]
    if not in_window:
        return ThesisCorrectRate(
            window_days=window_days,
            sleeve=str(sleeve) if sleeve else None,
            total=0,
            invalidated=0,
            correct_rate=None,
        )
    invalidated = sum(1 for t in in_window if t.status == "invalidated")
    rate = (len(in_window) - invalidated) / len(in_window)
    return ThesisCorrectRate(
        window_days=window_days,
        sleeve=str(sleeve) if sleeve else None,
        total=len(in_window),
        invalidated=invalidated,
        correct_rate=rate,
    )


__all__ = [
    "SLEEVE_CONCENTRATION_WARNING",
    "OTHER_BUCKET",
    "SleeveAllocation",
    "SleeveBalance",
    "ThesisCorrectRate",
    "compute_sleeve_balance",
    "compute_thesis_correct_rate",
]
