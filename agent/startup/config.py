"""
DomainConfig + DomainApp factory for the startup vertical.
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
from agent.startup.catalog import STARTUP_CATALOG, StartupCatalog
from agent.startup.ontology import (
    AudienceSignal,
    Bottleneck,
    StartupContract,
    StartupHypothesis,
    StartupPriority,
)


class StartupConfig:
    """Concrete ``DomainConfig`` for the startup vertical."""

    vertical_name: str = "startup"
    primary_resource_label: str = "thesis pivots"
    primary_metric_label: str = "strategic continuity score"
    catalog: StartupCatalog = STARTUP_CATALOG

    def __init__(self, home: Optional[Path] = None) -> None:
        self.home_dir: Path = home or (Path.home() / ".neuro_os_startup")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _make_morning_hook(*, contract_path: Path) -> Any:
    def morning_ritual(
        *,
        active_hypothesis_id: str,
        priorities: List[StartupPriority],
        primary_resource_budget: int = 0,  # default 0 thesis pivots/day
        threshold_pct: int = 90,
        when: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> StartupContract:
        when = when or datetime.now(timezone.utc)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        # Hard cap: thesis-pivots-per-day <= 1 (anti-idea-chaos guard).
        if primary_resource_budget > 1:
            raise ValueError(
                f"primary_resource_budget (thesis_pivots/day) is {primary_resource_budget}; "
                f"hard cap is 1. The PRD's 40-day-continuity bet is "
                f"meaningless if you preauthorize chaos."
            )
        contract = StartupContract(
            date=when.date().isoformat(),
            primary_resource_budget=primary_resource_budget,
            threshold_pct=threshold_pct,
            signed_at=when,
            notes=notes,
            priorities=priorities,
            active_hypothesis_id=active_hypothesis_id,
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
                    f"Founder drift '{observed_failure_mode}' detected. "
                    f"Suggest: {primary.action} ({primary.duration_min} min, "
                    f"+{primary.tank_credit_pct}% tank)."
                ),
                payload={
                    "primary_action": primary.action,
                    "duration_min": primary.duration_min,
                    "tank_credit_pct": primary.tank_credit_pct,
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

        # Strategic continuity = 1 - (kill_events_in_last_40d / 40).
        # Counted by reading hypotheses dir.
        hyp_dir = home_dir / "hypotheses"
        kill_count = 0
        if hyp_dir.exists() and hyp_dir.is_dir():
            for p in hyp_dir.glob("*.json"):
                try:
                    rec = json.loads(p.read_text())
                except json.JSONDecodeError:
                    continue
                if rec.get("status") == "killed":
                    kill_count += 1
        continuity_score = max(0.0, 1.0 - (kill_count / 40.0))

        # Audience-signal count, repeat-engagement (trust density).
        sig_dir = home_dir / "audience_signals"
        sig_count = 0
        person_counts: Dict[str, int] = {}
        if sig_dir.exists() and sig_dir.is_dir():
            for p in sig_dir.glob("*.json"):
                try:
                    rec = json.loads(p.read_text())
                except json.JSONDecodeError:
                    continue
                sig_count += 1
                pid = rec.get("person_id")
                if pid:
                    person_counts[pid] = person_counts.get(pid, 0) + 1
        repeat_engagements = sum(
            1 for c in person_counts.values() if c >= 2
        )
        trust_density = (
            repeat_engagements / len(person_counts)
            if person_counts else None
        )

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

        # primary_resource_used = thesis-pivot count today.
        thesis_pivots_today = sum(
            1 for a in actions if a.get("op") == "kill_event"
        )

        return NightlySummaryBase(
            date=date_iso,
            vertical="startup",
            primary_metric_today=continuity_score,
            primary_metric_label="strategic continuity score",
            honor_rate_today=honor_rate,
            primary_resource_used_today=float(thesis_pivots_today),
            primary_resource_label="thesis pivots",
            primary_success_rate_today=success_rate,
            extra={
                "audience_signals_today": sig_count,
                "trust_density": trust_density,
                "active_hypothesis_kill_count": kill_count,
            },
        )

    return nightly


def make_startup_app(
    *,
    home: Optional[Path] = None,
    registry_path: Optional[Path] = None,
    contract_path: Optional[Path] = None,
) -> DomainApp:
    """Build a ``DomainApp`` configured for the startup vertical."""
    config = StartupConfig(home=home)
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


def write_hypothesis(
    *,
    hypothesis: StartupHypothesis,
    home: Optional[Path] = None,
    share_with: Optional[List[str]] = None,
) -> None:
    """Persist a StartupHypothesis locally + emit a cross_vertical
    note. Default: PRIVATE. Founders explicitly opt into sharing."""
    base = home or (Path.home() / ".neuro_os_startup")
    base.mkdir(parents=True, exist_ok=True)
    hyp_dir = base / "hypotheses"
    hyp_dir.mkdir(parents=True, exist_ok=True)
    (hyp_dir / f"{hypothesis.id}.json").write_text(
        hypothesis.model_dump_json(indent=2)
    )
    write_note(
        source_vertical="startup",
        note_kind="startup_hypothesis",
        payload=hypothesis.model_dump(mode="json"),
        visible_to=(["startup"] + list(share_with)) if share_with else None,
    )


def write_audience_signal(
    *,
    signal: AudienceSignal,
    home: Optional[Path] = None,
) -> None:
    """Persist an AudienceSignal. Always private (audience comments
    are sensitive — never default-shared)."""
    base = home or (Path.home() / ".neuro_os_startup")
    base.mkdir(parents=True, exist_ok=True)
    sig_dir = base / "audience_signals"
    sig_dir.mkdir(parents=True, exist_ok=True)
    (sig_dir / f"{signal.id}.json").write_text(signal.model_dump_json(indent=2))


def write_bottleneck(
    *,
    bottleneck: Bottleneck,
    home: Optional[Path] = None,
) -> None:
    """Persist a Bottleneck row."""
    base = home or (Path.home() / ".neuro_os_startup")
    base.mkdir(parents=True, exist_ok=True)
    bn_dir = base / "bottlenecks"
    bn_dir.mkdir(parents=True, exist_ok=True)
    (bn_dir / f"{bottleneck.id}.json").write_text(
        bottleneck.model_dump_json(indent=2)
    )
