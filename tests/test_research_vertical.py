"""
Tests for the research vertical (Phase 2a).

Asserts:
* The catalog satisfies the substrate's invariants (6 needs, ≥1 option/need).
* DomainApp construction succeeds with ResearchConfig.
* morning_ritual signs a typed ResearchContract; thesis_id required.
* tick with observed_failure_mode emits propose_constructive_expression
  with a research-specific diagnosis.
* nightly produces a NightlySummary with the 4 first-class metrics.
* Cross-vertical: mechanism cards are PRIVATE to research by default.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agent.cross_vertical import query
from agent.research import (
    EVIDENCE_TYPE,
    MechanismCard,
    RESEARCH_CATALOG,
    ResearchContract,
    ResearchPriority,
    make_research_app,
)
from agent.research.config import write_mechanism_card


# ---------------------------------------------------------------------------
# Catalog invariants
# ---------------------------------------------------------------------------


def test_research_catalog_has_six_named_failure_modes():
    needs = RESEARCH_CATALOG.underlying_needs
    assert len(needs) == 6
    assert set(needs) == {
        "paper_collector",
        "topic_hopper",
        "memorizer",
        "authority_acceptor",
        "overloaded",
        "forgetting",
    }


def test_every_research_need_has_at_least_one_option():
    for need in RESEARCH_CATALOG.underlying_needs:
        opts = RESEARCH_CATALOG.options_for(need)
        assert len(opts) >= 1, f"need {need!r} has no options"
        for opt in opts:
            assert opt.action
            assert opt.duration_min >= 1
            assert opt.tank_credit_pct >= 0


# ---------------------------------------------------------------------------
# DomainApp construction
# ---------------------------------------------------------------------------


def test_make_research_app_construction(tmp_path):
    app = make_research_app(home=tmp_path / "home")
    assert app.config.vertical_name == "research"
    assert app.config.primary_resource_label == "papers read"
    assert app.config.primary_metric_label == "mechanism cards/day"


def test_make_research_app_substrate_validates_six_needs(tmp_path):
    """The substrate's _validate_config should pass for ResearchCatalog."""
    # Just constructing successfully is the assertion.
    make_research_app(home=tmp_path / "home")


# ---------------------------------------------------------------------------
# morning_ritual
# ---------------------------------------------------------------------------


def test_morning_ritual_signs_a_research_contract(tmp_path):
    app = make_research_app(home=tmp_path / "home")
    contract = app.morning_ritual(
        active_thesis_id="thesis-001",
        priorities=[
            ResearchPriority(
                title="extract mechanism from Friston 2010",
                evidence_type="paper_read",
                evidence_target="MechanismCard for predictive coding",
                weight=3,
                thesis_id="thesis-001",
            ),
        ],
        primary_resource_budget=1,
    )
    assert isinstance(contract, ResearchContract)
    assert contract.active_thesis_id == "thesis-001"
    assert len(contract.priorities) == 1
    assert contract.priorities[0].thesis_id == "thesis-001"


def test_morning_ritual_rejects_priority_without_thesis_id(tmp_path):
    """ResearchPriority requires thesis_id (single-thesis enforcement)."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        ResearchPriority(
            title="random reading",
            evidence_type="paper_read",
            evidence_target="something",
            weight=1,
            # thesis_id missing
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# tick: diagnosis fires for each named failure mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("failure_mode", [
    "paper_collector",
    "topic_hopper",
    "memorizer",
    "authority_acceptor",
    "overloaded",
    "forgetting",
])
def test_tick_proposes_constructive_expression_for_each_failure_mode(
    tmp_path, failure_mode,
):
    app = make_research_app(home=tmp_path / "home")
    result = app.tick(observed_failure_mode=failure_mode, dry_run=True)
    action = result["action"]
    assert action["op"] == "propose_constructive_expression"
    assert action["diagnosis"]["underlying_need"] == failure_mode
    assert len(action["diagnosis"]["options"]) >= 1
    assert action["payload"]["primary_action"]


def test_tick_with_no_drift_returns_continue(tmp_path):
    app = make_research_app(home=tmp_path / "home")
    result = app.tick(dry_run=True)
    assert result["action"]["op"] == "continue"


def test_tick_writes_to_registry_when_not_dry_run(tmp_path):
    home = tmp_path / "home"
    app = make_research_app(home=home)
    app.tick(observed_failure_mode="paper_collector", dry_run=False)
    registry = home / "registry.jsonl"
    assert registry.exists()
    content = registry.read_text()
    assert "propose_constructive_expression" in content


# ---------------------------------------------------------------------------
# nightly summary
# ---------------------------------------------------------------------------


def test_nightly_summary_carries_four_first_class_metrics(tmp_path):
    home = tmp_path / "home"
    app = make_research_app(home=home)
    # Run one tick that will be in today's date.
    app.tick(observed_failure_mode="paper_collector", dry_run=False)
    summary = app.nightly()
    assert summary.vertical == "research"
    assert summary.primary_metric_label == "mechanism cards/day"
    assert summary.primary_resource_label == "papers read"
    # Honor rate exists (the propose action was honored).
    assert summary.honor_rate_today is not None
    # Sublimation success rate computable (1 propose, no later violation = 1.0).
    assert summary.primary_success_rate_today == 1.0


def test_nightly_summary_handles_empty_registry(tmp_path):
    """Nightly on a fresh research home returns sensible defaults."""
    home = tmp_path / "home"
    app = make_research_app(home=home)
    summary = app.nightly()
    assert summary.honor_rate_today is None
    assert summary.primary_success_rate_today is None
    assert summary.primary_metric_today == 0.0


# ---------------------------------------------------------------------------
# Cross-vertical: research notes are PRIVATE by default
# ---------------------------------------------------------------------------


def test_mechanism_card_default_private_to_research(tmp_path, monkeypatch):
    """Writing a MechanismCard via write_mechanism_card defaults to
    research-only visibility. Investment and startup can't read it."""
    home = tmp_path / "home"
    monkeypatch.setenv("NEURO_OS_HOME", str(tmp_path / "neuro_os"))

    card = MechanismCard(
        id="card-001",
        ts=datetime.now(timezone.utc),
        paper_title="Friston 2010",
        paper_source="https://doi.org/10.1038/nrn2787",
        mechanism="free-energy minimization across cortical hierarchy",
        invariant="prediction error → update → predict",
        prediction="pharmacological disruption increases violations",
        failure_mode="non-stationary input distribution",
    )
    write_mechanism_card(card=card, home=home)

    # Research can read it (own vertical).
    own = query(reader="research")
    assert len(own) == 1
    assert own[0].note_kind == "mechanism_card"

    # Investment / startup cannot.
    assert query(reader="investment") == []
    assert query(reader="startup") == []


def test_mechanism_card_can_be_explicitly_shared(tmp_path, monkeypatch):
    """share_with=['investment'] at write time broadens visibility."""
    home = tmp_path / "home"
    monkeypatch.setenv("NEURO_OS_HOME", str(tmp_path / "neuro_os"))

    card = MechanismCard(
        id="card-002",
        ts=datetime.now(timezone.utc),
        paper_title="X",
        paper_source="DOI:y",
        mechanism="m",
        invariant="i",
        prediction="p",
        failure_mode="f",
    )
    write_mechanism_card(card=card, home=home, share_with=["investment"])

    assert query(reader="research") != []
    assert query(reader="investment") != []
    assert query(reader="startup") == []


# ---------------------------------------------------------------------------
# Evidence vocabulary is research-specific (not founder_loop's)
# ---------------------------------------------------------------------------


def test_evidence_type_vocabulary_is_research_shaped():
    # Pull the Literal members.
    valid_types = set(EVIDENCE_TYPE.__args__)  # type: ignore[attr-defined]
    assert "paper_read" in valid_types
    assert "experiment_run" in valid_types
    assert "prediction_logged" in valid_types
    # Anti-test: founder_loop terms are NOT in research's vocab.
    assert "commit_pushed" not in valid_types
    assert "pr_merged" not in valid_types
