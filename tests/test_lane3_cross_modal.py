"""
Tests for Lane 3 — cross-modal evaluation.

Strategy: every consensus / disagreement code path is exercised via
``make_fixture_scorers`` so the tests are hermetic — no LLM, no
network, fully deterministic.

The end-to-end test wires the module into investment's
``run_cross_modal_bias_check`` to verify the BiasCheck + CrossModalEval
pair persists correctly to disk.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from agent.cross_modal import (
    DISAGREEMENT_WARNING_THRESHOLD,
    CrossModalEval,
    ScorerVerdict,
    make_fixture_scorers,
    run_cross_modal_check,
)
from agent.investment import (
    PositionThesis,
    run_cross_modal_bias_check,
)


NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


def test_cross_modal_eval_is_frozen():
    scorers = make_fixture_scorers([(False, None, None)])
    e = run_cross_modal_check("test", scorers=scorers)
    with pytest.raises(Exception):  # noqa: B017 (Pydantic ValidationError)
        e.flag_count = 999  # type: ignore[misc]


def test_scorer_verdict_is_frozen():
    v = ScorerVerdict(scorer_label="x", flagged=True, primitive="emotional", reason="r")
    with pytest.raises(Exception):  # noqa: B017
        v.flagged = False  # type: ignore[misc]


def test_run_requires_at_least_one_scorer():
    with pytest.raises(ValueError):
        run_cross_modal_check("anything", scorers=[])


# ---------------------------------------------------------------------------
# All-agree paths (zero disagreement)
# ---------------------------------------------------------------------------


def test_unanimous_no_flag():
    scorers = make_fixture_scorers([
        (False, None, None),
        (False, None, None),
        (False, None, None),
    ])
    e = run_cross_modal_check("calm decision", scorers=scorers)
    assert e.consensus_verdict == "no_flag_unanimous"
    assert e.consensus_flagged is False
    assert e.flag_count == 0
    assert e.total_count == 3
    assert e.disagreement_score == 0.0
    assert e.low_confidence_warning is False


def test_unanimous_flag():
    scorers = make_fixture_scorers([
        (True, "emotional", "high arousal"),
        (True, "emotional", "panic words"),
        (True, "narrative_following", "story-thinking"),
    ])
    e = run_cross_modal_check("dump everything!", scorers=scorers)
    assert e.consensus_verdict == "flag_unanimous"
    assert e.consensus_flagged is True
    assert e.flag_count == 3
    assert e.disagreement_score == 0.0
    assert e.low_confidence_warning is False


# ---------------------------------------------------------------------------
# Majority paths (low disagreement; below warning threshold for K=3? actually
# 1/3 disagreement = 1 / (3/2) = 0.667 → warns; only K>=5 has below-threshold
# minorities). Pin the math explicitly.
# ---------------------------------------------------------------------------


def test_2_of_3_flag_majority():
    """flag_count=2, total=3: minority=1, disagreement=1/(3/2)=0.667 → warns."""
    scorers = make_fixture_scorers([
        (True, "emotional", "panic"),
        (True, "emotional", "panic"),
        (False, None, None),
    ])
    e = run_cross_modal_check("test", scorers=scorers)
    assert e.consensus_verdict == "flag_majority"
    assert e.consensus_flagged is True
    assert e.flag_count == 2
    assert e.disagreement_score == pytest.approx(2 / 3, rel=1e-3)
    assert e.low_confidence_warning is True  # 0.667 > 0.34


def test_2_of_3_no_flag_majority():
    scorers = make_fixture_scorers([
        (True, "emotional", "concerned"),
        (False, None, None),
        (False, None, None),
    ])
    e = run_cross_modal_check("test", scorers=scorers)
    assert e.consensus_verdict == "no_flag_majority"
    assert e.consensus_flagged is False
    assert e.flag_count == 1
    assert e.low_confidence_warning is True


# ---------------------------------------------------------------------------
# Tied paths (only meaningful with even K; pin K=4)
# ---------------------------------------------------------------------------


def test_2_of_4_tied():
    """flag_count=2, total=4: minority=2, disagreement=2/(4/2)=1.0."""
    scorers = make_fixture_scorers([
        (True, "emotional", None),
        (True, "emotional", None),
        (False, None, None),
        (False, None, None),
    ])
    e = run_cross_modal_check("ambiguous decision", scorers=scorers)
    assert e.consensus_verdict == "tied"
    # Conservative default for tied: do NOT block (consensus_flagged=False).
    assert e.consensus_flagged is False
    assert e.disagreement_score == 1.0
    assert e.low_confidence_warning is True


# ---------------------------------------------------------------------------
# Disagreement math invariants
# ---------------------------------------------------------------------------


def test_disagreement_is_zero_for_single_scorer():
    scorers = make_fixture_scorers([(True, "emotional", "x")])
    e = run_cross_modal_check("solo", scorers=scorers)
    # Single scorer: by definition no disagreement.
    assert e.disagreement_score == 0.0
    assert e.low_confidence_warning is False
    assert e.consensus_verdict == "flag_unanimous"


def test_disagreement_warning_threshold_constant():
    """Doc-the-constant: 0.34 means any 1-of-3 minority warns."""
    assert 0 < DISAGREEMENT_WARNING_THRESHOLD < 1.0
    assert DISAGREEMENT_WARNING_THRESHOLD < 2 / 3  # 1-of-3 must trip the warning


# ---------------------------------------------------------------------------
# Per-verdict accuracy (the verdict list should be in scorer order)
# ---------------------------------------------------------------------------


def test_verdicts_preserve_order_and_labels():
    scorers = make_fixture_scorers(
        [
            (True, "emotional", "first"),
            (False, None, None),
            (True, "narrative_following", "third"),
        ],
        labels=["haiku", "sonnet", "opus"],
    )
    e = run_cross_modal_check("test", scorers=scorers)
    assert [v.scorer_label for v in e.verdicts] == ["haiku", "sonnet", "opus"]
    assert e.verdicts[0].primitive == "emotional"
    assert e.verdicts[1].primitive is None
    assert e.verdicts[2].primitive == "narrative_following"


def test_make_fixture_scorers_validates_label_count():
    with pytest.raises(ValueError):
        make_fixture_scorers(
            [(True, None, None), (False, None, None)],
            labels=["only-one"],
        )


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_eval_round_trips_through_json():
    scorers = make_fixture_scorers([
        (True, "emotional", "r1"),
        (False, None, None),
        (True, "narrative_following", "r3"),
    ])
    e = run_cross_modal_check("hello world", scorers=scorers)
    body = e.model_dump_json()
    restored = CrossModalEval.model_validate_json(body)
    assert restored == e


def test_decision_text_excerpt_clipped_to_600_chars():
    long_text = "x" * 5000
    scorers = make_fixture_scorers([(False, None, None)])
    e = run_cross_modal_check(long_text, scorers=scorers)
    assert len(e.decision_text_excerpt) == 600


# ---------------------------------------------------------------------------
# End-to-end: investment vertical wiring (BiasCheck + CrossModalEval pair)
# ---------------------------------------------------------------------------


def _make_thesis() -> PositionThesis:
    return PositionThesis(
        id="thesis-test-001",
        ts=NOW,
        instrument="NVDA",
        thesis="Long NVDA: data-center demand stays strong for 4 quarters.",
        evidence=[
            "Hyperscaler capex up 35% YoY",
            "Blackwell GA timeline clear",
        ],
        confidence="medium",
        invalidation_condition="Hyperscaler capex falls > 15% sequentially",
        expected_timeline="6 months",
    )


def test_run_cross_modal_bias_check_persists_both(tmp_path):
    home = tmp_path / "investment"
    thesis = _make_thesis()
    scorers = make_fixture_scorers([
        (False, None, None),
        (False, None, None),
        (False, None, None),
    ])
    check, eval_result = run_cross_modal_bias_check(
        thesis=thesis, home=home, scorers=scorers,
    )
    # BiasCheck reflects consensus.
    assert check.thesis_id == thesis.id
    assert check.flagged is False
    # Both records persisted to their canonical dirs.
    bc_files = list((home / "bias_checks").glob("*.json"))
    cm_files = list((home / "cross_modal_evals").glob("*.json"))
    assert len(bc_files) == 1
    assert len(cm_files) == 1
    # Same id used for both files (audit-correlation invariant).
    assert bc_files[0].stem == cm_files[0].stem == check.id
    # CrossModalEval round-trips.
    body = json.loads(cm_files[0].read_text())
    restored = CrossModalEval.model_validate(body)
    assert restored == eval_result


def test_run_cross_modal_bias_check_warns_on_disagreement(tmp_path):
    home = tmp_path / "investment"
    thesis = _make_thesis()
    # 2 flag, 1 no-flag → consensus_flagged=True, disagreement above threshold.
    scorers = make_fixture_scorers([
        (True, "emotional", "panicky language"),
        (True, "emotional", "high arousal"),
        (False, None, None),
    ])
    check, eval_result = run_cross_modal_bias_check(
        thesis=thesis, home=home, scorers=scorers,
    )
    assert check.flagged is True
    assert check.mechanism == "emotional"  # majority primitive
    assert eval_result.low_confidence_warning is True
    # The reason string carries the low_confidence prefix so the
    # nightly summary can surface it.
    assert check.reason is not None
    assert "low_confidence" in check.reason


def test_run_cross_modal_bias_check_no_warning_on_unanimous_pass(tmp_path):
    home = tmp_path / "investment"
    thesis = _make_thesis()
    scorers = make_fixture_scorers([
        (False, None, None),
        (False, None, None),
        (False, None, None),
    ])
    check, eval_result = run_cross_modal_bias_check(
        thesis=thesis, home=home, scorers=scorers,
    )
    assert check.flagged is False
    assert check.reason is None or "low_confidence" not in (check.reason or "")
    assert eval_result.low_confidence_warning is False


def test_run_cross_modal_bias_check_majority_primitive(tmp_path):
    """When 2 scorers name 'emotional' and 1 names 'narrative_following',
    the BiasCheck.mechanism = 'emotional' (the majority)."""
    home = tmp_path / "investment"
    thesis = _make_thesis()
    scorers = make_fixture_scorers([
        (True, "emotional", "r1"),
        (True, "emotional", "r2"),
        (True, "narrative_following", "r3"),
    ])
    check, _ = run_cross_modal_bias_check(
        thesis=thesis, home=home, scorers=scorers,
    )
    assert check.mechanism == "emotional"


# ---------------------------------------------------------------------------
# Production scorer wiring (smoke test only — falls back to heuristic)
# ---------------------------------------------------------------------------


def test_make_default_scorers_produces_3_callable_pairs():
    from agent.cross_modal import make_default_scorers

    scorers = make_default_scorers(use_llm=False)
    assert len(scorers) == 3
    labels = [label for label, _ in scorers]
    assert "haiku-4-5" in labels[0]
    assert "sonnet-4-6" in labels[1]
    assert "opus-4-7" in labels[2]
    # And each is callable.
    for _, scorer in scorers:
        result = scorer("just a calm test sentence")
        assert isinstance(result, tuple)
        assert len(result) == 3
