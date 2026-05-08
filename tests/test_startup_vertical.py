"""
Tests for the startup vertical (Phase 2c).

Critical invariants:
* Single-thesis enforcement: priorities require hypothesis_id.
* primary_resource_budget (thesis_pivots/day) cannot exceed 1.
* Bottleneck has explicit type enum.
* AudienceSignal carries social_channel.
* Hypotheses default-PRIVATE in cross_vertical.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agent.cross_vertical import query
from agent.startup import (
    EVIDENCE_TYPE,
    STARTUP_CATALOG,
    AudienceSignal,
    Bottleneck,
    StartupContract,
    StartupHypothesis,
    StartupPriority,
    make_startup_app,
)
from agent.startup.config import (
    write_audience_signal,
    write_hypothesis,
)


# ---------------------------------------------------------------------------
# Catalog invariants
# ---------------------------------------------------------------------------


def test_startup_catalog_has_six_named_failure_modes():
    needs = STARTUP_CATALOG.underlying_needs
    assert len(needs) == 6
    assert set(needs) == {
        "idea_chaos",
        "broadcasting",
        "feature_creep",
        "vision_intoxicated",
        "vanity_metrics",
        "random_execution",
    }


def test_every_startup_need_has_at_least_one_option():
    for need in STARTUP_CATALOG.underlying_needs:
        opts = STARTUP_CATALOG.options_for(need)
        assert len(opts) >= 1


# ---------------------------------------------------------------------------
# Single-thesis enforcement
# ---------------------------------------------------------------------------


def test_startup_priority_requires_hypothesis_id():
    with pytest.raises(Exception):
        StartupPriority(
            title="ship something",
            evidence_type="hypothesis_validated",
            evidence_target="x",
            weight=2,
            # hypothesis_id missing
        )  # type: ignore[call-arg]


def test_morning_ritual_signs_a_startup_contract(tmp_path):
    app = make_startup_app(home=tmp_path / "home")
    contract = app.morning_ritual(
        active_hypothesis_id="hyp-001",
        priorities=[
            StartupPriority(
                title="capture 3 audience signals from twitter replies",
                evidence_type="audience_signal_captured",
                evidence_target="3 signals",
                weight=2,
                hypothesis_id="hyp-001",
            ),
        ],
    )
    assert isinstance(contract, StartupContract)
    assert contract.active_hypothesis_id == "hyp-001"


def test_morning_ritual_caps_thesis_pivots_at_one(tmp_path):
    """Hard cap: primary_resource_budget (thesis_pivots/day) <= 1."""
    app = make_startup_app(home=tmp_path / "home")
    with pytest.raises(ValueError, match="hard cap is 1"):
        app.morning_ritual(
            active_hypothesis_id="hyp-001",
            priorities=[
                StartupPriority(
                    title="ship",
                    evidence_type="hypothesis_validated",
                    evidence_target="x",
                    weight=1,
                    hypothesis_id="hyp-001",
                ),
            ],
            primary_resource_budget=2,  # over cap
        )


# ---------------------------------------------------------------------------
# Bottleneck schema with type enum
# ---------------------------------------------------------------------------


def test_bottleneck_requires_type_enum():
    bn = Bottleneck(
        id="b1",
        ts=datetime.now(timezone.utc),
        name="cold-email reply rate is 0.3%",
        bottleneck_type="distribution",
        evidence=["sent 200, got 0 replies"],
        proposed_unblock="switch from cold email to warm intros via shared "
                          "discord communities the target segment frequents",
    )
    assert bn.bottleneck_type == "distribution"


def test_bottleneck_rejects_invalid_type():
    with pytest.raises(Exception):
        Bottleneck(
            id="b1",
            ts=datetime.now(timezone.utc),
            name="x",
            bottleneck_type="marketing",  # not in BottleneckType  # type: ignore[arg-type]
            evidence=["e"],
            proposed_unblock="u",
        )


# ---------------------------------------------------------------------------
# AudienceSignal with social_channel enum
# ---------------------------------------------------------------------------


def test_audience_signal_requires_social_channel():
    sig = AudienceSignal(
        id="s1",
        ts=datetime.now(timezone.utc),
        social_channel="twitter",
        raw_text="why is this priced at $X when competitors are $Y?",
        interpreted_kind="objection",
        person_id="@alice",
    )
    assert sig.social_channel == "twitter"
    assert sig.interpreted_kind == "objection"


# ---------------------------------------------------------------------------
# DomainApp construction + tick + nightly
# ---------------------------------------------------------------------------


def test_make_startup_app_construction(tmp_path):
    app = make_startup_app(home=tmp_path / "home")
    assert app.config.vertical_name == "startup"
    assert app.config.primary_resource_label == "thesis pivots"
    assert app.config.primary_metric_label == "strategic continuity score"


@pytest.mark.parametrize("failure_mode", [
    "idea_chaos",
    "broadcasting",
    "feature_creep",
    "vision_intoxicated",
    "vanity_metrics",
    "random_execution",
])
def test_tick_proposes_for_each_failure_mode(tmp_path, failure_mode):
    app = make_startup_app(home=tmp_path / "home")
    result = app.tick(observed_failure_mode=failure_mode, dry_run=True)
    a = result["action"]
    assert a["op"] == "propose_constructive_expression"
    assert a["diagnosis"]["underlying_need"] == failure_mode


def test_nightly_summary_carries_four_first_class_metrics(tmp_path):
    app = make_startup_app(home=tmp_path / "home")
    app.tick(observed_failure_mode="broadcasting", dry_run=False)
    summary = app.nightly()
    assert summary.vertical == "startup"
    assert summary.primary_metric_label == "strategic continuity score"
    assert summary.primary_resource_label == "thesis pivots"
    # Strategic continuity defaults to 1.0 when no hypothesis kills.
    assert summary.primary_metric_today == 1.0
    # Audience signals + trust density show up in extra.
    assert "audience_signals_today" in summary.extra
    assert "trust_density" in summary.extra


# ---------------------------------------------------------------------------
# Trust density: repeat engagement signal
# ---------------------------------------------------------------------------


def test_nightly_trust_density_counts_repeat_engagement(tmp_path):
    home = tmp_path / "home"
    app = make_startup_app(home=home)
    # Same person posting twice → repeat engagement.
    write_audience_signal(
        signal=AudienceSignal(
            id="s1",
            ts=datetime.now(timezone.utc),
            social_channel="twitter",
            raw_text="first reply",
            interpreted_kind="resonance",
            person_id="@alice",
        ),
        home=home,
    )
    write_audience_signal(
        signal=AudienceSignal(
            id="s2",
            ts=datetime.now(timezone.utc),
            social_channel="twitter",
            raw_text="second reply",
            interpreted_kind="endorsement",
            person_id="@alice",
        ),
        home=home,
    )
    write_audience_signal(
        signal=AudienceSignal(
            id="s3",
            ts=datetime.now(timezone.utc),
            social_channel="email",
            raw_text="random one-off",
            interpreted_kind="confusion",
            person_id="@bob",
        ),
        home=home,
    )
    summary = app.nightly()
    # 1 repeat (alice) out of 2 unique people = 0.5
    assert summary.extra["trust_density"] == 0.5
    assert summary.extra["audience_signals_today"] == 3


# ---------------------------------------------------------------------------
# Cross-vertical: hypotheses default-private
# ---------------------------------------------------------------------------


def test_hypothesis_default_private_to_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURO_OS_HOME", str(tmp_path / "neuro_os"))
    h = StartupHypothesis(
        id="h1",
        title="X",
        hypothesis="Solo founders building AI agents will pay for "
                   "calm + coherence on top of cognitive overload.",
        target_segment="solo AI founders",
        falsification_signal="< 5% of contacted founders engage",
        expected_kpi_effect="MRR > $1k by Day 90",
        signed_at=datetime.now(timezone.utc),
    )
    write_hypothesis(hypothesis=h, home=tmp_path / "h")
    assert query(reader="startup") != []
    assert query(reader="research") == []
    assert query(reader="investment") == []


def test_hypothesis_can_be_explicitly_shared_with_research(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURO_OS_HOME", str(tmp_path / "neuro_os"))
    h = StartupHypothesis(
        id="h1",
        title="X",
        hypothesis="some hypothesis with at least ten characters",
        target_segment="seg",
        falsification_signal="sig",
        expected_kpi_effect="kpi",
        signed_at=datetime.now(timezone.utc),
    )
    write_hypothesis(hypothesis=h, home=tmp_path / "h", share_with=["research"])
    assert query(reader="startup") != []
    assert query(reader="research") != []
    assert query(reader="investment") == []


# ---------------------------------------------------------------------------
# Evidence vocabulary is startup-shaped
# ---------------------------------------------------------------------------


def test_evidence_vocabulary_is_startup_shaped():
    valid = set(EVIDENCE_TYPE.__args__)  # type: ignore[attr-defined]
    assert "hypothesis_validated" in valid
    assert "audience_signal_captured" in valid
    assert "bottleneck_resolved" in valid
    # Anti-test: no founder_loop / research / investment terms.
    assert "commit_pushed" not in valid
    assert "paper_read" not in valid
    assert "thesis_documented" not in valid
