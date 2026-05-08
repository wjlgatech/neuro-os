"""
DomainConfig + DomainApp factory for the investment vertical
(advisory-only v0).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.cross_vertical import write_note
from agent.domain_app import (
    ContractCheck,
    ControlActionBase,
    DomainApp,
    NightlySummaryBase,
)
from agent.domain_app.state import ControlOp
from agent.investment.catalog import INVESTMENT_CATALOG, InvestmentCatalog
from agent.investment.ontology import (
    BiasCheck,
    InvestmentContract,
    InvestmentPriority,
    PositionThesis,
)


class InvestmentConfig:
    """Concrete ``DomainConfig`` for the investment vertical."""

    vertical_name: str = "investment"
    primary_resource_label: str = "position edits"
    primary_metric_label: str = "calibration error"
    catalog: InvestmentCatalog = INVESTMENT_CATALOG

    def __init__(self, home: Optional[Path] = None) -> None:
        self.home_dir: Path = home or (Path.home() / ".neuro_os_investment")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _make_morning_hook(*, contract_path: Path) -> Any:
    def morning_ritual(
        *,
        priorities: List[InvestmentPriority],
        primary_resource_budget: int = 2,  # PRD: anti-emotional-trade cap
        threshold_pct: int = 90,
        when: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> InvestmentContract:
        when = when or datetime.now(timezone.utc)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        contract = InvestmentContract(
            date=when.date().isoformat(),
            primary_resource_budget=primary_resource_budget,
            threshold_pct=threshold_pct,
            signed_at=when,
            notes=notes,
            priorities=priorities,
        )
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        with contract_path.open("a", encoding="utf-8") as f:
            f.write(contract.model_dump_json() + "\n")
        return contract

    return morning_ritual


def _make_tick_hook(*, app: DomainApp, registry_path: Path) -> Any:
    def tick(
        *,
        intent: Optional[str] = None,
        now: Optional[datetime] = None,
        dry_run: bool = False,
        observed_failure_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        if observed_failure_mode is None:
            action = ControlActionBase(
                op="continue",
                rationale="No drift observed.",
                contract_check=ContractCheck(honored=True),
            )
        else:
            diagnosis = app.make_diagnosis(
                need=observed_failure_mode,
                confidence="high",
                reasoning=f"User reported: {observed_failure_mode}",
            )
            primary = diagnosis.options[0]
            op: ControlOp = "propose_constructive_expression"
            action = ControlActionBase(
                op=op,
                rationale=(
                    f"Investment drift '{observed_failure_mode}' detected. "
                    f"Suggest: {primary.action} ({primary.duration_min} min, "
                    f"+{primary.tank_credit_pct}% tank). ADVISORY-ONLY: no "
                    f"trade execution; user reads + decides."
                ),
                payload={
                    "primary_action": primary.action,
                    "duration_min": primary.duration_min,
                    "tank_credit_pct": primary.tank_credit_pct,
                    "advisory_only": True,
                },
                tank_delta=primary.tank_credit_pct,
                diagnosis=diagnosis,
                inverse_op="continue",
                contract_check=ContractCheck(honored=True),
            )

        if not dry_run:
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "ts": now.isoformat(),
                "row_id": _new_id(),
                "action": json.loads(action.model_dump_json()),
            }
            with registry_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")

        return {"action": json.loads(action.model_dump_json()), "ts": now.isoformat()}

    return tick


def _make_nightly_hook(*, registry_path: Path, home_dir: Path) -> Any:
    def nightly(
        *,
        day: Optional[datetime] = None,
    ) -> NightlySummaryBase:
        day = day or datetime.now(timezone.utc)
        date_iso = day.date().isoformat()
        rows: List[Dict[str, Any]] = []
        if registry_path.exists():
            with registry_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        today_rows = [
            r for r in rows
            if isinstance(r.get("ts"), str) and r["ts"].startswith(date_iso)
        ]
        actions = [r.get("action") or {} for r in today_rows]
        honored = sum(
            1 for a in actions
            if (a.get("contract_check") or {}).get("honored") is True
        )
        honor_rate = (honored / len(actions)) if actions else None

        # Calibration error from CalibrationRecord rows in home_dir.
        cal_dir = home_dir / "calibration_records"
        cal_today: List[Dict[str, Any]] = []
        if cal_dir.exists() and cal_dir.is_dir():
            for p in cal_dir.glob("*.json"):
                try:
                    rec = json.loads(p.read_text())
                except json.JSONDecodeError:
                    continue
                ts = rec.get("ts", "")
                if isinstance(ts, str) and ts.startswith(date_iso):
                    cal_today.append(rec)
        # Calibration error = mean(|confidence_score - actual_outcome|)
        # Map low/medium/high to 0.25/0.5/0.85.
        conf_to_score = {"low": 0.25, "medium": 0.5, "high": 0.85}
        if cal_today:
            errors = []
            for rec in cal_today:
                pred = conf_to_score.get(rec.get("predicted_confidence", ""), 0.5)
                actual = 1.0 if rec.get("thesis_still_valid") else 0.0
                errors.append(abs(pred - actual))
            calibration_error = sum(errors) / len(errors)
        else:
            calibration_error = None

        # Sublimation success rate
        propose_idxs = [
            i for i, a in enumerate(actions)
            if a.get("op") == "propose_constructive_expression"
        ]
        if propose_idxs:
            stuck = 0
            for idx in propose_idxs:
                later_violated = any(
                    (later.get("contract_check") or {}).get("honored") is False
                    for later in actions[idx + 1:]
                )
                if not later_violated:
                    stuck += 1
            success_rate = stuck / len(propose_idxs)
        else:
            success_rate = None

        # Bias-check count (extra metric)
        biases_dir = home_dir / "bias_checks"
        bias_count = 0
        if biases_dir.exists() and biases_dir.is_dir():
            bias_count = sum(1 for p in biases_dir.glob("*.json") if p.is_file())

        return NightlySummaryBase(
            date=date_iso,
            vertical="investment",
            primary_metric_today=calibration_error,
            primary_metric_label="calibration error",
            honor_rate_today=honor_rate,
            primary_resource_used_today=float(len([
                a for a in actions if a.get("op") != "continue"
            ])),
            primary_resource_label="position edits",
            primary_success_rate_today=success_rate,
            extra={
                "bias_checks_today": bias_count,
                "advisory_only": True,
            },
        )

    return nightly


def make_investment_app(
    *,
    home: Optional[Path] = None,
    registry_path: Optional[Path] = None,
    contract_path: Optional[Path] = None,
) -> DomainApp:
    """Build a ``DomainApp`` configured for the investment vertical
    (advisory-only)."""
    config = InvestmentConfig(home=home)
    home_dir = config.home_dir
    registry = registry_path or (home_dir / "registry.jsonl")
    contracts = contract_path or (home_dir / "contracts.jsonl")
    home_dir.mkdir(parents=True, exist_ok=True)

    app = DomainApp(
        config=config,
        registry_path=registry,
        contract_path=contracts,
    )
    app.hooks = {
        "morning_ritual": _make_morning_hook(contract_path=contracts),
        "tick": _make_tick_hook(app=app, registry_path=registry),
        "nightly": _make_nightly_hook(registry_path=registry, home_dir=home_dir),
    }
    return app


def write_position_thesis(
    *,
    thesis: PositionThesis,
    home: Optional[Path] = None,
    share_with: Optional[List[str]] = None,
) -> None:
    """Persist a PositionThesis locally + emit a cross_vertical note.

    Default: PRIVATE. Investor explicitly opts into sharing (e.g. with
    research for cross-domain mechanism transfer).
    """
    base = home or (Path.home() / ".neuro_os_investment")
    base.mkdir(parents=True, exist_ok=True)
    theses_dir = base / "position_theses"
    theses_dir.mkdir(parents=True, exist_ok=True)
    (theses_dir / f"{thesis.id}.json").write_text(thesis.model_dump_json(indent=2))
    write_note(
        source_vertical="investment",
        note_kind="position_thesis",
        payload=thesis.model_dump(mode="json"),
        visible_to=(["investment"] + list(share_with)) if share_with else None,
    )


def run_bias_check(
    *,
    thesis: PositionThesis,
    home: Optional[Path] = None,
) -> BiasCheck:
    """Run ``belief_os.check_decision_text`` against the thesis text.

    Reuses the shipped Belief-OS surface — does NOT re-implement bias
    detection. Returns a typed ``BiasCheck`` row that the nightly
    summary can count.
    """
    from agent.belief_os import check_decision_text

    text = f"{thesis.thesis}\n\nEvidence:\n" + "\n".join(thesis.evidence)
    gate = check_decision_text(text)
    base = home or (Path.home() / ".neuro_os_investment")
    biases_dir = base / "bias_checks"
    biases_dir.mkdir(parents=True, exist_ok=True)
    check = BiasCheck(
        id=_new_id(),
        ts=datetime.now(timezone.utc),
        thesis_id=thesis.id,
        mechanism=getattr(gate, "mechanism", None) or None,
        flagged=bool(getattr(gate, "flag_for_review", False)),
        reason=getattr(gate, "flag_reason", None),
    )
    (biases_dir / f"{check.id}.json").write_text(check.model_dump_json(indent=2))
    return check
