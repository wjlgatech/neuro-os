"""
Tests for the Three-Layer Research OS strengthening of the research vertical.

Covers:
* Layer 1 extension: new optional fields on MechanismCardProposal /
  MechanismCard; RawSource.tier; framework module round-trip.
* LLM extractor: framework directive prepended; new optional fields
  flow through extract_mechanisms.
* Layer 2 synthesis: heuristic clusterer + LLM clusterer + window load
  + on-disk SynthesisRun round-trip.
* Layer 3 briefs: heuristic brief + LLM brief + on-disk DecisionBrief
  round-trip + markdown rendering.
* Checkpoints: write / read / converging / streak.
* Dashboard extensions: tier_balance + verdict_histogram + health flags
  + checkpoint integration.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent.research.briefs import (
    DecisionBrief,
    ProjectContext,
    QuestionForCollaborator,
    generate_brief,
    list_briefs,
    render_markdown,
    write_brief,
)
from agent.research.checkpoints import (
    CONVERGENCE_WARNING_THRESHOLD,
    ResearchCheckpoint,
    is_converging,
    latest_checkpoint,
    read_checkpoints,
    recent_no_streak,
    write_checkpoint,
)
from agent.research.dashboard import build_dashboard_summary, render_text
from agent.research.framework import (
    EMPTY_FRAMEWORK,
    Framework,
    FrameworkAxis,
    load_framework,
    save_framework,
)
from agent.research.ingest import _build_framework_directive, extract_mechanisms
from agent.research.ontology import (
    FrameworkAxisNote,
    MechanismCard,
    MechanismCardProposal,
    RawSource,
)
from agent.research.synthesis import (
    DEFAULT_JACCARD_THRESHOLD,
    MechanismCluster,
    SynthesisRun,
    cluster_proposals,
    list_synthesis_runs,
    read_synthesis_run,
    run_synthesis,
    write_synthesis_run,
)


NOW = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Layer 1 schema extension
# ---------------------------------------------------------------------------


def _stub_proposal(**overrides) -> MechanismCardProposal:
    base = dict(
        proposal_id="prop-001",
        proposed_at=NOW,
        status="pending",
        paper_title="Test paper",
        paper_source="arxiv:0000.00000",
        mechanism="Mechanism: weight regularization slows forgetting.",
        invariant="Stability/plasticity tradeoff is the load-bearing relation.",
        prediction="Network retains task A above 80% after training task B.",
        failure_mode="Fails when tasks share zero feature overlap.",
        source_id="src-001",
        source_excerpt="Excerpt from the paper.",
        extraction_method="llm-anthropic",
        confidence="high",
        reasoning="Stub for test.",
    )
    base.update(overrides)
    return MechanismCardProposal(**base)


def test_proposal_back_compat_without_new_fields():
    p = _stub_proposal()
    assert p.first_principle is None
    assert p.anti_pattern is None
    assert p.transferability_test is None
    assert p.verdict is None
    assert p.one_sentence_compression is None
    assert p.framework_alignment == []
    assert p.source_tier is None


def test_proposal_accepts_new_optional_fields():
    note = FrameworkAxisNote(axis_name="Continual", note="protects load-bearing weights")
    p = _stub_proposal(
        first_principle="Not all parameters are equal.",
        anti_pattern="Freezing the whole network kills plasticity.",
        transferability_test="Personal identity vs. surface habits.",
        verdict="foundational",
        one_sentence_compression="Protect what matters; let the rest adapt.",
        framework_alignment=[note],
        source_tier="seed",
    )
    assert p.verdict == "foundational"
    assert p.framework_alignment[0].axis_name == "Continual"
    assert p.source_tier == "seed"


def test_proposal_rejects_invalid_verdict():
    with pytest.raises(Exception):
        _stub_proposal(verdict="brilliant")  # not in the Literal


def test_proposal_round_trips_through_json():
    note = FrameworkAxisNote(axis_name="Observation", note="sensor stream")
    p = _stub_proposal(
        first_principle="A truth", verdict="useful", framework_alignment=[note],
    )
    blob = p.model_dump_json()
    restored = MechanismCardProposal.model_validate_json(blob)
    assert restored.first_principle == "A truth"
    assert restored.verdict == "useful"
    assert restored.framework_alignment[0].note == "sensor stream"


def test_mechanism_card_carries_new_fields():
    note = FrameworkAxisNote(axis_name="Control", note="action surface")
    card = MechanismCard(
        id="card-001",
        ts=NOW,
        paper_title="Title",
        paper_source="src",
        mechanism="mech",
        invariant="inv",
        prediction="pred",
        failure_mode="fail",
        verdict="useful",
        framework_alignment=[note],
    )
    assert card.verdict == "useful"
    assert card.framework_alignment[0].axis_name == "Control"


def test_raw_source_tier_optional():
    s = RawSource(
        source_id="s",
        path=Path("/tmp/x.txt"),
        title="t",
        author="a",
        word_count=10,
        sha256="a" * 64,
    )
    assert s.tier is None
    s2 = s.model_copy(update={"tier": "lateral"})
    assert s2.tier == "lateral"


def test_raw_source_rejects_invalid_tier():
    with pytest.raises(Exception):
        RawSource(
            source_id="s", path=Path("/tmp/x.txt"), title="t", author="a",
            word_count=10, sha256="a" * 64, tier="foundational",
        )


# ---------------------------------------------------------------------------
# Framework module
# ---------------------------------------------------------------------------


def test_load_framework_returns_empty_when_missing(tmp_path):
    fw = load_framework(home=tmp_path)
    assert fw.name == "(none)"
    assert fw.axes == []


def test_save_and_load_framework_round_trip(tmp_path):
    fw = Framework(
        name="OEC",
        description="Observation -> Evaluation -> Control",
        axes=[
            FrameworkAxis(name="Observation"),
            FrameworkAxis(name="Evaluation", description="delta detection"),
            FrameworkAxis(name="Control"),
        ],
        signed_at=NOW,
    )
    save_framework(fw, home=tmp_path)
    restored = load_framework(home=tmp_path)
    assert restored.name == "OEC"
    assert len(restored.axes) == 3
    assert restored.axes[1].description == "delta detection"


def test_load_framework_tolerates_malformed_json(tmp_path):
    target = tmp_path / "framework.json"
    target.write_text("{not valid json", encoding="utf-8")
    fw = load_framework(home=tmp_path)
    assert fw is EMPTY_FRAMEWORK or fw.name == "(none)"


def test_build_framework_directive_empty():
    assert _build_framework_directive(EMPTY_FRAMEWORK) == ""


def test_build_framework_directive_with_axes():
    fw = Framework(name="X", axes=[
        FrameworkAxis(name="A", description="alpha"),
        FrameworkAxis(name="B"),
    ])
    out = _build_framework_directive(fw)
    assert "USER FRAMEWORK" in out
    assert "A — alpha" in out
    assert "B" in out


# ---------------------------------------------------------------------------
# LLM extractor — new fields flow through
# ---------------------------------------------------------------------------


def _write_source(tmp_path: Path, name: str, body: str) -> Path:
    src = tmp_path / name
    src.write_text(body, encoding="utf-8")
    return src


def _make_raw_source(path: Path, *, tier=None) -> RawSource:
    body = path.read_text(encoding="utf-8")
    sha = hashlib.sha256(body.encode()).hexdigest()
    return RawSource(
        source_id=f"local:{path.name}:{sha[:12]}",
        path=path,
        title="Test",
        author="Author",
        word_count=len(body.split()),
        sha256=sha,
        tier=tier,
    )


def test_extract_mechanisms_with_llm_threads_new_fields(tmp_path):
    src_path = _write_source(tmp_path, "p1.txt", "Some text about a mechanism.")
    src = _make_raw_source(src_path, tier="seed")

    def fake_llm(system_prompt: str, user_text: str):
        # Simulate an LLM that fills out the deepening fields.
        return [{
            "mechanism": "Causal mechanism here.",
            "invariant": "Invariant.",
            "prediction": "When X then Y.",
            "failure_mode": "Fails when Z.",
            "source_excerpt": "Some text about a mechanism.",
            "confidence": "high",
            "reasoning": "Strong support.",
            "first_principle": "Deepest truth.",
            "anti_pattern": "Common misuse.",
            "transferability_test": "Personal habits.",
            "verdict": "foundational",
            "one_sentence_compression": "Compressed.",
            "framework_alignment": [
                {"axis_name": "Observation", "note": "perception"},
            ],
        }]

    proposals = extract_mechanisms(src, llm_fn=fake_llm, now=NOW)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.first_principle == "Deepest truth."
    assert p.anti_pattern == "Common misuse."
    assert p.verdict == "foundational"
    assert p.one_sentence_compression == "Compressed."
    assert p.framework_alignment[0].axis_name == "Observation"
    assert p.source_tier == "seed"


def test_extract_mechanisms_drops_invalid_verdict(tmp_path):
    src_path = _write_source(tmp_path, "p.txt", "text")
    src = _make_raw_source(src_path)

    def fake_llm(s, u):
        return [{
            "mechanism": "m", "invariant": "i", "prediction": "p",
            "failure_mode": "f", "source_excerpt": "ex",
            "confidence": "high", "reasoning": "r",
            "verdict": "amazing",  # not in the literal
        }]

    proposals = extract_mechanisms(src, llm_fn=fake_llm, now=NOW)
    assert proposals[0].verdict is None


def test_extract_mechanisms_drops_malformed_framework_alignment(tmp_path):
    src_path = _write_source(tmp_path, "p.txt", "text")
    src = _make_raw_source(src_path)

    def fake_llm(s, u):
        return [{
            "mechanism": "m", "invariant": "i", "prediction": "p",
            "failure_mode": "f", "source_excerpt": "ex",
            "confidence": "high", "reasoning": "r",
            "framework_alignment": [
                {"axis_name": "Good", "note": "valid"},
                {"axis_name": 123},  # bad note shape
                "not a dict",
                {"note": "missing name"},
            ],
        }]

    proposals = extract_mechanisms(src, llm_fn=fake_llm, now=NOW)
    assert [a.axis_name for a in proposals[0].framework_alignment] == ["Good"]


# ---------------------------------------------------------------------------
# Layer 2 synthesis
# ---------------------------------------------------------------------------


def _stub_card_dict(card_id: str, mechanism: str, *, verdict=None, **extra) -> dict:
    base = dict(
        id=card_id,
        ts=NOW.isoformat(),
        paper_title=f"Paper {card_id}",
        paper_source="src",
        mechanism=mechanism,
        invariant="inv",
        prediction="pred",
        failure_mode="fail",
        entity_mentions=[],
        verdict=verdict,
    )
    base.update(extra)
    return base


def test_heuristic_cluster_finds_lexical_match():
    a = _stub_card_dict("c1", "weight regularization protects important parameters")
    b = _stub_card_dict("c2", "regularization protects important model parameters")
    c = _stub_card_dict("c3", "latent replay stores activations at mid-layer")
    clusters, unclustered = cluster_proposals([a, b, c], llm_fn=None, min_cluster_size=2)
    assert len(clusters) == 1
    assert set(clusters[0].member_card_ids) == {"c1", "c2"}
    assert unclustered == ["c3"]


def test_heuristic_cluster_min_size_filter():
    a = _stub_card_dict("c1", "unique mechanism alpha")
    b = _stub_card_dict("c2", "unique mechanism beta gamma")
    clusters, unclustered = cluster_proposals([a, b], llm_fn=None, min_cluster_size=3)
    assert clusters == []
    assert set(unclustered) == {"c1", "c2"}


def test_heuristic_cluster_propagates_framework_axes():
    a = _stub_card_dict(
        "c1", "weight regularization slows forgetting",
        framework_alignment=[{"axis_name": "Continual", "note": "memory"}],
    )
    b = _stub_card_dict(
        "c2", "regularization slows forgetting via importance",
        framework_alignment=[{"axis_name": "Observation", "note": "sensor"}],
    )
    clusters, _ = cluster_proposals([a, b], llm_fn=None)
    assert clusters
    assert set(clusters[0].framework_axes_touched) == {"Continual", "Observation"}


def test_llm_cluster_basic():
    a = _stub_card_dict("c1", "first mechanism")
    b = _stub_card_dict("c2", "second mechanism")
    c = _stub_card_dict("c3", "third mechanism")

    def fake_llm(system_prompt, user_text):
        # Return one cluster with two members.
        return [{
            "label": "shared cluster",
            "mechanism_summary": "all about mechanisms",
            "member_card_ids": ["c1", "c2"],
            "shared_first_principle": "principle",
            "recurring_anti_pattern": "anti",
            "frontier_position": "contested",
            "false_consensus_flag": "thin evidence here",
            "framework_axes_touched": ["A", "B"],
        }]

    clusters, unclustered = cluster_proposals([a, b, c], llm_fn=fake_llm, min_cluster_size=2)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.label == "shared cluster"
    assert cluster.shared_first_principle == "principle"
    assert cluster.frontier_position == "contested"
    assert set(cluster.framework_axes_touched) == {"A", "B"}
    assert unclustered == ["c3"]


def test_llm_cluster_drops_unknown_ids():
    a = _stub_card_dict("c1", "m1")
    b = _stub_card_dict("c2", "m2")

    def fake_llm(s, u):
        return [{
            "label": "x", "mechanism_summary": "y",
            "member_card_ids": ["c1", "c2", "ghost"],
        }]
    clusters, _ = cluster_proposals([a, b], llm_fn=fake_llm, min_cluster_size=2)
    assert set(clusters[0].member_card_ids) == {"c1", "c2"}


def test_llm_cluster_drops_below_min_size():
    a = _stub_card_dict("c1", "m1")

    def fake_llm(s, u):
        return [{
            "label": "x", "mechanism_summary": "y",
            "member_card_ids": ["c1"],
        }]
    clusters, unclustered = cluster_proposals([a], llm_fn=fake_llm, min_cluster_size=2)
    assert clusters == []
    assert unclustered == ["c1"]


def _write_card_file(home: Path, card_id: str, mechanism: str, *, ts=NOW, verdict=None):
    cards_dir = home / "mechanism_cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    body = json.dumps(_stub_card_dict(card_id, mechanism, verdict=verdict, ts=ts.isoformat()))
    (cards_dir / f"{card_id}.json").write_text(body, encoding="utf-8")


def test_run_synthesis_end_to_end(tmp_path):
    _write_card_file(tmp_path, "c1", "weight regularization slows forgetting")
    _write_card_file(tmp_path, "c2", "regularization slows weight forgetting")
    _write_card_file(tmp_path, "c3", "completely different mechanism alpha")
    run = run_synthesis(home=tmp_path, window_days=30, min_cluster_size=2, now=NOW)
    assert isinstance(run, SynthesisRun)
    assert run.input_card_count == 3
    assert len(run.clusters) == 1
    # Persistence round-trip.
    restored = read_synthesis_run(run.run_id, home=tmp_path)
    assert restored is not None
    assert restored.run_id == run.run_id


def test_run_synthesis_empty_corpus(tmp_path):
    run = run_synthesis(home=tmp_path, window_days=30, now=NOW)
    assert run.input_card_count == 0
    assert run.clusters == ()
    assert "no accepted mechanism cards" in (run.note or "")


def test_run_synthesis_outside_window(tmp_path):
    old = NOW - timedelta(days=60)
    _write_card_file(tmp_path, "c1", "m1", ts=old)
    _write_card_file(tmp_path, "c2", "m2", ts=old)
    run = run_synthesis(home=tmp_path, window_days=30, now=NOW)
    assert run.input_card_count == 0


def test_list_synthesis_runs_sorted(tmp_path):
    a = SynthesisRun(
        run_id="a", generated_at=NOW - timedelta(days=2),
        window_days=30, min_cluster_size=2,
        method="fallback-heuristic", input_card_count=0,
    )
    b = SynthesisRun(
        run_id="b", generated_at=NOW,
        window_days=30, min_cluster_size=2,
        method="fallback-heuristic", input_card_count=0,
    )
    write_synthesis_run(a, home=tmp_path)
    write_synthesis_run(b, home=tmp_path)
    runs = list_synthesis_runs(home=tmp_path)
    assert [r.run_id for r in runs] == ["b", "a"]


# ---------------------------------------------------------------------------
# Layer 3 briefs
# ---------------------------------------------------------------------------


def _stub_cluster(**overrides) -> MechanismCluster:
    base = dict(
        cluster_id="cl-1",
        label="weight regularization",
        mechanism_summary="protect load-bearing weights when learning new tasks",
        member_card_ids=("c1", "c2"),
        shared_first_principle="Not all parameters are equal.",
        recurring_anti_pattern="Freezing the whole net.",
        frontier_position="contested",
        framework_axes_touched=("Continual",),
    )
    base.update(overrides)
    return MechanismCluster(**base)


def _stub_context(**overrides) -> ProjectContext:
    base = dict(
        project_name="DemoProject",
        description="A test project.",
        current_questions=("How do we add capability without regression?",),
        collaborators=("Alex", "Sam"),
        pending_decisions=("ship feature X?",),
        framework_name="OEC",
    )
    base.update(overrides)
    return ProjectContext(**base)


def test_heuristic_brief_uses_context_decisions():
    cluster = _stub_cluster()
    ctx = _stub_context()
    brief = generate_brief(
        cluster=cluster, context=ctx, synthesis_run_id="run-1", now=NOW,
    )
    assert brief.method == "fallback-heuristic"
    assert any("ship feature X?" in d for d in brief.next_decisions)
    assert any("How do we add capability" in e for e in brief.next_experiments)
    assert any(q.collaborator_name == "Alex" for q in brief.questions_for_collaborators)


def test_llm_brief_overrides_heuristic_when_valid():
    cluster = _stub_cluster()
    ctx = _stub_context()

    def fake_llm(s, u):
        return {
            "project_implications": ["A specific implication"],
            "next_decisions": ["A specific decision"],
            "next_experiments": ["A specific experiment"],
            "questions_for_collaborators": [
                {"collaborator_name": "Alex", "question": "What's your test?",
                 "why_this_question": "to surface assumptions"},
            ],
            "framework_alignment_summary": "axis touched: Continual",
        }
    brief = generate_brief(
        cluster=cluster, context=ctx, synthesis_run_id="r",
        llm_fn=fake_llm, now=NOW,
    )
    assert brief.method == "llm-anthropic"
    assert brief.project_implications == ("A specific implication",)
    assert brief.questions_for_collaborators[0].question == "What's your test?"
    assert brief.framework_alignment_summary == "axis touched: Continual"


def test_llm_brief_falls_back_on_garbage_output():
    cluster = _stub_cluster()
    ctx = _stub_context()

    def fake_llm(s, u):
        return None  # simulating parse failure
    brief = generate_brief(
        cluster=cluster, context=ctx, synthesis_run_id="r",
        llm_fn=fake_llm, now=NOW,
    )
    assert brief.method == "fallback-heuristic"


def test_brief_round_trips_to_disk(tmp_path):
    cluster = _stub_cluster()
    ctx = _stub_context()
    brief = generate_brief(
        cluster=cluster, context=ctx, synthesis_run_id="r", now=NOW,
    )
    json_path, md_path = write_brief(brief, home=tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    md = md_path.read_text(encoding="utf-8")
    assert "# Brief — DemoProject" in md
    listed = list_briefs(home=tmp_path)
    assert listed[0].brief_id == brief.brief_id


def test_render_markdown_includes_questions():
    cluster = _stub_cluster()
    q = QuestionForCollaborator(collaborator_name="Alex", question="why?")
    brief = DecisionBrief(
        brief_id="b1", generated_at=NOW, cluster_id=cluster.cluster_id,
        synthesis_run_id="r", project_name="P", method="fallback-heuristic",
        questions_for_collaborators=(q,),
    )
    md = render_markdown(brief, cluster=cluster)
    assert "Alex" in md
    assert "why?" in md


# ---------------------------------------------------------------------------
# Checkpoints
# ---------------------------------------------------------------------------


def _stub_checkpoint(brief_produced=True, clearer=True, ts=NOW, note=None):
    return ResearchCheckpoint(
        checkpoint_id=f"chk-{uuid.uuid4().hex[:8]}",
        ts=ts,
        brief_produced=brief_produced,
        mental_model_clearer=clearer,
        note=note,
    )


def test_write_and_read_checkpoints_round_trip(tmp_path):
    c1 = _stub_checkpoint()
    c2 = _stub_checkpoint(clearer=False, ts=NOW + timedelta(days=1))
    write_checkpoint(c1, home=tmp_path)
    write_checkpoint(c2, home=tmp_path)
    events = read_checkpoints(home=tmp_path)
    assert len(events) == 2
    assert events[0].checkpoint_id == c1.checkpoint_id
    assert events[1].checkpoint_id == c2.checkpoint_id


def test_is_converging_requires_both():
    assert is_converging(_stub_checkpoint(True, True))
    assert not is_converging(_stub_checkpoint(True, False))
    assert not is_converging(_stub_checkpoint(False, True))
    assert not is_converging(_stub_checkpoint(False, False))


def test_recent_no_streak_counts_trailing_failures(tmp_path):
    base = NOW
    write_checkpoint(_stub_checkpoint(True, True, ts=base), home=tmp_path)
    write_checkpoint(
        _stub_checkpoint(False, True, ts=base + timedelta(days=1)), home=tmp_path,
    )
    write_checkpoint(
        _stub_checkpoint(True, False, ts=base + timedelta(days=2)), home=tmp_path,
    )
    streak = recent_no_streak(home=tmp_path, k=5)
    assert streak == 2
    assert streak >= CONVERGENCE_WARNING_THRESHOLD


def test_recent_no_streak_resets_on_converging(tmp_path):
    base = NOW
    write_checkpoint(_stub_checkpoint(False, False, ts=base), home=tmp_path)
    write_checkpoint(_stub_checkpoint(True, True, ts=base + timedelta(days=1)), home=tmp_path)
    write_checkpoint(_stub_checkpoint(True, True, ts=base + timedelta(days=2)), home=tmp_path)
    streak = recent_no_streak(home=tmp_path, k=5)
    assert streak == 0


def test_latest_checkpoint_returns_most_recent(tmp_path):
    write_checkpoint(_stub_checkpoint(True, True, ts=NOW), home=tmp_path)
    later = _stub_checkpoint(False, True, ts=NOW + timedelta(days=1))
    write_checkpoint(later, home=tmp_path)
    got = latest_checkpoint(home=tmp_path)
    assert got is not None
    assert got.checkpoint_id == later.checkpoint_id


def test_latest_checkpoint_missing(tmp_path):
    assert latest_checkpoint(home=tmp_path) is None


# ---------------------------------------------------------------------------
# Dashboard extensions
# ---------------------------------------------------------------------------


def _write_proposal_file(home: Path, prop_id: str, *, status="accepted",
                          proposed_at=NOW, tier=None):
    pdir = home / "proposals" / status
    pdir.mkdir(parents=True, exist_ok=True)
    proposal = _stub_proposal(
        proposal_id=prop_id,
        proposed_at=proposed_at,
        status=status,
        source_tier=tier,
    )
    (pdir / f"{prop_id}.json").write_text(
        proposal.model_dump_json(indent=2), encoding="utf-8",
    )


def test_dashboard_tier_balance_and_verdict_histogram(tmp_path):
    # Two seed proposals + one frontier + one unknown.
    _write_proposal_file(tmp_path, "p1", tier="seed")
    _write_proposal_file(tmp_path, "p2", tier="seed")
    _write_proposal_file(tmp_path, "p3", tier="frontier")
    _write_proposal_file(tmp_path, "p4")
    # Cards with verdicts.
    _write_card_file(tmp_path, "c1", "m1", verdict="foundational")
    _write_card_file(tmp_path, "c2", "m2", verdict="foundational")
    _write_card_file(tmp_path, "c3", "m3", verdict="useful")
    _write_card_file(tmp_path, "c4", "m4")  # unrated

    summary = build_dashboard_summary(home=tmp_path, window_days=30, now=NOW)
    assert summary.tier_balance.get("seed") == 2
    assert summary.tier_balance.get("frontier") == 1
    assert summary.tier_balance.get("unknown") == 1
    assert summary.verdict_histogram.get("foundational") == 2
    assert summary.verdict_histogram.get("useful") == 1
    assert summary.verdict_histogram.get("unrated") == 1


def test_dashboard_chaser_mode_flag(tmp_path):
    # 7 frontier, 0 seed → over 70% frontier, under 10% seed → chaser_mode.
    for i in range(7):
        _write_proposal_file(tmp_path, f"f{i}", tier="frontier")
    summary = build_dashboard_summary(home=tmp_path, window_days=30, now=NOW)
    assert "chaser_mode" in summary.system_health_flags


def test_dashboard_rubber_stamping_flag(tmp_path):
    # 6 cards all rated useful/foundational, zero skip/misleading.
    for i in range(6):
        _write_card_file(tmp_path, f"c{i}", "mech", verdict="useful")
    summary = build_dashboard_summary(home=tmp_path, window_days=30, now=NOW)
    assert "rubber_stamping" in summary.system_health_flags


def test_dashboard_rubber_stamping_does_not_fire_with_skip(tmp_path):
    for i in range(5):
        _write_card_file(tmp_path, f"c{i}", "mech", verdict="useful")
    _write_card_file(tmp_path, "cskip", "mech", verdict="skip")
    summary = build_dashboard_summary(home=tmp_path, window_days=30, now=NOW)
    assert "rubber_stamping" not in summary.system_health_flags


def test_dashboard_no_synthesis_flag(tmp_path):
    for i in range(6):
        _write_proposal_file(tmp_path, f"p{i}", tier="seed")
    summary = build_dashboard_summary(home=tmp_path, window_days=30, now=NOW)
    assert "no_synthesis" in summary.system_health_flags


def test_dashboard_system_not_converging_flag(tmp_path):
    write_checkpoint(_stub_checkpoint(False, False, ts=NOW), home=tmp_path)
    write_checkpoint(
        _stub_checkpoint(False, False, ts=NOW + timedelta(seconds=1)),
        home=tmp_path,
    )
    summary = build_dashboard_summary(home=tmp_path, window_days=30, now=NOW + timedelta(seconds=2))
    assert "system_not_converging" in summary.system_health_flags
    assert summary.checkpoint_no_streak >= 2
    assert summary.latest_checkpoint_converging is False


def test_dashboard_synthesis_count_and_briefs(tmp_path):
    # Create one synthesis run + one brief in window.
    run = SynthesisRun(
        run_id="r1", generated_at=NOW, window_days=30, min_cluster_size=2,
        method="fallback-heuristic", input_card_count=0,
    )
    write_synthesis_run(run, home=tmp_path)
    brief = DecisionBrief(
        brief_id="b1", generated_at=NOW, cluster_id="cl",
        synthesis_run_id="r1", project_name="P", method="fallback-heuristic",
    )
    write_brief(brief, home=tmp_path)
    summary = build_dashboard_summary(home=tmp_path, window_days=30, now=NOW)
    assert summary.synthesis_run_count == 1
    assert summary.briefs_produced_in_window == 1


def test_dashboard_render_text_includes_new_section(tmp_path):
    _write_card_file(tmp_path, "c1", "m1", verdict="useful")
    summary = build_dashboard_summary(home=tmp_path, window_days=30, now=NOW)
    text = render_text(summary)
    assert "Three-Layer Research OS" in text
    assert "tier balance" in text
    assert "verdicts" in text
    assert "synthesis runs" in text


def test_dashboard_handles_empty_state(tmp_path):
    summary = build_dashboard_summary(home=tmp_path, window_days=30, now=NOW)
    assert summary.tier_balance == {}
    assert summary.verdict_histogram == {}
    assert summary.system_health_flags == []
    assert summary.synthesis_run_count == 0
    assert summary.latest_checkpoint_converging is None


# ---------------------------------------------------------------------------
# Threshold sanity check (DEFAULT_JACCARD_THRESHOLD exposed for import users)
# ---------------------------------------------------------------------------


def test_default_jaccard_threshold_in_unit_range():
    assert 0.0 < DEFAULT_JACCARD_THRESHOLD < 1.0
