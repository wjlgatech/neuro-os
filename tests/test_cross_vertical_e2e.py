"""
Cross-vertical end-to-end privacy regression test.

Story under test (mirrors examples/09_cross_vertical_demo.py):

  1. Researcher writes a MechanismCard about LLM compute scaling and
     EXPLICITLY shares it with the investment vertical.
  2. Investor reads research's mechanism cards via cross_vertical.query.
  3. Investor files a PositionThesis citing the mechanism. The thesis
     stays PRIVATE to investment by default (no share_with).
  4. run_bias_check produces a typed BiasCheck via belief_os.
  5. PRIVACY ASSERTION: research and startup CANNOT see investment's
     position thesis. This is the load-bearing invariant.

This test is the CI gate. The matching demo lives at
``examples/09_cross_vertical_demo.py`` and is for human reading; this
test runs on every PR. If a future commit broadens the default
visibility of write_position_thesis (e.g. defaults to ['__all__']),
the privacy assertion below fires and CI goes red.

Anti-test: also asserts that broadcasting ['__all__'] DOES make the
note visible everywhere — so the test isn't vacuously passing because
visibility is broken in both directions.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agent.cross_vertical import query, write_note
from agent.investment import PositionThesis
from agent.investment.config import run_bias_check, write_position_thesis
from agent.research import MechanismCard
from agent.research.config import write_mechanism_card


@pytest.fixture
def neuro_os_home(tmp_path, monkeypatch):
    """Redirect the cross_vertical store to a tmp dir so this test
    doesn't pollute ~/.neuro_os/cross_vertical.jsonl."""
    home = tmp_path / "neuro_os"
    monkeypatch.setenv("NEURO_OS_HOME", str(home))
    return home


def test_cross_vertical_research_to_investment_handoff_with_privacy_intact(
    tmp_path, neuro_os_home,
):
    """End-to-end story: research → investment → bias_check, with
    investment's position thesis staying PRIVATE."""
    research_home = tmp_path / "research_home"
    investment_home = tmp_path / "investment_home"

    # ------------------------------------------------------------------
    # Step 1: researcher writes a MechanismCard, shared with investment.
    # ------------------------------------------------------------------
    card = MechanismCard(
        id="card-attn-001",
        ts=datetime.now(timezone.utc),
        paper_title="Attention is All You Need",
        paper_source="https://arxiv.org/abs/1706.03762",
        mechanism="self-attention enables tokens to consult arbitrary other "
                  "tokens in O(N^2) time, replacing recurrence as the long-"
                  "range dependency mechanism.",
        invariant="all token-to-token paths are length 1; no information "
                  "bottleneck from sequential processing.",
        prediction="larger attention windows + more heads will dominate "
                   "sequence-modeling benchmarks for the next 5 years.",
        failure_mode="quadratic compute makes very long sequences expensive; "
                     "sparse attention or state-space models compete.",
        thesis_id="thesis-llm-architecture",
    )
    write_mechanism_card(
        card=card,
        home=research_home,
        share_with=["investment"],
    )

    # ------------------------------------------------------------------
    # Step 2: investment can see the shared mechanism card.
    # ------------------------------------------------------------------
    visible = query(reader="investment", kinds=["mechanism_card"])
    assert len(visible) == 1
    assert visible[0].payload["paper_title"] == "Attention is All You Need"

    # ------------------------------------------------------------------
    # Step 3: investor files a PositionThesis (default-PRIVATE).
    # ------------------------------------------------------------------
    thesis = PositionThesis(
        id="position-nvda-001",
        ts=datetime.now(timezone.utc),
        instrument="NVDA",
        side="read_only",
        thesis=(
            "Self-attention's quadratic compute makes GPU compute the load-"
            "bearing constraint on the next 5 years of LLM scaling. NVIDIA's "
            "CUDA moat extracts the value of that constraint."
        ),
        evidence=[
            "Research MechanismCard card-attn-001: quadratic compute is failure mode",
            "Datacenter capex: $200B+ announced 2024-2025",
            "CUDA ecosystem entrenchment: switching cost is high",
        ],
        invalidation_condition=(
            "A non-CUDA accelerator (TPU, Trainium, etc.) captures >25% of "
            "training-cluster spend by EOY 2026"
        ),
        expected_timeline="24 months",
        confidence="medium",
    )
    write_position_thesis(thesis=thesis, home=investment_home)
    # NOTE: no share_with kwarg → must default to PRIVATE.

    # ------------------------------------------------------------------
    # Step 4: run_bias_check produces a typed BiasCheck.
    # ------------------------------------------------------------------
    check = run_bias_check(thesis=thesis, home=investment_home)
    assert check.thesis_id == "position-nvda-001"
    assert isinstance(check.flagged, bool)

    # ------------------------------------------------------------------
    # Step 5: PRIVACY ASSERTION (the load-bearing test).
    # ------------------------------------------------------------------
    research_view = query(reader="research", kinds=["position_thesis"])
    startup_view = query(reader="startup", kinds=["position_thesis"])
    investment_view = query(reader="investment", kinds=["position_thesis"])

    assert investment_view, (
        "investment should see its own thesis (source can always read)"
    )
    assert research_view == [], (
        "PRIVACY LEAK: research can see investment's position thesis. "
        "Default visibility regressed from PRIVATE to broadcast. "
        "Check write_position_thesis and cross_vertical.write_note defaults."
    )
    assert startup_view == [], (
        "PRIVACY LEAK: startup can see investment's position thesis. "
        "Same fix as above."
    )


def test_cross_vertical_explicit_broadcast_does_make_note_visible(
    neuro_os_home,
):
    """Anti-test for the privacy test: confirm that the visibility
    mechanism actually WORKS (a note shared with ['__all__'] reaches
    every vertical), so the privacy test isn't passing because
    visibility is broken in both directions."""
    write_note(
        source_vertical="research",
        note_kind="public_announcement",
        payload={"text": "I'm experimenting publicly today."},
        visible_to=["__all__"],
    )

    for reader in ("founder_loop", "investment", "startup"):
        notes = query(reader=reader, kinds=["public_announcement"])
        assert len(notes) == 1, (
            f"reader={reader} could not see a __all__-broadcast note. "
            f"The visibility mechanism is broken — privacy test would "
            f"pass vacuously without this anti-test catching it."
        )


def test_cross_vertical_share_after_the_fact_broadens_visibility(
    neuro_os_home,
):
    """Confirms that share_note() can broaden visibility post-write
    without mutating the original row. Mirrors the user-facing flow:
    researcher publishes a card privately, decides later to share."""
    from agent.cross_vertical import share_note

    note = write_note(
        source_vertical="investment",
        note_kind="position_thesis",
        payload={"ticker": "X"},
    )
    # Default-private — research can't see it.
    assert query(reader="research", kinds=["position_thesis"]) == []

    share_note(note_id=note.id, add_visible=["research"])

    # Research now sees it.
    research_view = query(reader="research", kinds=["position_thesis"])
    assert len(research_view) == 1
    # Startup still cannot.
    assert query(reader="startup", kinds=["position_thesis"]) == []
