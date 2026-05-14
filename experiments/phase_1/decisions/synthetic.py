"""Synthetic decision corpus generator.

A "decision" is a downstream act (e.g. an investment thesis, a founder-loop
drift card) that CITES one or more extracted mechanism cards. We generate
50 deterministic synthetic decisions spanning two verticals (investment,
founder-loop) so the survival metric and transferability lift have something
to measure. Pre-registered ratio: 70% in-vertical, 30% cross-vertical.

Determinism: seed=42. Same seed produces same corpus. Documented for the
OSF pre-registration (Wk 1).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from typing import Literal


@dataclass(frozen=True)
class Decision:
    decision_id: str
    vertical: Literal["investment", "founder-loop"]   # which downstream domain
    cited_paper_id: str                                # which paper's card this decision uses
    citation_aspect: Literal["mechanism", "invariant", "prediction", "failure_mode"]
    week: int                                          # 1..6 (40-day window with weekly granularity)
    is_cross_vertical: bool                            # paper extracted for vertical A, cited in vertical B


VERTICAL_BIAS = {
    # Which paper family is "native" to which vertical.
    "CL": "founder-loop",          # protect-load-bearing-routines maps to drift management
    "world-model": "investment",   # imagined rollouts map to thesis testing
    "embodied-AI": "founder-loop", # operational primitives
    "eval": "investment",          # methodology orientation
}

CORPUS_FAMILIES = {
    "ewc-kirkpatrick-2017": "CL",
    "world-models-ha-schmidhuber-2018": "world-model",
    "latent-replay-pellegrini-2019": "CL",
    "gem-lopez-paz-2017": "CL",
    "progressive-networks-rusu-2016": "CL",
    "dreamer-v3-hafner-2023": "world-model",
    "iris-micheli-2023": "world-model",
    "rt2-brohan-2023": "embodied-AI",
    "open-x-embodiment-2023": "embodied-AI",
    "helm-liang-2022": "eval",
}


def generate_decision_corpus(
    n_decisions: int = 50,
    cross_vertical_fraction: float = 0.30,
    seed: int = 42,
) -> list[Decision]:
    """Deterministic synthesis. Same seed → same corpus, by design."""
    rng = random.Random(seed)
    paper_ids = list(CORPUS_FAMILIES.keys())
    aspects = ["mechanism", "invariant", "prediction", "failure_mode"]

    n_cross = int(round(n_decisions * cross_vertical_fraction))
    n_native = n_decisions - n_cross

    decisions: list[Decision] = []

    for i in range(n_native):
        paper_id = rng.choice(paper_ids)
        native_vertical = VERTICAL_BIAS[CORPUS_FAMILIES[paper_id]]
        decisions.append(
            Decision(
                decision_id=f"d{i:03d}_native",
                vertical=native_vertical,                      # type: ignore[arg-type]
                cited_paper_id=paper_id,
                citation_aspect=rng.choice(aspects),           # type: ignore[arg-type]
                week=rng.randint(1, 6),
                is_cross_vertical=False,
            )
        )

    for i in range(n_cross):
        paper_id = rng.choice(paper_ids)
        native_vertical = VERTICAL_BIAS[CORPUS_FAMILIES[paper_id]]
        cross_vertical = "founder-loop" if native_vertical == "investment" else "investment"
        decisions.append(
            Decision(
                decision_id=f"d{i:03d}_cross",
                vertical=cross_vertical,                       # type: ignore[arg-type]
                cited_paper_id=paper_id,
                citation_aspect=rng.choice(aspects),           # type: ignore[arg-type]
                week=rng.randint(1, 6),
                is_cross_vertical=True,
            )
        )

    rng.shuffle(decisions)
    return decisions


def decisions_to_jsonable(decisions: list[Decision]) -> list[dict]:
    return [asdict(d) for d in decisions]
