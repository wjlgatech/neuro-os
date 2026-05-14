"""H4 — Provenance audit pass rate.

Per Law 1, every extracted MechanismCard's source_excerpt MUST appear verbatim
(after light normalization) in the paper. We check this with a substring match
that was already implemented in extractors.base.verify_excerpt_in_text.

By construction:
  - B1/B2/B3 produce no source_excerpt → 0% pass rate
  - B4/B5/Ours produce source_excerpt → up to 100% pass rate, depending on
    whether the LLM actually copied verbatim or paraphrased
"""

from __future__ import annotations


def provenance_audit_pass_rate(extractions: list) -> dict:
    n_total = len(extractions)
    n_attempted = sum(1 for e in extractions if e.source_excerpt)
    n_verified = sum(1 for e in extractions if e.pinned_provenance)

    return {
        "n_total": n_total,
        "n_with_excerpt_attempt": n_attempted,
        "n_verified_in_paper": n_verified,
        "audit_pass_rate": n_verified / n_total if n_total else 0.0,
        # The strict interpretation: of cards that CLAIM provenance, how many actually verify?
        "audit_strict_pass_rate": (
            n_verified / n_attempted if n_attempted else 0.0
        ),
    }
