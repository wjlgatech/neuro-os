"""
``contract.py`` — the Ulysses pact.

Yesterday-self signs the daily contract via ``bind_morning_contract()``.
Today-self is bound by it: every ``ControlAction`` is checked against
the contract via ``check_contract()`` and a ``ContractCheck`` is
attached to the action. Overrides are not silently denied — they are
logged with a ``violation_type``, and the tank takes the abuse-tax
debit. Agency is preserved; visibility is mandatory.

I/O: contracts are persisted as JSONL (one line per day) at the
``contract_path`` provided to the loop. Most-recent-by-date wins on
load.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

from agent.founder_loop.priorities import warn_if_over_capacity
from agent.founder_loop.state import (
    AbuseTax,
    Contract,
    ContractCheck,
    ControlAction,
    Priority,
    TankState,
)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_contract(contract: Contract, path: Union[str, Path]) -> None:
    """Append a contract to the JSONL store at ``path``.

    One line per day. Re-signing the same date appends a new line; the
    loader returns the last one for that date.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(contract.model_dump_json() + "\n")


def load_contract_for_date(
    path: Union[str, Path], date: str
) -> Optional[Contract]:
    """Return the most recent contract for ``date`` (ISO YYYY-MM-DD)."""
    p = Path(path)
    if not p.exists():
        return None
    found: Optional[Contract] = None
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if data.get("date") == date:
                found = Contract.model_validate(data)
    return found


def load_latest_contract(path: Union[str, Path]) -> Optional[Contract]:
    """Return the most recent contract regardless of date.

    Used by ``loop.tick()`` when running mid-day — the latest signed
    contract is the active one until tomorrow's morning ritual replaces it.
    """
    p = Path(path)
    if not p.exists():
        return None
    last: Optional[Contract] = None
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            last = Contract.model_validate_json(line)
    return last


# ---------------------------------------------------------------------------
# Morning binding
# ---------------------------------------------------------------------------


def bind_morning_contract(
    *,
    priorities: List[Priority],
    entertainment_ration_min: int,
    threshold_pct: int = 90,
    abuse_tax: Optional[AbuseTax] = None,
    pre_authorized_blocks: Optional[List[str]] = None,
    notes: Optional[str] = None,
    when: Optional[datetime] = None,
    save_to: Optional[Union[str, Path]] = None,
) -> Contract:
    """Build + (optionally) persist today's contract.

    Returns a list of warning strings via ``contract.notes`` when the
    user is over the soft priority cap; the contract is still produced
    so today-self can knowingly accept the over-ambition.
    """
    when = when or datetime.now(timezone.utc)
    today = when.date().isoformat()
    warning = warn_if_over_capacity(priorities)
    final_notes = notes
    if warning:
        final_notes = (notes + "\n\n" + warning) if notes else warning

    contract = Contract(
        date=today,
        priorities=list(priorities),
        entertainment_ration_min=entertainment_ration_min,
        threshold_pct=threshold_pct,
        abuse_tax=abuse_tax or AbuseTax(),
        pre_authorized_blocks=list(pre_authorized_blocks or []),
        signed_at=when,
        notes=final_notes,
    )
    if save_to is not None:
        save_contract(contract, save_to)
    return contract


# ---------------------------------------------------------------------------
# Per-action contract check
# ---------------------------------------------------------------------------


def check_contract(
    op: str,
    payload: dict,
    *,
    contract: Optional[Contract],
    tank: TankState,
) -> ContractCheck:
    """Verdict on whether ``op + payload`` honors the active ``contract``.

    Rules:

    * Ops that don't touch the reward economy (``continue``, ``rest``,
      ``escalate_to_human``, ``replan``, ``force_intent_capture``,
      ``start_25min_sprint``, ``shorten_current_task``,
      ``propose_constructive_expression``) always honor (no contract
      surface to violate).
    * ``unlock_entertainment`` requires ``tank.status ==
      'threshold_within_ration'``. Status ``below_threshold`` →
      ``threshold_violation``. Status ``threshold_over_ration`` →
      ``ration_violation``.
    * ``notify_ration_used`` is itself a contract-aware op; honors.
    * ``swap_priority`` always honors (the swap is logged as the cost).
    * ``block_url`` requires the target to be in
      ``contract.pre_authorized_blocks`` — otherwise
      ``block_target_not_authorized``.
    """
    if contract is None:
        # No contract bound yet — treat as a free-day. Honor everything;
        # the user is in pre-contract debugging mode.
        return ContractCheck(honored=True, notes="no contract bound")

    if op == "unlock_entertainment":
        if tank.status == "below_threshold":
            return ContractCheck(
                honored=False,
                violation_type="threshold_violation",
                notes=(
                    f"tank at {tank.percent:.1f}% < threshold "
                    f"{tank.threshold}%; entertainment is not yet earned"
                ),
            )
        if tank.status == "threshold_over_ration":
            return ContractCheck(
                honored=False,
                violation_type="ration_violation",
                notes=(
                    f"daily ration ({contract.entertainment_ration_min}min) "
                    "is exhausted; further entertainment debits at the "
                    f"abuse-tax rate "
                    f"({contract.abuse_tax.ration_violation_multiplier}×)"
                ),
            )
        return ContractCheck(honored=True)

    if op == "block_url":
        target = (payload or {}).get("target") or (payload or {}).get("url")
        if target is None:
            return ContractCheck(
                honored=False,
                violation_type="block_target_not_authorized",
                notes="block_url op missing 'target'/'url' in payload",
            )
        for pattern in contract.pre_authorized_blocks:
            if pattern in target:
                return ContractCheck(honored=True)
        return ContractCheck(
            honored=False,
            violation_type="block_target_not_authorized",
            notes=(
                f"target '{target}' is not in pre_authorized_blocks "
                f"{contract.pre_authorized_blocks}; today-self can override "
                "but the override is logged"
            ),
        )

    return ContractCheck(honored=True)


# ---------------------------------------------------------------------------
# Helpers used elsewhere
# ---------------------------------------------------------------------------


def evidenced_priority_weight(contract: Contract) -> float:
    """Sum of ``weight`` over priorities currently marked ``evidenced``.

    Used by ``reward_ledger.compute_tank()`` — credits are earned per
    weight-unit of evidenced priority.
    """
    return float(sum(p.weight for p in contract.priorities if p.status == "evidenced"))


def total_priority_weight(contract: Contract) -> float:
    """Sum of all priority weights — the denominator for the tank %."""
    return float(sum(p.weight for p in contract.priorities)) or 1.0


__all__ = [
    "save_contract",
    "load_contract_for_date",
    "load_latest_contract",
    "bind_morning_contract",
    "check_contract",
    "evidenced_priority_weight",
    "total_priority_weight",
]
