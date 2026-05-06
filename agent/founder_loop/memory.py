"""
``memory.py`` — write tick rows to a JSONL registry, read them back,
compute the night-summary metrics.

Registry row shape (one line per tick):

```
{
  "kind": "tick",
  "timestamp": "...",
  "state": {...},        # FounderState dump
  "forecasted": {...},   # ForecastedState dump
  "tank": {...},         # TankState dump
  "action": {...},       # ControlAction dump (includes contract_check, diagnosis)
  "intent_flag": {...},  # IntentFlag dump (if computed)
  "row_id": "..."        # short uuid
}
```

Write path: ``append_registry_row`` → JSONL append.
Read path: ``read_registry`` → ordered list of dicts.

Nightly metrics:

* ``compute_mae(rows, day=...)`` — mean abs error of predicted-vs-actual
  distraction over a single day's rows.
* ``compute_contract_honor_rate(rows, day=...)`` — fraction of rows
  with ``contract_check.honored == True``.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent.founder_loop.state import (
    ControlAction,
    ForecastedState,
    FounderState,
    TankState,
)


def _row_dict(
    *,
    state: FounderState,
    forecasted: ForecastedState,
    tank: TankState,
    action: ControlAction,
    intent_flag: Optional[Any] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "kind": "tick",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "row_id": uuid.uuid4().hex[:12],
        "state": json.loads(state.model_dump_json()),
        "forecasted": json.loads(forecasted.model_dump_json()),
        "tank": json.loads(tank.model_dump_json()),
        "action": json.loads(action.model_dump_json()),
    }
    if intent_flag is not None:
        try:
            row["intent_flag"] = json.loads(intent_flag.model_dump_json())
        except AttributeError:
            row["intent_flag"] = dict(intent_flag) if isinstance(intent_flag, dict) else str(intent_flag)
    if extra:
        row.update(extra)
    return row


def append_registry_row(
    path: Union[str, Path],
    *,
    state: FounderState,
    forecasted: ForecastedState,
    tank: TankState,
    action: ControlAction,
    intent_flag: Optional[Any] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Append a tick row to the JSONL registry. Returns ``row_id``."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = _row_dict(
        state=state,
        forecasted=forecasted,
        tank=tank,
        action=action,
        intent_flag=intent_flag,
        extra=extra,
    )
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row["row_id"]


def read_registry(path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Read all tick rows from the JSONL registry, in append order."""
    p = Path(path)
    if not p.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def filter_by_day(rows: List[Dict[str, Any]], day: Union[str, date]) -> List[Dict[str, Any]]:
    """Filter rows to those whose ``state.timestamp`` is on ``day``."""
    if isinstance(day, date):
        day_str = day.isoformat()
    else:
        day_str = str(day)
    out: List[Dict[str, Any]] = []
    for row in rows:
        ts = (row.get("state") or {}).get("timestamp", "")
        if ts.startswith(day_str):
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# Nightly metrics
# ---------------------------------------------------------------------------


def compute_mae(rows: List[Dict[str, Any]]) -> Optional[float]:
    """Mean absolute error of predicted distraction vs actual.

    Returns ``None`` when no rows have both predicted and actual.
    """
    errors: List[float] = []
    for row in rows:
        forecasted = row.get("forecasted") or {}
        state = row.get("state") or {}
        predicted = forecasted.get("predicted_distraction_min")
        actual = state.get("distraction_minutes_last_hour")
        if predicted is None or actual is None:
            continue
        errors.append(abs(float(predicted) - float(actual)))
    if not errors:
        return None
    return sum(errors) / len(errors)


def compute_contract_honor_rate(rows: List[Dict[str, Any]]) -> Optional[float]:
    """Fraction of rows where ``action.contract_check.honored == True``.

    Returns ``None`` when no rows. Range [0.0, 1.0].
    """
    if not rows:
        return None
    honored = 0
    counted = 0
    for row in rows:
        action = row.get("action") or {}
        check = action.get("contract_check") or {}
        if "honored" not in check:
            continue
        counted += 1
        if check["honored"]:
            honored += 1
    if counted == 0:
        return None
    return honored / counted


def compute_entertainment_usage_min(rows: List[Dict[str, Any]]) -> float:
    """Total entertainment minutes consumed across the given rows.

    Sums ``payload.duration_min`` for every ``unlock_entertainment`` op
    regardless of whether the contract was honored — the goal is the raw
    usage figure, not a compliance one. Honor information lives on
    ``compute_contract_honor_rate``.
    """
    minutes = 0.0
    for row in rows:
        action = row.get("action") or {}
        if action.get("op") != "unlock_entertainment":
            continue
        payload = action.get("payload") or {}
        try:
            minutes += float(payload.get("duration_min", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
    return minutes


def compute_sublimation_success_rate(rows: List[Dict[str, Any]]) -> Optional[float]:
    """Fraction of ``propose_constructive_expression`` ops that 'stuck'.

    A proposal is considered to have stuck when no later row in the same
    list contains an ``unlock_entertainment`` op with
    ``contract_check.honored=False`` (a threshold or ration violation).
    The intuition: the constructive alternative was offered, and the
    user did NOT subsequently break the contract by consuming
    entertainment they hadn't earned.

    Returns ``None`` when no proposals fired in the window — there's no
    meaningful rate without a denominator.
    """
    proposal_indices: List[int] = []
    for i, row in enumerate(rows):
        action = row.get("action") or {}
        if action.get("op") == "propose_constructive_expression":
            proposal_indices.append(i)
    if not proposal_indices:
        return None

    def _has_violation_after(start_idx: int) -> bool:
        for j in range(start_idx + 1, len(rows)):
            a = rows[j].get("action") or {}
            if a.get("op") != "unlock_entertainment":
                continue
            check = a.get("contract_check") or {}
            if check.get("honored") is False:
                return True
        return False

    stuck = 0
    for idx in proposal_indices:
        if not _has_violation_after(idx):
            stuck += 1
    return stuck / len(proposal_indices)


__all__ = [
    "append_registry_row",
    "read_registry",
    "filter_by_day",
    "compute_mae",
    "compute_contract_honor_rate",
    "compute_entertainment_usage_min",
    "compute_sublimation_success_rate",
]
