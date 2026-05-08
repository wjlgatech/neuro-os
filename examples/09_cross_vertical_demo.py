"""
Cross-vertical demo: how the 4 verticals talk through cross_vertical.

Story: a researcher writes a MechanismCard about market behavior
and explicitly shares it with the investment vertical. The investor
reads it, files a PositionThesis citing the mechanism, and
``run_bias_check`` flags any reasoning failures via belief_os. Their
thesis stays PRIVATE to investment by default — the researcher does
NOT see the position back.

This demonstrates the three guarantees of the substrate:

1. **Default-private cross-vertical visibility** (Phase 0 decision).
2. **Explicit opt-in sharing** via ``share_with=`` at write time.
3. **Belief OS as a primitive** that any vertical can consume —
   investment's bias detection is one example.

Run::

    python examples/09_cross_vertical_demo.py

Prints a step-by-step trace; writes nothing outside ``$NEURO_OS_HOME``
(default ``~/.neuro_os/``) plus the per-vertical homes.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from agent.cross_vertical import query
from agent.investment import PositionThesis
from agent.investment.config import run_bias_check, write_position_thesis
from agent.research import MechanismCard
from agent.research.config import write_mechanism_card


def main() -> None:
    # Use a temp dir for the demo so we don't pollute ~/.neuro_os.
    tmp = Path(tempfile.mkdtemp(prefix="neuro_os_xv_demo_"))
    os.environ["NEURO_OS_HOME"] = str(tmp / "neuro_os")
    research_home = tmp / "research"
    investment_home = tmp / "investment"

    print("=== STEP 1: researcher files a MechanismCard ===")
    card = MechanismCard(
        id="card-attn-001",
        ts=datetime.now(timezone.utc),
        paper_title="Attention is All You Need",
        paper_source="https://arxiv.org/abs/1706.03762",
        mechanism="self-attention enables tokens to consult arbitrary other tokens "
                  "in O(N^2) time, replacing recurrence as the long-range dependency mechanism.",
        invariant="all token-to-token paths are length 1; no information bottleneck "
                  "from sequential processing.",
        prediction="larger attention windows + more heads will dominate sequence-modeling "
                   "benchmarks for the next 5 years.",
        failure_mode="quadratic compute makes very long sequences expensive; sparse "
                     "attention or state-space models compete on long-context tasks.",
        thesis_id="thesis-llm-architecture",
    )
    # Researcher chooses to share with investment (e.g. for tech-thesis evaluation).
    write_mechanism_card(
        card=card,
        home=research_home,
        share_with=["investment"],
    )
    print(f"  Wrote MechanismCard {card.id!r} → shared with investment")
    print()

    print("=== STEP 2: investor reads research's mechanism cards ===")
    visible_to_investment = query(
        reader="investment",
        kinds=["mechanism_card"],
    )
    print(f"  Investment can see {len(visible_to_investment)} mechanism card(s)")
    for note in visible_to_investment:
        print(f"    - {note.payload['paper_title']} (mechanism={note.payload['mechanism'][:60]}...)")
    print()

    print("=== STEP 3: investor files a PositionThesis citing the mechanism ===")
    thesis = PositionThesis(
        id="position-nvda-001",
        ts=datetime.now(timezone.utc),
        instrument="NVDA",
        side="read_only",  # advisory-only v0
        thesis=(
            "Self-attention's quadratic compute (per research mechanism card "
            "attn-001) makes GPU compute the load-bearing constraint on the "
            "next 5 years of LLM scaling. NVIDIA's CUDA moat extracts the "
            "value of that constraint."
        ),
        evidence=[
            "Research MechanismCard card-attn-001: quadratic compute is the failure mode",
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
    # Note: thesis stays PRIVATE to investment by default (no share_with).
    write_position_thesis(thesis=thesis, home=investment_home)
    print(f"  Wrote PositionThesis {thesis.id!r} (default-PRIVATE to investment)")
    print()

    print("=== STEP 4: bias check via belief_os ===")
    check = run_bias_check(thesis=thesis, home=investment_home)
    print(f"  BiasCheck mechanism: {check.mechanism!r}")
    print(f"  Flagged: {check.flagged}")
    print(f"  Reason: {check.reason or '(none)'}")
    print()

    print("=== STEP 5: privacy check ===")
    research_view = query(
        reader="research",
        kinds=["position_thesis"],
    )
    startup_view = query(
        reader="startup",
        kinds=["position_thesis"],
    )
    print(f"  Research can see {len(research_view)} position_thesis "
          f"(should be 0 — investment didn't share back)")
    print(f"  Startup can see {len(startup_view)} position_thesis "
          f"(should be 0 — investment didn't share back)")
    if research_view or startup_view:
        raise AssertionError("PRIVACY LEAK: position thesis visible to other verticals")
    print("  ✓ Default-private boundary is intact.")
    print()

    print("=== STEP 6: investment vertical's nightly summary ===")
    from agent.investment import make_investment_app
    investment_app = make_investment_app(home=investment_home)
    summary = investment_app.nightly()
    print(f"  vertical: {summary.vertical}")
    print(f"  primary_metric_label: {summary.primary_metric_label}")
    print(f"  primary_metric_today: {summary.primary_metric_today}")
    print(f"  honor_rate_today: {summary.honor_rate_today}")
    print(f"  bias_checks_today: {summary.extra.get('bias_checks_today')}")
    print(f"  advisory_only: {summary.extra.get('advisory_only')}")
    print()

    print(f"Demo data written under: {tmp}")
    print("Done.")


if __name__ == "__main__":
    main()
