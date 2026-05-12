"""
Phase-1 substrate for the investment vertical: options-income tracking.

Background: the user's "$12-14k/mo steady income" goal is an income
problem, not a wealth problem. The wheel + cash-secured puts + covered
calls family of strategies CAN produce this on $400-600k of capital
when run with discipline — and routinely fails when the operator hides
losses in "I'll roll it" indefinitely or chases premium without
respecting expected value.

money-os (the user's other Claude plugin) does not handle options. This
module fills that gap.

Design choices:

* **Frozen Pydantic at every boundary.** Each option trade is one
  immutable row; "closing a trade" writes a new row referencing the
  parent. No mutation.
* **expected_value is a first-class field, win_rate is decorative.**
  The most common failure mode in retail options income is conflating
  high win-rate with profitability. The schema makes you fill in
  expected_value at log time; the dashboard surfaces both, with
  sample-size guards on win-rate (< 20 trades → "noise").
* **No live broker integration.** Like the rest of the investment
  vertical, this is advisory-only. The user records trades; the
  system surfaces the math. Real execution is out of scope (v0
  anti-goal).
* **Strategy-typed.** OptionStrategy is a Literal, not free-text, so
  the dashboard can roll up per-strategy. New strategies extend the
  Literal in a follow-up.

Storage: JSONL at ``~/.neuro_os_investment/option_trades.jsonl``.
Append-only; closing or rolling a trade writes a new row pointing at
the original via ``parent_trade_id``.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


OptionStrategy = Literal[
    "cash_secured_put",
    "covered_call",
    "wheel",
    "credit_spread",
    "iron_condor",
    "naked",
    "other",
]

OptionOutcome = Literal["open", "won", "lost", "assigned", "rolled"]


# Sample-size threshold below which win-rate is treated as noise. 20 is
# a commonly-cited "first signal" threshold for option-income discipline;
# below it, observed win-rate barely separates from random.
WINRATE_MIN_SAMPLE_SIZE = 20


class OptionTrade(BaseModel):
    """One option trade — frozen audit row. Closing / rolling a trade
    writes a NEW row pointing at this one via ``parent_trade_id``.
    """

    model_config = ConfigDict(frozen=True)

    trade_id: str = Field(min_length=1, max_length=64)
    opened_at: datetime
    strategy: OptionStrategy
    ticker: str = Field(min_length=1, max_length=12)
    underlying_price_at_open: float = Field(gt=0.0)
    expiry: str = Field(
        min_length=10,
        max_length=10,
        description="ISO date YYYY-MM-DD of the option expiration.",
    )
    # Strikes vary by strategy. Cash-secured put: one strike.
    # Credit spread: two strikes. Iron condor: four. We use a list to
    # cover all of them; the position of each strike is strategy-defined.
    strikes: List[float] = Field(min_length=1, max_length=4)
    contracts: int = Field(ge=1, le=10_000)
    premium_received: float = Field(
        ge=0.0,
        description="Net credit received at open (per contract × contracts). "
                    "Debit strategies have premium_received < max_profit.",
    )
    max_loss: float = Field(
        ge=0.0,
        description="Worst-case capital at risk if everything goes wrong "
                    "(strike-to-zero for short puts, spread-width for "
                    "spreads, etc.). REQUIRED — the discipline gate.",
    )
    expected_value: float = Field(
        description="Probability-weighted expected P&L at open. "
                    "= win_p × premium_received − loss_p × max_loss. "
                    "Negative EVs are valid (the system records, doesn't "
                    "veto); the dashboard surfaces them.",
    )
    assignment_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Probability of assignment at open. Optional — most "
                    "broker / data feeds expose this as delta for ATM-ish "
                    "strikes. Used by the dashboard's wheel-readiness "
                    "signal.",
    )
    outcome: OptionOutcome = "open"
    closed_at: Optional[datetime] = None
    realized_pnl: Optional[float] = Field(
        default=None,
        description="Set when outcome != 'open'. Negative = loss. The "
                    "row stays frozen; closing writes a NEW row with a "
                    "realized_pnl value, referencing this one as parent.",
    )
    parent_trade_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="When a row is a CLOSE / ROLL of an earlier trade, "
                    "the trade_id of the earlier row.",
    )
    notes: Optional[str] = Field(default=None, max_length=600)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _investment_home(home: Optional[Path]) -> Path:
    return home or (Path.home() / ".neuro_os_investment")


def option_trades_path(home: Optional[Path] = None) -> Path:
    return _investment_home(home) / "option_trades.jsonl"


def write_trade(
    trade: OptionTrade, *, home: Optional[Path] = None,
) -> Path:
    """Append one trade to the JSONL log. Atomic os.write+fsync."""
    target = option_trades_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = (trade.model_dump_json() + "\n").encode("utf-8")
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        written = 0
        while written < len(line):
            n = os.write(fd, line[written:])
            if n <= 0:
                raise OSError("os.write returned 0 — disk full?")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)
    return target


def read_trades(
    *, home: Optional[Path] = None,
    strategy: Optional[OptionStrategy] = None,
    ticker: Optional[str] = None,
    outcome: Optional[OptionOutcome] = None,
    since: Optional[datetime] = None,
) -> List[OptionTrade]:
    """Read all trades, optionally filtered. Oldest first."""
    target = option_trades_path(home)
    if not target.exists():
        return []
    out: List[OptionTrade] = []
    with target.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                trade = OptionTrade.model_validate_json(line)
            except Exception:
                continue
            if strategy and trade.strategy != strategy:
                continue
            if ticker and trade.ticker != ticker:
                continue
            if outcome and trade.outcome != outcome:
                continue
            if since and trade.opened_at < since:
                continue
            out.append(trade)
    out.sort(key=lambda t: t.opened_at)
    return out


# ---------------------------------------------------------------------------
# Derived signals
# ---------------------------------------------------------------------------


def compute_expected_value(
    *,
    win_probability: float,
    premium_received: float,
    max_loss: float,
) -> float:
    """Probability-weighted expected P&L for one trade.

    EV = P(win) × premium − P(loss) × max_loss
       = P(win) × premium − (1 − P(win)) × max_loss

    Returns a signed dollar amount per trade unit (the caller scales by
    number of contracts).
    """
    if not 0.0 <= win_probability <= 1.0:
        raise ValueError(
            f"win_probability must be in [0, 1] (got {win_probability!r})"
        )
    return (
        win_probability * premium_received
        - (1.0 - win_probability) * max_loss
    )


class WinRateSummary(BaseModel):
    """Strategy-level win-rate with explicit sample-size guard."""

    model_config = ConfigDict(frozen=True)

    strategy: OptionStrategy
    closed_trades: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    assignments: int = Field(ge=0)
    win_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="None when sample size < WINRATE_MIN_SAMPLE_SIZE. "
                    "Below the threshold, win_rate is noise.",
    )
    realized_pnl_sum: float = 0.0


def compute_winrate(
    trades: List[OptionTrade], *, strategy: OptionStrategy,
) -> WinRateSummary:
    """Win-rate + realized-PNL rollup for one strategy. Below
    WINRATE_MIN_SAMPLE_SIZE closed trades, win_rate is None (the
    dashboard renders it as 'noise: < 20 trades')."""
    closed = [
        t for t in trades
        if t.strategy == strategy
        and t.outcome in ("won", "lost", "assigned")
    ]
    wins = sum(1 for t in closed if t.outcome == "won")
    losses = sum(1 for t in closed if t.outcome == "lost")
    assignments = sum(1 for t in closed if t.outcome == "assigned")
    pnl_sum = sum(t.realized_pnl or 0.0 for t in closed)
    rate: Optional[float] = None
    if len(closed) >= WINRATE_MIN_SAMPLE_SIZE:
        # Assignment is neither a clean win nor a clean loss; we count
        # it as a separate bucket, and win_rate = wins / (wins + losses).
        denom = wins + losses
        rate = (wins / denom) if denom > 0 else None
    return WinRateSummary(
        strategy=strategy,
        closed_trades=len(closed),
        wins=wins,
        losses=losses,
        assignments=assignments,
        win_rate=rate,
        realized_pnl_sum=pnl_sum,
    )


class MonthlyPnL(BaseModel):
    """Monthly options-income rollup. The Phase-1 income metric."""

    model_config = ConfigDict(frozen=True)

    year_month: str = Field(
        min_length=7,
        max_length=7,
        description="ISO YYYY-MM.",
    )
    closed_trades: int = Field(ge=0)
    realized_pnl: float
    premium_received_open: float = Field(
        ge=0.0,
        description="Total premium on trades OPENED in this month "
                    "(not yet realized for trades still open).",
    )


def compute_monthly_pnl(
    trades: List[OptionTrade], *, year_month: str,
) -> MonthlyPnL:
    """Sum realized_pnl for trades CLOSED in the given month, plus
    open-month premium for trades OPENED in the month."""
    closed_in_month = [
        t for t in trades
        if t.closed_at
        and t.closed_at.strftime("%Y-%m") == year_month
        and t.outcome in ("won", "lost", "assigned", "rolled")
    ]
    opened_in_month = [
        t for t in trades
        if t.opened_at.strftime("%Y-%m") == year_month
    ]
    return MonthlyPnL(
        year_month=year_month,
        closed_trades=len(closed_in_month),
        realized_pnl=sum(t.realized_pnl or 0.0 for t in closed_in_month),
        premium_received_open=sum(t.premium_received for t in opened_in_month),
    )


def list_open_trades(
    *, home: Optional[Path] = None,
) -> List[OptionTrade]:
    """Open trades = rows with outcome == 'open' AND no later row
    references them as parent (i.e. not yet closed / rolled).
    """
    all_trades = read_trades(home=home)
    closed_parent_ids = {
        t.parent_trade_id for t in all_trades if t.parent_trade_id
    }
    return [
        t for t in all_trades
        if t.outcome == "open" and t.trade_id not in closed_parent_ids
    ]


def new_trade_id() -> str:
    """uuid-based id; mirrors the rest of neuro-os."""
    return f"opt-{uuid.uuid4().hex[:12]}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "OptionStrategy",
    "OptionOutcome",
    "WINRATE_MIN_SAMPLE_SIZE",
    "OptionTrade",
    "WinRateSummary",
    "MonthlyPnL",
    "option_trades_path",
    "write_trade",
    "read_trades",
    "compute_expected_value",
    "compute_winrate",
    "compute_monthly_pnl",
    "list_open_trades",
    "new_trade_id",
    "now_utc",
]
