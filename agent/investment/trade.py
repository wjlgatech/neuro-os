"""
Trade journal (advisory-only).

⚠️ CRITICAL: this module is a **post-decision journal**, not a
broker integration. Calling ``write_trade_log`` does NOT route an
order; it records what the user is planning to do (or has already
done) so the dashboard can compute calibration over time.

The discipline gate: every trade is logged with ``win_prob``,
``assignment_prob``, and ``max_loss`` at decision time. When realized
outcomes are recorded later (future ``TradeOutcome`` schema, parked
in the plan doc), the dashboard can compute calibration error per
``(strategy, sleeve)`` slice and surface where the user's edge is /
isn't.

v0 is options-focused: strategy enum covers premium-collecting
positions (CSP, CC, credit spreads, condors) where the discipline
gate matters most. ``other`` is the escape hatch.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from agent.investment.ontology import Sleeve


TradeStrategy = Literal[
    "cash_secured_put",
    "covered_call",
    "short_call_spread",
    "short_put_spread",
    "iron_condor",
    "other",
]


def _investment_home(home: Optional[Path]) -> Path:
    return home or (Path.home() / ".neuro_os_investment")


def _trades_dir(home: Optional[Path]) -> Path:
    return _investment_home(home) / "trades"


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class TradeLog(BaseModel):
    """One trade-journal entry.

    Frozen — once written, you log a NEW entry; you don't mutate the
    original. (Realized-outcome data lives in a future TradeOutcome
    schema that references the trade by id, not in this row.)
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    ts: datetime
    strategy: TradeStrategy
    ticker: str = Field(
        min_length=1,
        max_length=12,
        description="Underlying ticker, e.g. 'NVDA'.",
    )
    underlying_price: float = Field(
        gt=0.0,
        description="Underlying price at decision time.",
    )
    expiry: date
    strikes: List[float] = Field(
        min_length=1,
        max_length=4,
        description="One strike for CSP/CC; 2 for verticals; 4 for "
                    "iron condors.",
    )
    premium: float = Field(
        gt=0.0,
        description="Net credit received in USD. v0 is credit-only.",
    )
    max_loss: float = Field(
        gt=0.0,
        description="Max dollar loss if the trade goes against you "
                    "to the worst breakeven.",
    )
    win_prob: float = Field(
        ge=0.0,
        le=1.0,
        description="User's pre-trade probability that the position "
                    "expires worthless / closes profitable.",
    )
    assignment_prob: float = Field(
        ge=0.0,
        le=1.0,
        description="User's pre-trade probability of assignment "
                    "(short options).",
    )
    thesis_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Link to a PositionThesis if filed.",
    )
    sleeve: Optional[Sleeve] = Field(
        default=None,
        description="Mega-trend bucket. Mirrors PositionThesis.sleeve "
                    "when no thesis is linked.",
    )
    notes: Optional[str] = Field(default=None, max_length=400)


def write_trade_log(
    trade: TradeLog,
    *,
    home: Optional[Path] = None,
) -> Path:
    """Persist ``trade`` to ``<home>/trades/<id>.json``. Returns the path.

    Does NOT route an order anywhere. This is a journal.
    """
    d = _trades_dir(home)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{trade.id}.json"
    path.write_text(trade.model_dump_json(indent=2))
    return path


def iter_trade_logs(
    *,
    home: Optional[Path] = None,
    window_days: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Iterator[TradeLog]:
    """Yield every trade in ``<home>/trades/``. If ``window_days`` is
    set, restrict to trades whose ``ts`` is within ``now - window_days``.

    Malformed JSON files are skipped (logged-but-not-raised). The
    dashboard treats this as a read-only audit surface; corrupted
    rows must not break the rollup.
    """
    d = _trades_dir(home)
    if not d.exists():
        return
    cutoff: Optional[datetime] = None
    if window_days is not None:
        anchor = now or datetime.now(timezone.utc)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        cutoff = anchor - timedelta(days=window_days)
    for path in sorted(d.glob("*.json")):
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
            trade = TradeLog.model_validate(body)
        except (json.JSONDecodeError, OSError, ValueError):
            continue
        if cutoff is not None:
            ts = trade.ts
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
        yield trade


def make_trade_log(
    *,
    strategy: TradeStrategy,
    ticker: str,
    underlying_price: float,
    expiry: date,
    strikes: List[float],
    premium: float,
    max_loss: float,
    win_prob: float,
    assignment_prob: float,
    thesis_id: Optional[str] = None,
    sleeve: Optional[Sleeve] = None,
    notes: Optional[str] = None,
    ts: Optional[datetime] = None,
    id: Optional[str] = None,
) -> TradeLog:
    """Convenience builder — fills ``id`` and ``ts`` if absent."""
    return TradeLog(
        id=id or _new_id(),
        ts=ts or datetime.now(timezone.utc),
        strategy=strategy,
        ticker=ticker,
        underlying_price=underlying_price,
        expiry=expiry,
        strikes=strikes,
        premium=premium,
        max_loss=max_loss,
        win_prob=win_prob,
        assignment_prob=assignment_prob,
        thesis_id=thesis_id,
        sleeve=sleeve,
        notes=notes,
    )


__all__ = [
    "TradeStrategy",
    "TradeLog",
    "write_trade_log",
    "iter_trade_logs",
    "make_trade_log",
]
