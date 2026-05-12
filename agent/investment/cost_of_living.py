"""
Cost-of-living tracker + Phase-1 income gap.

The user's Phase-1 goal is "stop relying on the 9-to-5 to cover Bay
Area living cost (~$12-14k/mo)." That's an income-vs-expense gap
metric. Two ways the number gets into neuro-os:

  1. **Direct set:** ``CostOfLivingProfile(monthly_target=14000, …)``
     written via ``invest cost-of-living set --monthly-target 14000``.
     Stored at ``~/.neuro_os_investment/cost_of_living.json``.
  2. **Read from money-os:** the user's money-os plugin maintains a
     `profile/financial-identity.md`. We do a best-effort regex parse
     of that file for a monthly-cost line. **No hard dependency** —
     if the file doesn't exist or can't be parsed, the user falls
     back to direct set.

Income gap math is intentionally simple: ``gap = target - monthly_net
income``. Negative gap = covered. The dashboard surfaces the gap as a
single number + a per-month trend (last 6 months of options-income
realized PNL).
"""
from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# Regex for parsing a monthly cost from money-os's
# profile/financial-identity.md. Best-effort — patterns this matches:
#   "Monthly expenses: $14,000"
#   "Monthly burn: $12k"
#   "Cost of living: $13,500/mo"
#   "monthly_cost: 14000"
# The user's actual format may differ; if so, direct-set is the answer.
_MONEY_OS_COST_PATTERNS = [
    # "$14,000" or "$14000" or "$14k" near a "monthly" keyword
    re.compile(
        r"(?i)(?:monthly|month|burn|cost of living|living cost|expenses)[^\n]{0,40}?"
        r"\$?\s*([\d,]+)\s*([kKmM])?",
    ),
    # "monthly_cost: 14000" — yaml-ish front matter form
    re.compile(
        r"(?im)^\s*(?:monthly_cost|monthly_expenses|cost_of_living)\s*[:=]\s*"
        r"\$?\s*([\d,]+)\s*([kKmM])?",
    ),
]


class CostOfLivingProfile(BaseModel):
    """The current cost-of-living target. Frozen — overwriting is a
    new write event, not a mutation."""

    model_config = ConfigDict(frozen=True)

    monthly_target: float = Field(
        gt=0.0,
        description="Monthly dollar amount to cover (rent + food + "
                    "kids + healthcare + … — whatever the user counts "
                    "as 'replacing the 9-to-5'). NOT 'live extremely "
                    "frugally'; the realistic Bay Area number.",
    )
    region: Optional[str] = Field(default=None, max_length=80)
    breakdown: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional human-readable breakdown: 'rent 5000, "
                    "food 2000, …'. For audit; the math uses "
                    "monthly_target only.",
    )
    source: str = Field(
        default="direct",
        max_length=80,
        description="'direct' (user typed it), 'money_os_profile' (parsed "
                    "from money-os's profile/financial-identity.md), "
                    "or some custom string.",
    )
    written_at: datetime


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _investment_home(home: Optional[Path]) -> Path:
    return home or (Path.home() / ".neuro_os_investment")


def profile_path(home: Optional[Path] = None) -> Path:
    return _investment_home(home) / "cost_of_living.json"


def save_profile(
    profile: CostOfLivingProfile, *, home: Optional[Path] = None,
) -> Path:
    """Atomic write of the current profile. Overwrites the previous
    profile (single-row state, not a log)."""
    target = profile_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = profile.model_dump_json(indent=2)
    fd, tmp = tempfile.mkstemp(
        prefix=".cost_of_living.", suffix=".json.tmp", dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(tmp, target)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    return target


def load_profile(
    *, home: Optional[Path] = None,
) -> Optional[CostOfLivingProfile]:
    """Load the current profile, or None if not set."""
    p = profile_path(home)
    if not p.exists():
        return None
    try:
        return CostOfLivingProfile.model_validate_json(
            p.read_text(encoding="utf-8")
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Money-os profile bridge
# ---------------------------------------------------------------------------


def read_from_money_os_profile(
    profile_path_md: Path,
) -> Optional[CostOfLivingProfile]:
    """Best-effort parse of money-os's ``profile/financial-identity.md``
    for a monthly cost number. Returns None on any failure — the user
    falls back to direct-set.

    Heuristics applied: looks for "monthly" / "month" / "burn" / "cost
    of living" near a dollar amount, OR a yaml-ish front-matter line.
    Multipliers: 'k' → 1000.
    """
    if not profile_path_md.exists():
        return None
    try:
        body = profile_path_md.read_text(encoding="utf-8")
    except Exception:
        return None

    for pattern in _MONEY_OS_COST_PATTERNS:
        match = pattern.search(body)
        if not match:
            continue
        raw_number = match.group(1).replace(",", "")
        try:
            num = float(raw_number)
        except ValueError:
            continue
        suffix = (match.group(2) or "").lower()
        if suffix == "k":
            num *= 1_000
        elif suffix == "m":
            num *= 1_000_000
        if num <= 0.0:
            continue
        return CostOfLivingProfile(
            monthly_target=num,
            source="money_os_profile",
            breakdown=None,
            region=None,
            written_at=datetime.now(timezone.utc),
        )
    return None


# ---------------------------------------------------------------------------
# Derived signal — the Phase-1 metric
# ---------------------------------------------------------------------------


class IncomeGap(BaseModel):
    """Phase-1 income gap: how far is monthly net income from the
    target cost-of-living."""

    model_config = ConfigDict(frozen=True)

    target: float = Field(gt=0.0)
    monthly_net_income: float
    gap_dollars: float = Field(
        description="target - monthly_net_income. Positive = uncovered. "
                    "Negative = surplus.",
    )
    gap_pct: float = Field(
        description="gap_dollars / target. Useful as a single-number "
                    "headline (e.g. '32% uncovered').",
    )
    months_runway_remaining: Optional[float] = Field(
        default=None,
        description="If a savings_balance was supplied: how many months "
                    "of the gap that balance covers. None when no "
                    "balance was supplied.",
    )


def compute_income_gap(
    *,
    monthly_net_income: float,
    profile: CostOfLivingProfile,
    savings_balance: Optional[float] = None,
) -> IncomeGap:
    """Compute the income gap for one month.

    ``savings_balance`` (optional): when supplied, compute months of
    runway = balance / max(gap_dollars, 1). Negative gap → unlimited
    runway in this snapshot; we return None to keep the field honest.
    """
    gap_dollars = profile.monthly_target - monthly_net_income
    pct = gap_dollars / profile.monthly_target
    runway: Optional[float] = None
    if savings_balance is not None and gap_dollars > 0.0:
        runway = savings_balance / gap_dollars
    return IncomeGap(
        target=profile.monthly_target,
        monthly_net_income=monthly_net_income,
        gap_dollars=gap_dollars,
        gap_pct=pct,
        months_runway_remaining=runway,
    )


__all__ = [
    "CostOfLivingProfile",
    "IncomeGap",
    "profile_path",
    "save_profile",
    "load_profile",
    "read_from_money_os_profile",
    "compute_income_gap",
]
