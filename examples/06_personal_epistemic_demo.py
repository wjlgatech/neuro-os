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

Run::

    python examples/06_personal_epistemic_demo.py
"""
from __future__ import annotations

import json
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
    personal_epistemic_extractor,
)


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


if __name__ == "__main__":
    stage1_classify()
    stage2_ingest_with_learnback()
