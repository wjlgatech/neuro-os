"""
Example 07 — Belief OS as a primitive consumed by other products.

Belief OS is **not a standalone app**. It is a capability that other
products in the wjlgatech ecosystem call into. This example simulates
three consumers and shows the call shape each one would use.

Run::

    python examples/07_belief_os_consumer.py

No API key required for the offline path. Set ``ANTHROPIC_API_KEY`` to
have the Claude classifier handle slang/natural-language inputs the
keyword router would miss.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.belief_os import (  # noqa: E402
    BeliefOS,
    check_decision_text,
    classify_belief,
)


# ===========================================================================
# Consumer 1 — company-os Founder OS
# ===========================================================================
#
# Founder OS workflow: Intent → PLAN.md → Approval Gate → Execution → Memory.
# Belief OS plugs into the **Intent → Approval Gate** transition. When the
# user states an intent, Founder OS asks Belief OS "does this invoke a
# known reasoning failure mode?" and routes flagged intents through a
# confirmation step before promotion to PLAN.md.
# ===========================================================================


def founder_os_intent_check(intent: str) -> bool:
    """Stand-in for a Founder-OS approval-gate hook.

    Returns True iff the intent should be auto-approved. Returns False
    iff Founder OS should pause for human confirmation.
    """
    result = check_decision_text(intent)
    if result.flag_for_review:
        print(f"  ⚠️  FOUNDER-OS PAUSE — {result.flag_reason}")
        return False
    print(
        f"  ✅ FOUNDER-OS OK — invoked '{result.classification.mechanism}' "
        f"(decision: {result.classification.decision})"
    )
    return True


def consumer_1_founder_os() -> None:
    print("=" * 78)
    print("CONSUMER 1 — company-os Founder OS")
    print("Pattern: gate intents that invoke reasoning failure modes")
    print("=" * 78)
    intents = [
        # FAIL: invokes survivorship_bias
        "Drop out of college — Jobs and Gates and Zuck dropped out and became billionaires, that's the smart move.",
        # FAIL: invokes falsifiability (claim works for everyone always)
        "Adopt the 5am routine — it works for everyone always, no exceptions, this routine cannot fail.",
        # PASS: invokes expected_value (sound reasoning)
        "Allocate 5% to this bet because the expected value is positive after weighting the 1% chance of 100x.",
        # PASS: invokes second_order_thinking (sound reasoning)
        "Don't drop our price; the kids next door will outsell us short term but we'll trigger a price war.",
    ]
    for intent in intents:
        print(f"\n  INTENT: {intent[:78]}{'...' if len(intent) > 78 else ''}")
        founder_os_intent_check(intent)


# ===========================================================================
# Consumer 2 — money-os
# ===========================================================================
#
# money-os captures investment theses across time. Belief OS gives it a
# durable belief graph: when the user enters a new thesis, money-os calls
# ``ingest()`` to (a) classify the reasoning pattern, (b) detect if the
# thesis contradicts a prior thesis, and (c) gate the position by
# requiring contradiction resolution before booking. The graph is
# persisted to a per-user file so theses accumulate across sessions.
# ===========================================================================


def consumer_2_money_os() -> None:
    print("\n" + "=" * 78)
    print("CONSUMER 2 — money-os")
    print("Pattern: persistent belief graph for investment theses")
    print("=" * 78)

    # Per-user belief graph, persisted to disk. money-os would put this
    # under the user's account dir.
    tmp_dir = Path(tempfile.mkdtemp(prefix="money_os_demo_"))
    user_graph = tmp_dir / "user_alice_priors.json"
    print(f"\n  per-user graph: {user_graph}")

    money_belief_os = BeliefOS(ontology_path=user_graph)

    # Capture a thesis with strong evidence — the L1 loop should accept
    # the refinement and persist it.
    thesis_1 = (
        "Tetlock & Gardner (2015) Superforecasting "
        "https://doi.org/10.1234/superforecasting show that the brain "
        "does not update beliefs by Bayesian multiplication when priors "
        "are stale; calibration training is required. arXiv:1503.04567"
    )
    print("\n  → ingesting thesis 1 (citation-rich)...")
    r1 = money_belief_os.ingest(thesis_1, source_type="investment_thesis")
    print(f"    primitive={r1.classification.mechanism} merge_status={r1.merge_status}")
    print(f"    contradicts_prior={r1.contradicts_prior} updated={r1.primitive_updated}")

    # Now query the graph to confirm the thesis is recorded.
    print("\n  → query bayesian_updating belief now stored in user's graph:")
    records = money_belief_os.query(primitive="bayesian_updating")
    if records:
        rec = records[0]
        print(f"    sources tracked: {len(rec.sources)}")
        if rec.sources:
            print(f"    first source   : {rec.sources[0][:80]}...")

    # Capture a casual / weakly-cited claim — the L1 loop should NOT
    # merge it (weak evidence), but the classification still works.
    casual = "Markets always recover within a year, no exceptions."
    print(f"\n  → ingesting casual claim (no citation): {casual!r}")
    r2 = money_belief_os.ingest(casual, source_type="user_journal")
    print(f"    primitive={r2.classification.mechanism} merge_status={r2.merge_status}")
    if r2.classification.mechanism == "falsifiability":
        print("    money-os action: flag this thesis to the user before sizing")


# ===========================================================================
# Consumer 3 — hypothetical research-os
# ===========================================================================
#
# A research-os captures key claims from papers as the user reads. The
# value-add over a plain note-taking app is contradiction detection: when
# paper B claims the opposite of paper A (which the user previously
# ingested), research-os surfaces the contradiction at capture time.
# ===========================================================================


def consumer_3_research_os() -> None:
    print("\n" + "=" * 78)
    print("CONSUMER 3 — research-os (hypothetical)")
    print("Pattern: cross-paper contradiction detection at capture time")
    print("=" * 78)

    tmp_dir = Path(tempfile.mkdtemp(prefix="research_os_demo_"))
    user_graph = tmp_dir / "user_bob_research.json"
    print(f"\n  per-user graph: {user_graph}")

    research_belief_os = BeliefOS(ontology_path=user_graph)

    # User reads a paper — capture its key claim.
    paper_a = (
        "Tetlock & Gardner (2015) https://doi.org/10.1234/superforecasting "
        "show that the brain does not update beliefs by Bayesian "
        "multiplication when priors are stale. arXiv:1503.04567"
    )
    print("\n  → user reads paper A → captures key claim")
    r_a = research_belief_os.ingest(paper_a, source_type="research_paper")
    print(f"    primitive={r_a.classification.mechanism} merge_status={r_a.merge_status}")

    # User reads a SECOND paper that disagrees. The L1 loop should
    # detect the contradiction and propose a new refinement (which may
    # or may not pass the golden gate).
    paper_b = (
        "Friston (2018) https://doi.org/10.5678/freeenergy "
        "argues the brain updates beliefs by free-energy minimization "
        "without prior staleness — the prior is regularized by the "
        "generative model itself. arXiv:1807.12345"
    )
    print("\n  → user reads paper B (contradicts paper A) → captures key claim")
    r_b = research_belief_os.ingest(paper_b, source_type="research_paper")
    print(f"    primitive={r_b.classification.mechanism} merge_status={r_b.merge_status}")
    print(f"    contradicts_prior={r_b.contradicts_prior}")
    if r_b.contradicts_prior:
        print(
            "    research-os action: surface the contradiction at capture "
            "time, ask the user which framing to keep"
        )


# ===========================================================================
# One-off / stateless consumer (smallest possible call shape)
# ===========================================================================


def consumer_oneoff() -> None:
    print("\n" + "=" * 78)
    print("ONE-OFF — stateless `classify_belief()` for ad-hoc lookups")
    print("=" * 78)
    sample = (
        "There's a 1% chance this stock 100x and I become rich. The "
        "expected value is the same as keeping the cash, so why not yolo it?"
    )
    print(f"\n  INPUT: {sample}")
    r = classify_belief(sample)
    print(f"  → mechanism: {r.mechanism}")
    print(f"  → decision : {r.decision}")
    print(f"  → method   : {r.method}")
    print(f"  → TRUE     : {r.true_score}")
    print("\n  Use this when you don't need persistence — e.g. a Discord")
    print("  bot, a CLI, or a one-off label. No state, no API key needed.")


if __name__ == "__main__":
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(
        f"LLM extractor: {'ENABLED (Claude Haiku 4.5)' if has_key else 'OFF'}\n"
    )
    consumer_1_founder_os()
    consumer_2_money_os()
    consumer_3_research_os()
    consumer_oneoff()
    print("\n" + "=" * 78)
    print("All four consumers run against the same Belief OS primitive.")
    print("None of them know about ontologies, golden cases, or priority rules.")
    print("=" * 78)
