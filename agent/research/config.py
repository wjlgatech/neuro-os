"""
DomainConfig + DomainApp factory for the research vertical.

Wires the substrate to the research-specific catalog, ontology, and
defaults. The ``make_research_app`` factory is the public entry point;
tests and the daemon both call it.
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
from agent.research.catalog import RESEARCH_CATALOG, ResearchCatalog
from agent.research.ontology import (
    MechanismCard,
    ResearchContract,
    ResearchPriority,
)


class ResearchConfig:
    """Concrete ``DomainConfig`` for the research vertical."""

    vertical_name: str = "research"
    primary_resource_label: str = "papers read"
    primary_metric_label: str = "mechanism cards/day"
    catalog: ResearchCatalog = RESEARCH_CATALOG

    def __init__(self, home: Optional[Path] = None) -> None:
        self.home_dir: Path = home or (Path.home() / ".neuro_os_research")


# ---------------------------------------------------------------------------
# Hooks (shared shape across verticals; minimal v0)
# ---------------------------------------------------------------------------


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _make_morning_hook(
    *,
    contract_path: Path,
) -> Any:
    """Returns a callable that signs a ResearchContract and writes it
    to ``contract_path`` (one row per day, JSONL)."""

    def morning_ritual(
        *,
        active_thesis_id: str,
        priorities: List[ResearchPriority],
        primary_resource_budget: int = 1,  # PRD: 1 paper/day max
        threshold_pct: int = 90,
        when: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> ResearchContract:
        when = when or datetime.now(timezone.utc)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        contract = ResearchContract(
            date=when.date().isoformat(),
            primary_resource_budget=primary_resource_budget,
            threshold_pct=threshold_pct,
            signed_at=when,
            notes=notes,
            priorities=priorities,
            active_thesis_id=active_thesis_id,
        )
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        with contract_path.open("a", encoding="utf-8") as f:
            f.write(contract.model_dump_json() + "\n")
        return contract

    return morning_ritual


def _make_tick_hook(
    *,
    app: DomainApp,
    registry_path: Path,
) -> Any:
    """Returns a callable that runs one tick. v0 of research: takes an
    optional 'observed_failure_mode' (which the user names; predict.py
    style auto-detection lives in v1) and returns a ControlAction with
    the diagnosis."""

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
                    f"Research drift '{observed_failure_mode}' detected. "
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


def _make_nightly_hook(
    *,
    registry_path: Path,
    home_dir: Path,
) -> Any:
    """End-of-day rollup. Counts evidenced priorities, contract-honor
    rate, papers-read, and the 'sublimation success' (fraction of
    proposals that didn't precede a violation)."""

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

        # Honor rate
        actions = [r.get("action") or {} for r in today_rows]
        honored = sum(
            1 for a in actions
            if (a.get("contract_check") or {}).get("honored") is True
        )
        honor_rate = (honored / len(actions)) if actions else None

        # Mechanism cards count (from the cards directory under home_dir).
        cards_dir = home_dir / "mechanism_cards"
        card_count = 0
        if cards_dir.exists() and cards_dir.is_dir():
            card_count = sum(1 for p in cards_dir.glob("*.json") if p.is_file())

        # "primary_metric_today" = mechanism cards/day
        # "primary_resource_used_today" = papers read today
        # "primary_success_rate_today" = stuck-proposal rate
        primary_metric = float(card_count)
        # Sublimation success: of propose ops, fraction with no later violation.
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

        return NightlySummaryBase(
            date=date_iso,
            vertical="research",
            primary_metric_today=primary_metric,
            primary_metric_label="mechanism cards/day",
            honor_rate_today=honor_rate,
            primary_resource_used_today=float(card_count),  # 1 paper -> 1 card
            primary_resource_label="papers read",
            primary_success_rate_today=success_rate,
            extra={
                "thesis_continuity_check": "see cross_vertical for thesis history",
            },
        )

    return nightly


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def make_research_app(
    *,
    home: Optional[Path] = None,
    registry_path: Optional[Path] = None,
    contract_path: Optional[Path] = None,
) -> DomainApp:
    """Build a ``DomainApp`` configured for the research vertical.

    Defaults to ``~/.neuro_os_research/`` for everything; tests pass
    explicit paths.
    """
    config = ResearchConfig(home=home)
    home_dir = config.home_dir
    registry = registry_path or (home_dir / "registry.jsonl")
    contracts = contract_path or (home_dir / "contracts.jsonl")

    home_dir.mkdir(parents=True, exist_ok=True)

    # We construct the app first because the tick hook needs `app` for
    # make_diagnosis. Then we attach hooks via the public attribute.
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


def write_mechanism_card(
    *,
    card: MechanismCard,
    home: Optional[Path] = None,
    share_with: Optional[List[str]] = None,
) -> None:
    """Persist a MechanismCard locally AND emit a cross_vertical note.

    Default: card is private to research. Pass ``share_with=['investment',
    'startup']`` to broadcast (e.g. researcher wants startup to see the
    mechanism map for a market hypothesis).
    """
    base = home or (Path.home() / ".neuro_os_research")
    base.mkdir(parents=True, exist_ok=True)
    cards_dir = base / "mechanism_cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    (cards_dir / f"{card.id}.json").write_text(card.model_dump_json(indent=2))
    write_note(
        source_vertical="research",
        note_kind="mechanism_card",
        payload=card.model_dump(mode="json"),
        visible_to=(["research"] + list(share_with)) if share_with else None,
    )
