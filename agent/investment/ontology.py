"""
Investment-vertical Pydantic schemas (advisory-only v0).

Four primitives:

* **PositionThesis** — every position has one. Carries thesis,
  evidence, invalidation condition, expected timeline. Required at
  every position-edit (PRD SMART #1: 100% thesis coverage).
* **BiasCheck** — output of running ``belief_os.check_decision_text``
  on a thesis. Logs the mechanism if any (survivorship_bias,
  falsifiability, etc.).
* **CalibrationRecord** — per-thesis confidence over time. Confidence
  reuses the substrate's ``Confidence`` enum (low/medium/high) — NO
  parallel 0-1 float scale (Phase 0 PRD revision).
* **InvestmentContract** — daily contract; primary_resource_budget
  here counts max position-edits per day.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from agent.domain_app.state import Confidence, DailyContractBase


# Investment-specific evidence vocabulary. Designed for advisory-only
# v0: no execution-shaped evidence types ('trade_executed', etc.).
EVIDENCE_TYPE = Literal[
    "thesis_documented",     # PositionThesis filed
    "evidence_added",        # new evidence row attached to a thesis
    "thesis_invalidated",    # invalidation condition triggered, thesis killed
    "calibration_logged",    # CalibrationRecord entry for the day
    "bias_check_run",        # belief_os.check_decision_text output captured
    "reflection_completed",  # nightly review entry filed
]


# Position-side enum. ``read_only`` is the v0 default — no execution.
PositionSide = Literal["read_only", "long_simulated", "short_simulated"]


# Mega-trend allocation buckets. Optional tag on PositionThesis +
# TradeLog so the dashboard can roll up exposure by sleeve. Untagged
# rows bucket under "untagged" in the dashboard view.
Sleeve = Literal["ai", "energy", "biotech", "macro", "crypto", "other"]


class PositionThesis(BaseModel):
    """One per position. Required at every position edit.

    Frozen — once filed, you log NEW theses; you don't mutate the
    original. Killing a thesis (invalidation triggered) writes a new
    row with ``status='invalidated'`` and references the prior id.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    ts: datetime
    instrument: str = Field(
        min_length=1,
        max_length=80,
        description="Ticker / asset id. e.g. 'AAPL', 'BTC-USD'.",
    )
    side: PositionSide = "read_only"
    thesis: str = Field(
        min_length=10,
        max_length=2000,
        description="One paragraph: WHY this position should exist.",
    )
    evidence: List[str] = Field(
        min_length=1,
        max_length=20,
        description="Concrete evidence supporting the thesis. Each row "
                    "is a citable claim.",
    )
    invalidation_condition: str = Field(
        min_length=1,
        max_length=500,
        description="The single condition under which the thesis dies. "
                    "Required (PRD: 100% theses must have explicit "
                    "falsification).",
    )
    expected_timeline: str = Field(
        min_length=1,
        max_length=200,
        description="When the thesis should pay off / be checkable. "
                    "Free text but bounded.",
    )
    confidence: Confidence
    """Substrate-shared low/medium/high enum. NO 0-1 float scale."""

    status: Literal["active", "invalidated", "graduated"] = "active"
    invalidation_reason: Optional[str] = Field(default=None, max_length=500)
    parent_thesis_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="When this thesis replaces/refines an earlier one.",
    )
    sleeve: Optional[Sleeve] = Field(
        default=None,
        description="Mega-trend allocation bucket. Optional; untagged "
                    "theses bucket under 'untagged' in the dashboard.",
    )


class BiasCheck(BaseModel):
    """The output of running ``belief_os.check_decision_text`` on a
    thesis. Captures whether a known reasoning failure mode (Bayesian
    updating gap, survivorship bias, falsifiability gap, etc.) was
    flagged.

    The investment vertical does NOT re-implement bias detection — it
    consumes belief_os and persists the result here.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    ts: datetime
    thesis_id: str = Field(min_length=1, max_length=64)
    mechanism: Optional[str] = Field(
        default=None,
        max_length=80,
        description="The Belief-OS mechanism flagged, e.g. "
                    "'survivorship_bias', 'falsifiability_gap'. "
                    "None when no flag fired.",
    )
    flagged: bool
    reason: Optional[str] = Field(default=None, max_length=600)


class CalibrationRecord(BaseModel):
    """Daily entry: predicted-confidence vs realized-thesis-stability.

    Lets the nightly summary compute Calibration Error =
    |confidence_predicted - thesis_still_valid|.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    ts: datetime
    thesis_id: str = Field(min_length=1, max_length=64)
    predicted_confidence: Confidence
    thesis_still_valid: bool
    notes: Optional[str] = Field(default=None, max_length=400)


class InvestmentPriority(BaseModel):
    """One priority on the daily investment contract.

    The PRD's "thesis documentation" SMART = every priority is a
    documentation/calibration/reflection task tied to a specific
    instrument. Substrate enforces the priority list shape via
    DailyContractBase override.
    """

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, max_length=200)
    evidence_type: EVIDENCE_TYPE
    evidence_target: str = Field(min_length=1, max_length=200)
    weight: int = Field(ge=1, le=3)
    instrument: Optional[str] = Field(
        default=None,
        max_length=80,
        description="Optional: the instrument this priority operates on.",
    )
    status: Literal["pending", "in_progress", "evidenced", "abandoned"] = "pending"
    evidenced_at: Optional[datetime] = None


class InvestmentContract(DailyContractBase):
    """Investment's daily contract. ``primary_resource_budget`` counts
    max position-edits-per-day (default 2 — anti-emotional-trading
    guard from PRD).
    """

    priorities: List[InvestmentPriority] = Field(min_length=1, max_length=5)
    advisory_only: Literal[True] = Field(
        default=True,
        description="HARD INVARIANT: v0 is advisory-only. NEVER set False "
                    "without an explicit broker-integration v1 PR.",
    )
