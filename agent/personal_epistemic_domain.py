"""
``personal_epistemic_v1`` — Belief OS domain for Neuro-OS.

A domain that points the L1 knowledge loop at *reasoning patterns*
(Bayesian updating, base-rate reasoning, falsifiability, expected value,
second-order thinking, survivorship bias) instead of neuroscience
mechanisms. Same machinery, different ontology + golden cases + priority
rules.

Read-only for v1: ``mutable_paths=[]`` so the L2 self-modification loop
short-circuits. The priority-rules file lives at
``agent/data/personal_epistemic_priority_rules.json`` and is plumbed
through ``run_pipeline(..., priority_rules_path=...)``.

Register and use::

    import agent.personal_epistemic_domain  # registers on import
    from agent.domains import get_domain
    domain = get_domain("personal_epistemic_v1")
    result = domain.extractor("The reference class is dropouts who tried.")
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agent.domains import (
    Domain,
    import_smoke_validator,
    list_domains,
    register_domain,
)
from agent.ingestion_pipeline import run_pipeline


# ---------------------------------------------------------------------------
# Optional LLM extractor — set via ``enable_llm()`` (v1.2 upgrade).
# ---------------------------------------------------------------------------

# When non-None, ``personal_epistemic_extractor`` tries the LLM first and
# falls back to keyword routing if the LLM returns 'unknown' or errors.
# Default ``None`` keeps every existing test deterministic and offline.
_llm_fn: Optional[Callable[[str], Dict[str, Any]]] = None


def enable_llm(
    *,
    model: str = "claude-haiku-4-5",
    api_key: Optional[str] = None,
    enable_caching: bool = True,
) -> None:
    """Enable the LLM-backed extractor for this domain.

    Subsequent calls to ``personal_epistemic_extractor()`` will try the
    LLM first and fall back to keyword routing only when the LLM returns
    'unknown' or errors. Calling this without a configured
    ``ANTHROPIC_API_KEY`` (or explicit ``api_key``) raises immediately
    rather than silently falling back, so misconfiguration is loud.
    """
    global _llm_fn
    from agent.llm_extractors import make_anthropic_extractor

    _llm_fn = make_anthropic_extractor(
        model=model,
        api_key=api_key,
        enable_caching=enable_caching,
    )


def disable_llm() -> None:
    """Reset to keyword-only routing (used by tests + the UI toggle)."""
    global _llm_fn
    _llm_fn = None


def set_llm_fn(fn: Optional[Callable[[str], Dict[str, Any]]]) -> None:
    """Inject a custom ``llm_fn`` directly. Used by tests to mock the SDK."""
    global _llm_fn
    _llm_fn = fn


PERSONAL_EPISTEMIC_PRIORITY_RULES_RELATIVE = (
    "agent/data/personal_epistemic_priority_rules.json"
)
PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH = (
    Path(__file__).parent / "data" / "personal_epistemic_priority_rules.json"
)


PERSONAL_EPISTEMIC_PRIMITIVES: Dict[str, Dict[str, Any]] = {
    "bayesian_updating": {
        "definition": (
            "Beliefs are probabilistic; the brain updates them by multiplying "
            "the prior by the likelihood of new evidence."
        ),
        "aliases": [
            "bayesian updating",
            "bayes",
            "prior probability",
            "posterior",
            "likelihood ratio",
            "update on",
            "calibration",
        ],
        "relations": ["base_rate_reasoning", "falsifiability"],
    },
    "base_rate_reasoning": {
        "definition": (
            "Anchor estimates to the prior frequency of the outcome in the "
            "relevant reference class before updating on case-specific evidence."
        ),
        "aliases": [
            "base rate",
            "base-rate",
            "reference class",
            "conjunction fallacy",
            "representativeness",
            "prior frequency",
        ],
        "relations": ["bayesian_updating", "survivorship_bias"],
    },
    "falsifiability": {
        "definition": (
            "A belief is real knowledge only if it forbids something — if no "
            "observation could reduce confidence in it, it is not a claim about the world."
        ),
        "aliases": [
            "falsifiability",
            "falsifiable",
            "would falsify",
            "forbids",
            "change my mind",
            "unfalsifiable",
            "popperian",
        ],
        "relations": ["bayesian_updating", "second_order_thinking"],
    },
    "expected_value": {
        "definition": (
            "The rational value of an uncertain decision is the probability-weighted "
            "sum of its outcomes; vivid stories about a single outcome should not dominate."
        ),
        "aliases": [
            "expected value",
            "ev calculation",
            "probability-weighted",
            "probability weighted",
            "kelly criterion",
            "tail risk",
            "ruin risk",
        ],
        "relations": ["bayesian_updating", "second_order_thinking"],
    },
    "second_order_thinking": {
        "definition": (
            "A decision's true value is the sum of its first-order effect and the "
            "downstream effects it triggers; ask 'and then what?' until the answer stabilizes."
        ),
        "aliases": [
            "second-order",
            "second order",
            "and then what",
            "downstream effect",
            "downstream effects",
            "systemic effect",
            "feedback loop",
        ],
        "relations": ["expected_value", "falsifiability"],
    },
    "survivorship_bias": {
        "definition": (
            "The visible sample is the population filtered by selection — failures are "
            "invisible, so patterns in survivors must be discounted by the selection rate."
        ),
        "aliases": [
            "survivorship bias",
            "survivor bias",
            "selection effect",
            "selection bias",
            "filtered sample",
            "where are the missing",
            "denominator",
        ],
        "relations": ["base_rate_reasoning", "bayesian_updating"],
    },
}


PERSONAL_EPISTEMIC_GOLDEN_CASES: List[Dict[str, str]] = [
    {
        "text": (
            "Linda is 31, a philosophy major, active in social-justice causes. "
            "Most respondents incorrectly rank her as more likely to be a feminist "
            "bank teller than a bank teller — a conjunction fallacy that ignores "
            "the base rate of bank tellers."
        ),
        "expected_mechanism": "base_rate_reasoning",
    },
    {
        "text": (
            "A medical test is 99% accurate; disease prevalence is 0.1%. Even after "
            "a positive result, the posterior probability of disease is only ~9% "
            "because the prior probability dominates the likelihood ratio."
        ),
        "expected_mechanism": "bayesian_updating",
    },
    {
        "text": (
            "The claim 'markets will be volatile' forbids no observation, so it is "
            "unfalsifiable; it cannot be reduced in confidence by any evidence."
        ),
        "expected_mechanism": "falsifiability",
    },
    {
        "text": (
            "A 1% chance of winning $1M has the same expected value as a 99% chance "
            "of winning $10,101 — vivid single outcomes should not dominate the "
            "probability-weighted sum."
        ),
        "expected_mechanism": "expected_value",
    },
    {
        "text": (
            "Lowering price increases sales in the first order, but competitors match, "
            "customers learn to wait for sales, and brand drifts down-market — second-order "
            "effects often dominate the first-order win."
        ),
        "expected_mechanism": "second_order_thinking",
    },
    {
        "text": (
            "Successful founders dropped out of college, so dropouts succeed. "
            "The visible sample is filtered by survival; the denominator of dropouts "
            "who tried and failed is invisible — classic survivorship bias."
        ),
        "expected_mechanism": "survivorship_bias",
    },
]


def _ontology() -> Dict[str, Any]:
    return {
        "primitives": {k: dict(v) for k, v in PERSONAL_EPISTEMIC_PRIMITIVES.items()},
        "source_count": 0,
        "relation_count": sum(
            len(p.get("relations", [])) for p in PERSONAL_EPISTEMIC_PRIMITIVES.values()
        ),
    }


def personal_epistemic_extractor(text: str) -> Dict[str, Any]:
    """Classify text with the LLM (if enabled) then keyword routing.

    Behaviour:
      * If ``_llm_fn`` is configured (via ``enable_llm()`` /
        ``set_llm_fn()``), run the pipeline through the LLM first. If
        the LLM returns a known primitive, that result is final.
      * If the LLM returns ``'unknown'`` (or its underlying call errored
        and our wrapper turned the error into 'unknown'), retry the
        pipeline with keyword routing — many cases the LLM legitimately
        misses still match a priority rule.
      * If ``_llm_fn`` is ``None`` (default), use keyword routing only.
        This is the original v1.1 behaviour and keeps every existing
        test deterministic and offline.

    The chosen path is recorded in
    ``result['knowledge']['evidence']['method']`` (``llm-anthropic``,
    ``llm-error``, or ``offline-keyword``) so callers can audit which
    leg of the chain produced the answer.
    """
    ontology = _ontology()

    if _llm_fn is not None:
        llm_result = run_pipeline(
            text,
            ontology=ontology,
            llm_fn=_llm_fn,
            priority_rules_path=PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH,
        )
        if llm_result["knowledge"].get("mechanism") != "unknown":
            return llm_result
        # LLM came back 'unknown' or errored — try the deterministic
        # keyword path before giving up. Many real claims don't trip the
        # LLM but do match a priority rule, and vice versa, so the chain
        # has noticeably better coverage than either alone.

    return run_pipeline(
        text,
        ontology=ontology,
        priority_rules_path=PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH,
    )


_PERSONAL_EPISTEMIC_V1 = Domain(
    name="personal_epistemic_v1",
    ontology=_ontology(),
    golden_cases=list(PERSONAL_EPISTEMIC_GOLDEN_CASES),
    extractor=personal_epistemic_extractor,
    # v1 is read-only: no L2 self-modification, so import-smoke is enough.
    validators=[import_smoke_validator],
    mutable_paths=[],
)


if "personal_epistemic_v1" not in list_domains():
    register_domain(_PERSONAL_EPISTEMIC_V1)


__all__ = [
    "PERSONAL_EPISTEMIC_PRIMITIVES",
    "PERSONAL_EPISTEMIC_GOLDEN_CASES",
    "PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH",
    "PERSONAL_EPISTEMIC_PRIORITY_RULES_RELATIVE",
    "personal_epistemic_extractor",
]
