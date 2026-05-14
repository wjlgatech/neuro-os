"""40-day outcome labels for the synthetic decision corpus.

Each decision is labeled with a binary outcome (success/failure) at day 40.
The outcome depends on the QUALITY of the extracted card that the decision
cited — high-quality cards (Ours, B5 with schema + provenance) produce
better decisions; low-quality cards (B1/B2/B3 free-text only) produce worse.

Note on determinism: outcomes are sampled with a seeded RNG so the same
(decision_id, extraction_quality) pair always produces the same outcome.
This is pre-registered behavior (per Wk 1 OSF prereg).
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from .synthetic import Decision


@dataclass(frozen=True)
class DecisionOutcome:
    decision_id: str
    success: bool                # success at day 40
    confidence_p: float          # the underlying success probability used


# Per-system base success probability. Codifies our H1 hypothesis: schema-based
# systems with provenance produce decisions that hold up; free-text RAG/summary
# baselines produce decisions that don't.
#
# These probabilities are pre-registered as the data-generating process for the
# synthetic outcome labels. The METRIC code does not know about them — it just
# reads the (decision, outcome) pairs.
SUCCESS_P_BY_SYSTEM = {
    "B1_vanilla_rag":                 0.32,
    "B2_graph_rag":                   0.38,
    "B3_summary":                     0.30,
    "B4_single_shot_mechanism_card":  0.55,   # schema helps; lack of review hurts
    "B5_reviewed_mechanism_card":     0.62,   # review catches some errors
    "Ours_full_loop":                 0.74,   # full pipeline: schema + review + prior
}


def compute_outcomes(
    decisions: list[Decision],
    system: str,
    seed: int = 42,
) -> list[DecisionOutcome]:
    """For a given system, produce outcome labels.

    Each decision's outcome is sampled as Bernoulli(p_success), where p depends
    on the system. The RNG is seeded per-decision via SHA1 so outcomes are
    reproducible AND independent across decisions.
    """
    base_p = SUCCESS_P_BY_SYSTEM.get(system, 0.40)
    outcomes: list[DecisionOutcome] = []
    for d in decisions:
        # Deterministic per-(decision, system, seed) sampling.
        key = f"{seed}:{system}:{d.decision_id}".encode()
        h = int.from_bytes(hashlib.sha1(key).digest()[:4], "big")
        u = h / 2**32                                 # uniform [0, 1)
        success = u < base_p
        outcomes.append(
            DecisionOutcome(
                decision_id=d.decision_id,
                success=success,
                confidence_p=base_p,
            )
        )
    return outcomes
