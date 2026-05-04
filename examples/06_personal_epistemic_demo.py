"""
Example 06 — Belief OS (``personal_epistemic_v1``) end-to-end demo.

Runs the same closed loop as the neuroscience domain, but pointed at six
reasoning primitives (Bayesian updating, base-rate reasoning, falsifiability,
expected value, second-order thinking, survivorship bias).

Stage 1: classify a handful of claims and show the predicted primitive,
         decision, and TRUE score.

Stage 2: feed a citation-rich note that proposes a refinement to one of
         the primitives. Run the L1 loop with the Belief-OS goldens and
         priority rules. Print the merge outcome and the resulting
         ontology delta.

Stage 3 (v1.2 LLM upgrade): try the SAME slang claims with the LLM
         extractor enabled. Skipped automatically if ``ANTHROPIC_API_KEY``
         is not set.

Run::

    python examples/06_personal_epistemic_demo.py            # stages 1+2 (offline)
    ANTHROPIC_API_KEY=sk-... python examples/06_personal_epistemic_demo.py  # + stage 3
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Allow running directly without `pip install -e .`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Importing the module registers the domain.
import agent.personal_epistemic_domain  # noqa: E402, F401
from agent import primitive_feedback, version_registry  # noqa: E402
from agent.api import ingest_documents  # noqa: E402
from agent.domains import get_domain  # noqa: E402
from agent.personal_epistemic_domain import (  # noqa: E402
    PERSONAL_EPISTEMIC_GOLDEN_CASES,
    PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH,
    disable_llm,
    enable_llm,
    personal_epistemic_extractor,
)


# Slang / informal claims that the v1.1 keyword router struggles with.
# These are the inputs we'll re-run with the LLM extractor in Stage 3.
SLANG_CLAIMS = [
    "bro every founder I know who actually made bank just bailed on school fr, the smart move is to not bother with college",
    "she literally tested cancer free, she's gonna live forever fr fr",
    "if I lower my price tmrw I'll crush the competition",
    "lol my uncle is so confident crypto will 10x next year, but his last 5 'sure things' all flopped",
    "this morning routine works for everyone always, no exceptions, you just have to actually try it",
    "bananas are yellow when ripe and float in fresh water lmao",
]


def stage1_classify() -> None:
    print("=" * 72)
    print("Stage 1 — classify claims against Belief OS")
    print("=" * 72)
    claims = [
        "Successful founders dropped out of college, so dropouts succeed — "
        "but the failed dropouts are invisible. Survivorship bias.",
        "A medical test is 99% accurate but disease prevalence is 0.1%; "
        "after a positive result, the posterior probability of disease "
        "is only ~9% because the prior dominates the likelihood ratio.",
        "The forecast 'markets will be volatile next year' forbids no "
        "observation and is therefore unfalsifiable.",
        "Bananas turn yellow when ripe. They float in fresh water.",  # OOD
    ]
    for claim in claims:
        result = personal_epistemic_extractor(claim)
        knowledge = result["knowledge"]
        scores = result["true_validation"]["scores"]
        print(f"\n  CLAIM    : {claim[:72]}{'...' if len(claim) > 72 else ''}")
        print(f"  PRIMITIVE: {knowledge.get('mechanism')}")
        print(f"  DECISION : {result['decision']}")
        print(f"  TRUE     : {scores.get('TRUE')}  (E={scores.get('E')} "
              f"U={scores.get('U')} R={scores.get('R')} T={scores.get('T')})")


def stage2_ingest_with_learnback() -> None:
    print("\n" + "=" * 72)
    print("Stage 2 — ingest a contradiction; watch the ontology evolve")
    print("=" * 72)

    contradiction = (
        "Tetlock & Gardner (2015) https://doi.org/10.1234/superforecasting "
        "show that the brain does not update beliefs by Bayesian "
        "multiplication when priors are stale; calibration training is "
        "required to restore the posterior probability mapping. "
        "arXiv:1503.04567"
    )

    domain = get_domain("personal_epistemic_v1")
    ontology_copy = {
        "primitives": {k: dict(v) for k, v in domain.ontology["primitives"].items()},
    }

    # Use a temp registry so the demo never pollutes a live log.
    tmp_dir = Path(tempfile.mkdtemp(prefix="neuro_belief_demo_"))
    version_registry.set_registry_path(tmp_dir / "registry.jsonl")
    primitive_feedback.FEEDBACK_PATH = tmp_dir / "feedback.jsonl"
    primitive_feedback.reset_for_tests()
    ontology_path = tmp_dir / "belief_ontology.json"

    print(f"\n  Sandbox dir: {tmp_dir}")
    print(f"  Ingesting 1 doc into Belief OS...\n")

    report = ingest_documents(
        [contradiction],
        ontology=ontology_copy,
        ontology_path=ontology_path,
        golden_cases=list(PERSONAL_EPISTEMIC_GOLDEN_CASES),
        priority_rules_path=PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH,
    )

    print(f"  Documents ingested  : {len(report['ingested'])}")
    print(f"  Merges applied      : {report['merges_applied']}")
    print(f"  Merges reverted     : {report['merges_reverted']}")
    print(f"  Evolution actions   : "
          f"{[e['action'] for e in report['evolutions']]}")

    if ontology_path.exists():
        on_disk = json.loads(ontology_path.read_text())
        for name, primitive in on_disk["primitives"].items():
            sources = primitive.get("sources") or []
            if sources:
                print(f"\n  Mutated primitive   : {name}")
                print(f"    new definition    : {primitive.get('definition')}")
                print(f"    sources accreted  : {len(sources)}")
                print(f"    first source      : {sources[0][:80]}...")


def stage3_llm_upgrade() -> None:
    """Re-run the slang claims with and without the LLM enabled."""
    print("\n" + "=" * 72)
    print("Stage 3 — LLM upgrade (Claude Haiku 4.5)")
    print("=" * 72)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "\n  Skipped: ANTHROPIC_API_KEY not set.\n"
            "  Set the env var to run this stage:\n"
            "    ANTHROPIC_API_KEY=sk-... python examples/06_personal_epistemic_demo.py"
        )
        return

    print("\n  Comparing keyword-only vs. LLM extraction on raw slang.\n")
    print(f"  {'CLAIM':<60s}  {'KEYWORD':<22s}  {'LLM':<22s}")
    print("  " + "-" * 108)

    for claim in SLANG_CLAIMS:
        # Keyword-only
        disable_llm()
        keyword = personal_epistemic_extractor(claim)
        kw_label = keyword["knowledge"].get("mechanism", "unknown")

        # LLM-augmented
        enable_llm(model="claude-haiku-4-5")
        try:
            llm = personal_epistemic_extractor(claim)
            llm_label = llm["knowledge"].get("mechanism", "unknown")
            method = llm["knowledge"].get("extraction_evidence", {}).get("method", "")
            badge = "via LLM" if method == "llm-anthropic" else "via fallback"
        except Exception as exc:  # noqa: BLE001
            llm_label = "ERROR"
            badge = type(exc).__name__
        finally:
            disable_llm()

        truncated = (claim[:57] + "...") if len(claim) > 60 else claim
        print(
            f"  {truncated:<60s}  {kw_label:<22s}  {llm_label} ({badge})"
        )


if __name__ == "__main__":
    stage1_classify()
    stage2_ingest_with_learnback()
    stage3_llm_upgrade()
