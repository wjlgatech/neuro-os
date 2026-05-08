"""
Tests for the agent/domain_app/ substrate.

Verifies the contracts every vertical must satisfy:
* DomainConfig invariants (6 needs, ≥1 option per need)
* DomainApp construction validation
* Base schemas are frozen (Law 5)
* DiagnosisBase enforces ≥1 option (Law 1 / Law 3)
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from agent.domain_app import (
    ConstructiveExpressionBase,
    ContractCheck,
    ControlActionBase,
    DiagnosisBase,
    DomainApp,
    NightlySummaryBase,
    TankStateBase,
)
from agent.domain_app.app import DomainAppError


# ---------------------------------------------------------------------------
# Test fixtures: a minimal valid DomainConfig
# ---------------------------------------------------------------------------


class _FakeCatalog:
    """Minimal catalog satisfying DiagnosisCatalogProtocol."""

    underlying_needs: List[str] = [
        "need_a", "need_b", "need_c", "need_d", "need_e", "need_f",
    ]

    def options_for(self, need: str) -> List[ConstructiveExpressionBase]:
        return [
            ConstructiveExpressionBase(
                action=f"do_{need}",
                duration_min=10,
                tank_credit_pct=2.0,
            )
        ]


class _FakeConfig:
    """Minimal config satisfying DomainConfig."""

    vertical_name = "research"
    primary_resource_label = "papers read"
    primary_metric_label = "mechanism cards/day"
    catalog = _FakeCatalog()

    def __init__(self, home: Path) -> None:
        self.home_dir = home


def _make_app(tmp_path: Path) -> DomainApp:
    config = _FakeConfig(home=tmp_path / "research_home")
    return DomainApp(
        config=config,
        registry_path=tmp_path / "registry.jsonl",
        contract_path=tmp_path / "contracts.jsonl",
    )


# ---------------------------------------------------------------------------
# DomainApp construction validation
# ---------------------------------------------------------------------------


def test_domain_app_constructs_with_valid_config(tmp_path):
    app = _make_app(tmp_path)
    assert app.config.vertical_name == "research"
    assert app.config.home_dir.exists()


def test_domain_app_rejects_unknown_vertical_name(tmp_path):
    class BadConfig(_FakeConfig):
        vertical_name = "marketing"

    with pytest.raises(DomainAppError, match="vertical_name 'marketing' not in"):
        DomainApp(
            config=BadConfig(home=tmp_path / "h"),
            registry_path=tmp_path / "r.jsonl",
            contract_path=tmp_path / "c.jsonl",
        )


def test_domain_app_rejects_wrong_number_of_needs(tmp_path):
    class FiveNeedsCatalog(_FakeCatalog):
        underlying_needs = ["a", "b", "c", "d", "e"]  # only 5

    class BadConfig(_FakeConfig):
        catalog = FiveNeedsCatalog()

    with pytest.raises(DomainAppError, match="has 5 underlying_needs"):
        DomainApp(
            config=BadConfig(home=tmp_path / "h"),
            registry_path=tmp_path / "r.jsonl",
            contract_path=tmp_path / "c.jsonl",
        )


def test_domain_app_rejects_duplicate_needs(tmp_path):
    class DupCatalog(_FakeCatalog):
        underlying_needs = ["a", "a", "c", "d", "e", "f"]  # 'a' twice

    class BadConfig(_FakeConfig):
        catalog = DupCatalog()

    with pytest.raises(DomainAppError, match="duplicate"):
        DomainApp(
            config=BadConfig(home=tmp_path / "h"),
            registry_path=tmp_path / "r.jsonl",
            contract_path=tmp_path / "c.jsonl",
        )


def test_domain_app_rejects_need_with_no_options(tmp_path):
    class EmptyOptionsCatalog(_FakeCatalog):
        def options_for(self, need: str) -> List[ConstructiveExpressionBase]:
            return []  # no options

    class BadConfig(_FakeConfig):
        catalog = EmptyOptionsCatalog()

    with pytest.raises(DomainAppError, match="no constructive-expression options"):
        DomainApp(
            config=BadConfig(home=tmp_path / "h"),
            registry_path=tmp_path / "r.jsonl",
            contract_path=tmp_path / "c.jsonl",
        )


# ---------------------------------------------------------------------------
# Schema invariants (frozen + min_length)
# ---------------------------------------------------------------------------


def test_constructive_expression_is_frozen():
    expr = ConstructiveExpressionBase(
        action="walk",
        duration_min=10,
        tank_credit_pct=2.0,
    )
    with pytest.raises(Exception):  # pydantic frozen → ValidationError
        expr.action = "run"  # type: ignore[misc]


def test_diagnosis_requires_at_least_one_option():
    with pytest.raises(Exception):
        DiagnosisBase(
            underlying_need="need_a",
            confidence="medium",
            reasoning="...",
            options=[],  # empty — must raise
        )


def test_diagnosis_accepts_one_option():
    d = DiagnosisBase(
        underlying_need="need_a",
        confidence="medium",
        reasoning="...",
        options=[
            ConstructiveExpressionBase(
                action="walk", duration_min=10, tank_credit_pct=2.0,
            )
        ],
    )
    assert len(d.options) == 1


def test_control_action_carries_contract_check():
    action = ControlActionBase(
        op="continue",
        rationale="all good",
        contract_check=ContractCheck(honored=True),
    )
    assert action.contract_check.honored is True


def test_nightly_summary_has_four_first_class_metrics():
    summary = NightlySummaryBase(
        date="2026-05-07",
        vertical="research",
        primary_metric_today=3.5,
        primary_metric_label="cards/day",
        honor_rate_today=0.85,
        primary_resource_used_today=2.0,
        primary_resource_label="papers",
        primary_success_rate_today=0.6,
    )
    assert summary.vertical == "research"
    assert summary.extra == {}  # default empty


def test_tank_state_status_values():
    """TankStateBase.status must be one of the three documented positions."""
    for status in ("below_threshold", "threshold_within_budget", "threshold_over_budget"):
        TankStateBase(
            percent=50.0,
            credits_today=50.0,
            debits_today=0.0,
            threshold=90,
            budget_remaining=10,
            status=status,  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# DomainApp helper: make_diagnosis
# ---------------------------------------------------------------------------


def test_make_diagnosis_uses_catalog(tmp_path):
    app = _make_app(tmp_path)
    d = app.make_diagnosis(
        need="need_b",
        confidence="high",
        reasoning="testing",
    )
    assert d.underlying_need == "need_b"
    assert len(d.options) == 1
    assert d.options[0].action == "do_need_b"


def test_make_diagnosis_rejects_unknown_need(tmp_path):
    app = _make_app(tmp_path)
    with pytest.raises(DomainAppError, match="not in 'research' catalog"):
        app.make_diagnosis(
            need="not_in_catalog",
            confidence="high",
            reasoning="testing",
        )


def test_make_diagnosis_accepts_explicit_options(tmp_path):
    app = _make_app(tmp_path)
    custom = [
        ConstructiveExpressionBase(
            action="custom_alt", duration_min=15, tank_credit_pct=3.0,
        )
    ]
    d = app.make_diagnosis(
        need="need_c",
        confidence="low",
        reasoning="...",
        options=custom,
    )
    assert d.options[0].action == "custom_alt"


# ---------------------------------------------------------------------------
# Hooks: morning_ritual / tick / nightly raise without explicit hook
# ---------------------------------------------------------------------------


def test_morning_ritual_without_hook_raises(tmp_path):
    app = _make_app(tmp_path)
    with pytest.raises(DomainAppError, match="did not provide a 'morning_ritual' hook"):
        app.morning_ritual()


def test_tick_without_hook_raises(tmp_path):
    app = _make_app(tmp_path)
    with pytest.raises(DomainAppError, match="did not provide a 'tick' hook"):
        app.tick()


def test_nightly_without_hook_raises(tmp_path):
    app = _make_app(tmp_path)
    with pytest.raises(DomainAppError, match="did not provide a 'nightly' hook"):
        app.nightly()


def test_hooks_can_be_supplied(tmp_path):
    """Vertical wires its own implementation via hooks dict."""
    config = _FakeConfig(home=tmp_path / "h")
    app = DomainApp(
        config=config,
        registry_path=tmp_path / "r.jsonl",
        contract_path=tmp_path / "c.jsonl",
        hooks={
            "tick": lambda **kw: {"action": {"op": "continue"}},
        },
    )
    result = app.tick()
    assert result["action"]["op"] == "continue"
