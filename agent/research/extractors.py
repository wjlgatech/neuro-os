"""Multi-persona extraction with built-in rubric filter.

Five extractor personas — one per Law 8 primitive — each runs the LLM
with a lens-specific system prompt biased toward seeing mechanisms
through that primitive. Run in parallel; merge + dedup at the end.

Each persona's prompt also bakes in the 4-criteria rubric (compression,
transferability, executability, falsifiability) so the LLM filters out
junk mechanisms BEFORE they reach the review queue.

Why this is better than a single extraction pass:
  * Recall: a single prompt has a single bias; 5 lenses surface 5×
    more mechanism types (in practice 1.5-2× since some lenses converge).
  * Precision: the inline rubric filter rejects "X was observed" style
    descriptions at extraction time instead of cluttering the review queue.

Cost: ~5× LLM calls per source. Acceptable for the typical 10-50 paper
corpus (≈ $0.50/paper at gpt-4o-mini). Tune via ``PERSONAS`` if needed.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Persona:
    """A named extraction lens.

    ``lens_description`` is appended to the base system prompt so the
    LLM is primed to see mechanisms through this primitive's frame.
    """
    name: str
    lens_description: str


# Five personas, one per Law 8 primitive. Order is stable so test
# expectations don't depend on dict ordering.
PERSONAS: Tuple[Persona, ...] = (
    Persona(
        name="predictive_processing",
        lens_description=(
            "LENS — Predictive Processing.\n"
            "You see the world as a hierarchy of predictive models that "
            "minimize prediction error. You look for: forward models, "
            "prediction errors as learning signals, top-down expectations "
            "modulating bottom-up sensation, generative models, "
            "free-energy minimization, surprise as a control signal. "
            "Frame every candidate mechanism as: 'what prediction is "
            "being made?', 'what error signal corrects it?', 'what's the "
            "hierarchy?'."
        ),
    ),
    Persona(
        name="hebbian",
        lens_description=(
            "LENS — Hebbian / Associative Learning.\n"
            "You see the world as patterns of co-occurrence that strengthen "
            "or weaken couplings. You look for: 'fire together, wire "
            "together' dynamics, correlation-driven plasticity, weight "
            "updates as a function of pre/post activity, stable attractors "
            "formed by repeated co-activation, decay without rehearsal. "
            "Frame every candidate mechanism as: 'what two things are "
            "becoming correlated?', 'what is the update rule on the "
            "coupling?'."
        ),
    ),
    Persona(
        name="reinforcement_learning",
        lens_description=(
            "LENS — Reinforcement Learning / Value & Policy.\n"
            "You see the world as agents learning policies that maximize "
            "expected reward over time. You look for: reward signals "
            "(dense or sparse), value functions, policy updates, "
            "exploration vs. exploitation, credit assignment, delayed "
            "consequences, temporal-difference errors. Frame every "
            "candidate mechanism as: 'what is being rewarded?', 'what is "
            "the policy update rule?', 'where does the credit-assignment "
            "happen?'."
        ),
    ),
    Persona(
        name="attention",
        lens_description=(
            "LENS — Attention / Selective Routing.\n"
            "You see the world as a bottleneck-and-router system: limited "
            "capacity is allocated to inputs that matter most. You look "
            "for: gating, salience, top-down vs. bottom-up biasing, "
            "winner-take-all dynamics, capacity limits, query-key matching, "
            "context modulating which features survive. Frame every "
            "candidate mechanism as: 'what is competing for attention?', "
            "'what wins?', 'what is suppressed?', 'what controls the gate?'."
        ),
    ),
    Persona(
        name="hierarchical_abstraction",
        lens_description=(
            "LENS — Hierarchical Abstraction.\n"
            "You see the world as nested levels of representation, each "
            "compressing the one below into invariants. You look for: "
            "compositionality, layered features (low → high), abstraction "
            "as compression, generalization across instances, the bridge "
            "between concrete observations and abstract rules. Frame "
            "every candidate mechanism as: 'what is being compressed?', "
            "'what invariant survives across instances?', 'what level "
            "of the hierarchy does this operate at?'."
        ),
    ),
)


# The 4-criteria filter — appended to every persona's system prompt so
# the LLM self-rejects mechanisms that fail at extraction time, before
# they ever reach the review queue. Move #5 of the alignment-audit
# follow-up.
EVAL_FILTER = """
QUALITY FILTER — apply to EVERY candidate mechanism BEFORE emitting it.
Emit ONLY mechanisms that satisfy all four:

  1. COMPRESSION
     The mechanism compresses many observations into one rule.
     REJECT: "The authors observed that X happens in this dataset."
     KEEP:   "X happens whenever Y because of underlying force Z."

  2. TRANSFERABILITY
     The rule generalizes beyond the specific paper / dataset / model.
     REJECT: "BERT-base achieves 89.2 F1 on SQuAD."
     KEEP:   "Self-attention enables long-range dependency capture in
             any sequence model with enough heads."

  3. EXECUTABILITY
     The mechanism is testable, implementable, or practiceable.
     REJECT: "Consciousness emerges from sufficient complexity."
     KEEP:   "Gradient descent converges to a local minimum at O(1/k)
             under convexity."

  4. FALSIFIABILITY
     A specific observation could prove the mechanism wrong.
     REJECT: "Brains are complex systems."
     KEEP:   "Removing layer N from this architecture drops downstream
             accuracy by ≥ 10%."

If a candidate fails ANY of these four, do NOT emit it. Emit fewer
high-quality mechanisms rather than more low-quality ones. It is
correct and expected to emit 0 candidates from a descriptive paper.
"""


def build_persona_prompt(persona: Persona, base_prompt: str) -> str:
    """Compose the persona's full system prompt: base + lens + filter."""
    return f"{base_prompt}\n\n{persona.lens_description}\n\n{EVAL_FILTER}"


LLMCallable = Callable[[str, str], List[Dict]]


def _normalize_for_hash(s: str) -> str:
    """Lowercase + collapse whitespace + strip punctuation. Identical
    normalization to ``agent.research.proposals._normalize_text`` (keeping
    them in sync is a unit-tested invariant).
    """
    import re as _re
    return _re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _row_hash(row: Dict) -> str:
    """Stable short hash of (mechanism, invariant). Used to dedup raw
    LLM outputs ACROSS persona calls before they're materialized as
    MechanismCardProposal rows. Matches the wire-level hash format that
    ``compute_mechanism_hash`` exposes downstream."""
    import hashlib as _hl
    payload = (
        _normalize_for_hash(str(row.get("mechanism", "")))
        + " || "
        + _normalize_for_hash(str(row.get("invariant", "")))
    )
    return _hl.sha256(payload.encode("utf-8")).hexdigest()[:16]


def extract_multi_persona(
    *,
    llm_fn: LLMCallable,
    base_prompt: str,
    user_message: str,
    personas: Tuple[Persona, ...] = PERSONAS,
    max_workers: Optional[int] = None,
) -> Tuple[List[Dict], Dict[str, int]]:
    """Run every persona's prompt against ``llm_fn`` in parallel and
    return the deduped union of raw rows.

    Each persona's failure (network, JSON parse, timeout) is isolated:
    its results are treated as an empty list, the run continues.

    Returns:
        (rows, stats) where:
          rows = deduped list of raw LLM row dicts (one per unique
                 mechanism-hash across all personas).
          stats = {persona_name: count_emitted} for telemetry.
    """
    if not personas:
        return [], {}
    workers = max_workers or len(personas)

    def _run_one(persona: Persona) -> Tuple[str, List[Dict]]:
        prompt = build_persona_prompt(persona, base_prompt)
        try:
            rows = llm_fn(prompt, user_message)
        except Exception as e:
            logger.warning(
                "extract_multi_persona: persona %r failed (%s); "
                "treating as empty result",
                persona.name, e,
            )
            return persona.name, []
        if not isinstance(rows, list):
            return persona.name, []
        return persona.name, [r for r in rows if isinstance(r, dict)]

    with ThreadPoolExecutor(max_workers=workers) as ex:
        per_persona = list(ex.map(_run_one, personas))

    seen_hashes: Dict[str, str] = {}  # hash -> persona that won
    merged: List[Dict] = []
    stats: Dict[str, int] = {p.name: 0 for p in personas}

    for persona_name, rows in per_persona:
        for row in rows:
            h = _row_hash(row)
            if h in seen_hashes:
                continue
            seen_hashes[h] = persona_name
            stats[persona_name] += 1
            # Tag the row with the persona that surfaced it — surfaces in
            # the proposal's `reasoning` field downstream for audit.
            row = dict(row)
            existing_reasoning = str(row.get("reasoning", "")).strip()
            row["reasoning"] = (
                f"[lens: {persona_name}] "
                + (existing_reasoning or "No reasoning supplied.")
            )
            merged.append(row)

    return merged, stats


__all__ = [
    "Persona",
    "PERSONAS",
    "EVAL_FILTER",
    "build_persona_prompt",
    "extract_multi_persona",
]
