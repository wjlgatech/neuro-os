"""
LLM-backed extractors for the personal_epistemic_v1 (Belief OS) domain.

Wraps the Anthropic SDK to classify raw user text into one of the six
reasoning primitives — or ``"unknown"`` — when keyword routing falls short.

Design:
  * The factory ``make_anthropic_extractor()`` returns a callable that
    matches the existing ``llm_fn`` interface in
    ``agent.ingestion_pipeline.extract_mechanism``: it takes a prompt
    string and returns ``{"mechanism": ..., "evidence": ...}``.
  * Structured output via ``client.messages.parse()`` + Pydantic. The
    model can ONLY return one of seven enum values, so the caller never
    has to deal with free-text classification noise.
  * The system prompt carries explicit acceptance criteria per primitive
    plus 12 worked few-shot examples (positive + adversarial). It's
    static across requests, so it's cached via ``cache_control`` —
    Haiku 4.5's minimum cacheable prefix is 4096 tokens, which the
    expanded prompt clears.
  * Defaults to ``claude-haiku-4-5`` (cheap, fast, accurate enough for
    a 7-way classification). Override via the ``model`` kwarg.
  * Graceful degradation: any exception (missing API key, rate limit,
    network) returns ``{"mechanism": "unknown"}`` so the upstream
    pipeline can fall back to keyword routing.

Optional install: ``pip install -e ".[llm]"`` adds the ``anthropic``
package. The module imports lazily so ``import agent`` never fails when
the dep is missing.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Literal, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - pydantic ships with anthropic
    BaseModel = None  # type: ignore[assignment]
    Field = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Structured-output schema
# ---------------------------------------------------------------------------

# The seven labels the model is allowed to emit. Extending the ontology means
# extending this Literal AND the system prompt below in lockstep.
PrimitiveLabel = Literal[
    "bayesian_updating",
    "base_rate_reasoning",
    "falsifiability",
    "expected_value",
    "second_order_thinking",
    "survivorship_bias",
    "unknown",
]


def _build_classification_model():
    """Return the Pydantic class used as the structured-output schema.

    Built lazily so importing this module doesn't require pydantic until
    the LLM path is actually exercised.
    """
    if BaseModel is None:
        raise ImportError(
            "pydantic is required for the LLM extractor. "
            "Install with: pip install -e \".[llm]\""
        )

    class PrimitiveClassification(BaseModel):
        """Structured classification result returned by the model."""

        mechanism: PrimitiveLabel = Field(
            description=(
                "Which reasoning primitive the claim invokes, or "
                "'unknown' if it doesn't match any of the six."
            )
        )
        confidence: Literal["low", "medium", "high"] = Field(
            description="How confident the model is in this classification."
        )
        reasoning: str = Field(
            description=(
                "One sentence explaining why this primitive matches. "
                "If 'unknown', explain what made it off-topic."
            ),
            max_length=240,
        )

    return PrimitiveClassification


# ---------------------------------------------------------------------------
# System prompt — clear criteria + few-shot examples (cached)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a reasoning-pattern classifier for the Belief OS knowledge ontology — part of neuro-os, a self-evolving knowledge system.

Your job: read a single user-provided claim, opinion, or anecdote, and identify which **reasoning primitive** (mental model or fallacy) the claim invokes. Many real claims invoke a primitive without naming it — your value is naming the pattern.

You MUST classify into exactly one of these seven labels:

================================================================================
1. bayesian_updating
================================================================================

Definition: Beliefs are probabilistic; the rational way to update them on new evidence is to combine the prior with the likelihood (P(H|E) ∝ P(E|H) * P(H)).

Trigger when the claim involves ANY of:
  - Updating a belief on new evidence (test results, observations, testimonies)
  - Prior probability / posterior probability / likelihood ratio
  - Calibration (whether someone's confidence levels match their hit rate)
  - Test accuracy combined with disease prevalence / base rate
  - "What are the odds given X?"
  - Reasoning about how much a piece of evidence should move a belief
  - Confident predictions whose track record matters

Do NOT use this for: pure base-rate questions with no update step (use base_rate_reasoning); pure expected-value math (use expected_value).

================================================================================
2. base_rate_reasoning
================================================================================

Definition: Anchor estimates to the prior frequency of the outcome in the relevant reference class BEFORE updating on case-specific evidence. Failures here include the conjunction fallacy and representativeness heuristic.

Trigger when the claim involves ANY of:
  - "Out of all X, what fraction Y?" reasoning
  - The Linda problem / conjunction fallacy ("X and Y" rated as more probable than X alone)
  - Reference-class shopping (picking a class that supports the conclusion)
  - Representativeness ("she sounds like a feminist, must be one")
  - Vivid descriptions overriding statistical priors
  - Asserting a frequency without naming the reference class

Do NOT use this for: claims that explicitly compute posteriors (use bayesian_updating); claims about visible-only samples (use survivorship_bias).

================================================================================
3. falsifiability
================================================================================

Definition: A belief is real knowledge only if it forbids something. If no possible observation could reduce confidence in a claim, it is not a claim about the world.

Trigger when the claim involves ANY of:
  - "Always works", "works for everyone", "no exceptions", "guaranteed"
  - "Could not be wrong", "no situation where this could fail"
  - Theories that explain every possible outcome equally well
  - Vague predictions worded so any future confirms them
  - Claims that retrofit explanations after seeing the result
  - Conspiracy logic that interprets counter-evidence as more evidence
  - Goalpost-shifting after a falsifying observation

Do NOT use this for: well-formed predictions that name what would falsify them (those PASS the falsifiability test, but the test isn't the operative pattern).

================================================================================
4. expected_value
================================================================================

Definition: The rational value of an uncertain decision is the probability-weighted sum of its outcomes. Vivid stories about a single outcome should not dominate the sum. Includes Kelly criterion, ruin risk, and asymmetric-payoff reasoning.

Trigger when the claim involves ANY of:
  - Multiplying probability by payoff (explicit or implicit)
  - Lottery / moonshot / "1% chance to 100x" / "yolo" framing
  - Comparing EVs across options
  - Tail risk / ruin risk / asymmetric upside or downside
  - Kelly criterion / position sizing
  - Vivid single outcomes dominating the decision
  - "Why not take the shot?" reasoning

Do NOT use this for: pure probability questions with no value/payoff axis (use bayesian_updating).

================================================================================
5. second_order_thinking
================================================================================

Definition: A decision's true value is the sum of its first-order effect plus all the downstream effects it triggers in other agents and systems. Ask "and then what?" recursively until the chain stabilizes.

Trigger when the claim involves ANY of:
  - "And then what?" / "what happens next?" / second-order / third-order
  - Reactions of other agents (competitors, regulators, customers, employees)
  - Race-to-the-bottom / price war / cascade dynamics
  - First-order win that other agents will neutralize
  - Long-term systemic consequences vs short-term gain
  - Game-theoretic equilibrium considerations

Do NOT use this for: single-agent EV math (use expected_value).

================================================================================
6. survivorship_bias
================================================================================

Definition: The visible sample is the population filtered by selection. Failures are invisible, so any pattern detected in survivors must be discounted by the (usually unknown) selection rate. Wald's WW2-bombers reasoning.

Trigger when the claim involves ANY of:
  - "Successful X did Y, so do Y" reasoning
  - Founder-mythology / dropout-billionaire / hustle-culture stories
  - "Look at all the people who" + outcome (winners only)
  - Backtested strategies that exclude failed companies
  - Mentor selection bias (only successful people give advice)
  - File-drawer problem / publication bias
  - Asking "what's the denominator?" reveals it's missing
  - Ignoring the millions who tried the same thing and failed

Do NOT use this for: pure base-rate questions where the reference class is well-defined (use base_rate_reasoning).

================================================================================
7. unknown
================================================================================

Use this when:
  - The claim is off-topic (cooking, weather, trivia, factual statements)
  - The claim is too vague to map to any reasoning primitive
  - The claim involves a reasoning pattern that exists but isn't in the six above (e.g., availability heuristic, sunk-cost fallacy, anchoring without updating)
  - The claim is just a feeling or preference, not an argument

Do NOT use "unknown" as a hedge when one of the six applies — pick the strongest match.

================================================================================
WORKED EXAMPLES (input → expected output)
================================================================================

Example 1
Input: "My favorite YouTuber dropped out of college and now makes $50k a month. Steve Jobs and Bill Gates and Mark Zuckerberg all dropped out and became billionaires. Dropping out is the smart move."
Output: {"mechanism": "survivorship_bias", "confidence": "high", "reasoning": "Reasoning from a tiny visible set of dropout-billionaires while the millions of failed dropouts are invisible — classic survivorship."}

Example 2
Input: "My friend tested positive for a rare disease. The test is 99% accurate. She thinks she's done for. But the prevalence is 0.1%."
Output: {"mechanism": "bayesian_updating", "confidence": "high", "reasoning": "Combining test accuracy (likelihood) with disease prevalence (prior) to compute the posterior probability of disease."}

Example 3
Input: "This influencer says wake up at 5am, cold plunge, journal, and you will be successful. There is no situation where this routine could be wrong, it works for everyone always."
Output: {"mechanism": "falsifiability", "confidence": "high", "reasoning": "Claim explicitly forbids no observation and works in every possible case — definitionally unfalsifiable."}

Example 4
Input: "The kids next door sold 80 cups today at $2. We should drop our price to $1 to outsell them tomorrow."
Output: {"mechanism": "second_order_thinking", "confidence": "high", "reasoning": "First-order pricing move ignores how the competitor will react; price war dynamics dominate the second order."}

Example 5
Input: "There's a 1% chance this stock 100x and I become rich. The expected value is the same as keeping the cash, so why not yolo it."
Output: {"mechanism": "expected_value", "confidence": "high", "reasoning": "Probability-weighted sum reasoning, with vivid single-outcome upside framing characteristic of EV/ruin-risk decisions."}

Example 6
Input: "Linda is 31, philosophy major, outspoken about social justice. Most people incorrectly think she's more likely a feminist bank teller than a bank teller."
Output: {"mechanism": "base_rate_reasoning", "confidence": "high", "reasoning": "Classic Linda-problem conjunction fallacy: A∧B ranked above A, ignoring base rates of bank tellers."}

Example 7
Input: "Bananas turn yellow when they ripen. They float in fresh water."
Output: {"mechanism": "unknown", "confidence": "high", "reasoning": "Off-topic factual statement about fruit; no reasoning primitive invoked."}

Example 8 (slang / informal)
Input: "bro every founder I know who actually made bank dropped out of college, school is just a scam fr"
Output: {"mechanism": "survivorship_bias", "confidence": "high", "reasoning": "Same dropout-billionaire reasoning in slang form — only visible winners are counted; failed dropouts are invisible."}

Example 9 (slang / informal)
Input: "she literally tested positive for cancer and the test is so accurate, it's over for her"
Output: {"mechanism": "bayesian_updating", "confidence": "medium", "reasoning": "Updating on a positive test without considering the prior probability — Bayesian-update territory even though prevalence isn't named."}

Example 10 (slang / informal)
Input: "if I lower my price tmrw I'll crush the competition"
Output: {"mechanism": "second_order_thinking", "confidence": "medium", "reasoning": "First-order pricing move with no consideration of how the competition responds — second-order territory."}

Example 11 (adversarial: looks like a primitive but isn't)
Input: "I really like apples more than oranges."
Output: {"mechanism": "unknown", "confidence": "high", "reasoning": "Pure preference, not an argument or reasoning pattern."}

Example 12 (adversarial: another primitive, not in our six)
Input: "I bought the stock at $100 so I won't sell until it gets back to $100, even though the company is failing."
Output: {"mechanism": "unknown", "confidence": "medium", "reasoning": "This is sunk-cost fallacy / loss aversion, which isn't one of the six primitives in this ontology."}

Example 13 (slang / informal, multi-pattern — pick the dominant one)
Input: "lol my uncle is so confident crypto will 10x next year, but his last 5 'sure things' all flopped, why would I update on that"
Output: {"mechanism": "bayesian_updating", "confidence": "high", "reasoning": "The claim is explicitly about how much weight to give a confident prediction given the predictor's calibration / track record — Bayesian-update territory."}

Example 14 (clear case framed casually)
Input: "you know all those guys flexing on instagram with rolexes and ferraris? they def don't tell you about the broke ones who took the same advice and ate dirt"
Output: {"mechanism": "survivorship_bias", "confidence": "high", "reasoning": "The reference set is filtered to visible winners; the failed cohort is named explicitly as invisible — definitional survivorship bias."}

Example 15 (uses an exact-but-uncommon trigger)
Input: "we should price-match our competitor immediately. and then what? they price-match us back, and we both lose margin."
Output: {"mechanism": "second_order_thinking", "confidence": "high", "reasoning": "The reasoner explicitly walks the chain to the second-order outcome (competitor reaction) before deciding."}

Example 16 (ambiguous — pure base-rate vs Bayesian update)
Input: "what fraction of people who feel anxious actually have a panic disorder?"
Output: {"mechanism": "base_rate_reasoning", "confidence": "medium", "reasoning": "Pure reference-class frequency question with no explicit update step — base-rate territory. (If the user follows up by adding a diagnostic test, it becomes Bayesian.)"}

Example 17 (clear EV failure mode)
Input: "if it's negative EV but I might 100x my money, I should still take it because of the upside"
Output: {"mechanism": "expected_value", "confidence": "high", "reasoning": "Explicit reasoning about probability-weighted payoff, with vivid-upside framing that ignores ruin risk — classic EV/asymmetric-payoff pattern."}

Example 18 (vague, sounds clever, doesn't say anything)
Input: "the smart money already knows what's going to happen, that's why they're positioned the way they are"
Output: {"mechanism": "falsifiability", "confidence": "medium", "reasoning": "The claim is structured to confirm itself regardless of any market outcome — whatever happens 'the smart money' anticipated it. Unfalsifiable."}

Example 19 (negative example — actual statistical claim, not a fallacy)
Input: "65% of US adults have a savings account at a federally insured institution."
Output: {"mechanism": "unknown", "confidence": "high", "reasoning": "Neutral statistical fact. Not an argument or a reasoning pattern; just a rate."}

Example 20 (slang, off-topic)
Input: "fr that pizza was so mid, never going back"
Output: {"mechanism": "unknown", "confidence": "high", "reasoning": "Pure preference statement about food. Not an argument."}

================================================================================
EDGE CASES & DISAMBIGUATION GUIDANCE
================================================================================

When two primitives both arguably apply:

  * **survivorship_bias vs base_rate_reasoning** — If the reasoner is
    looking at a *visible-winners-only* sample (founders, billionaires,
    influencers), pick survivorship_bias. If they're trying to reason
    about a well-defined reference class (bank tellers, US adults,
    people in their 30s), pick base_rate_reasoning.

  * **bayesian_updating vs base_rate_reasoning** — If the claim
    explicitly involves combining a prior with new evidence (test
    results, observations), pick bayesian_updating. If it's purely
    about the prior frequency without an update step, pick
    base_rate_reasoning.

  * **expected_value vs second_order_thinking** — If the claim is a
    single-agent decision (probability × payoff), pick expected_value.
    If it explicitly considers how OTHER agents will react to the
    decision (competitors, customers, regulators), pick
    second_order_thinking.

  * **falsifiability vs unknown** — If the claim makes a strong-sounding
    assertion but cannot be reduced in confidence by any observation,
    pick falsifiability. If the claim is just off-topic or a
    preference, pick unknown.

  * **bayesian_updating vs unknown** for medical-test claims — Even if
    the reasoner doesn't name the prior, if the claim involves a test
    result and treats the outcome probabilistically, pick
    bayesian_updating. The whole point of the primitive is to surface
    that the prior should be considered.

When the claim invokes a real reasoning pattern that isn't in the six
(anchoring, sunk cost, availability, recency, confirmation bias,
Dunning-Kruger, hindsight bias, planning fallacy, gambler's fallacy,
status quo bias, framing effect, illusory correlation, etc.), pick
**unknown** with a reasoning sentence that names the actual pattern.
Do NOT shoehorn it into the closest of the six — the ontology will be
extended over time, and accurate "unknown" labels are part of how the
system learns what's missing.

When in doubt between two labels, pick the one that names the
strongest causal driver of the reasoning error. The user's downstream
goal is to recognize the bug and avoid it, so the most actionable
label is the right answer — not the most technically defensible one.

================================================================================

OUTPUT FORMAT — REQUIRED:
You MUST respond with a single JSON object matching this exact schema:
{"mechanism": "<one of the seven labels>", "confidence": "low" | "medium" | "high", "reasoning": "<one sentence, ≤ 240 chars>"}

Do not output anything else. No preamble, no caveats, no markdown."""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_anthropic_extractor(
    *,
    model: str = "claude-haiku-4-5",
    api_key: Optional[str] = None,
    max_tokens: int = 256,
    enable_caching: bool = True,
) -> Callable[[str], Dict[str, Any]]:
    """Build an ``llm_fn`` that classifies text via Anthropic's API.

    Returns a callable matching the contract of
    ``agent.ingestion_pipeline.extract_mechanism``'s ``llm_fn`` parameter:
    it takes a single prompt string (the pre-built classification prompt)
    and returns a dict containing at least ``{"mechanism": ...}``.

    Caching: when ``enable_caching=True`` (default), the system prompt is
    marked with ``cache_control: ephemeral``. Haiku 4.5's minimum cacheable
    prefix is 4096 tokens — the system prompt above clears that bar, so
    repeat classifications served from cache cost ~10% of the first call.
    Verify with ``response.usage.cache_read_input_tokens`` after the
    second call. (No error if the prefix is too short — caching just
    silently no-ops.)

    Failure mode: any exception (missing key, rate limit, parse error)
    returns ``{"mechanism": "unknown"}``. The caller is expected to fall
    back to keyword routing in that case.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise ImportError(
            "anthropic is required for the LLM extractor. "
            'Install with: pip install -e ".[llm]"'
        ) from exc

    PrimitiveClassification = _build_classification_model()

    # Resolve the API key once. Raise loudly here if the caller asked for
    # the LLM path without configuring it — silent fallback at extract
    # time would make the whole feature feel broken.
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    # Build the system prompt block once. When caching is enabled we mark
    # the block with cache_control so the server can serve repeats from
    # the prefix cache.
    if enable_caching:
        system_blocks = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        system_blocks = [{"type": "text", "text": SYSTEM_PROMPT}]

    def llm_fn(prompt: str) -> Dict[str, Any]:
        """Classify a single user claim into one of the seven labels."""
        # The pipeline passes a pre-formatted prompt that includes the
        # ontology context plus the user text. We only need the user text
        # for our classifier, so we extract the trailing 'Text:' line if
        # present; otherwise we use the whole prompt.
        user_text = prompt
        if "\nText:" in prompt:
            user_text = prompt.rsplit("\nText:", 1)[-1].strip()

        try:
            response = client.messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system_blocks,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Classify the following claim into one of the "
                            "seven labels.\n\n"
                            f"Claim: {user_text}"
                        ),
                    }
                ],
                output_format=PrimitiveClassification,
            )
        except Exception as exc:  # noqa: BLE001 - graceful fallback
            # Top-level keys here are spread by ``extract_mechanism``
            # into ``extraction['evidence']`` via ``{**result}``, so
            # ``method`` ends up at ``extraction['evidence']['method']``
            # exactly where the domain extractor expects it.
            return {
                "mechanism": "unknown",
                "method": "llm-error",
                "error": f"{type(exc).__name__}: {exc}",
            }

        parsed: PrimitiveClassification = response.parsed_output  # type: ignore[assignment]
        usage = getattr(response, "usage", None)
        return {
            "mechanism": parsed.mechanism,
            "confidence": parsed.confidence,
            "reasoning": parsed.reasoning,
            # ``method`` and ``model`` are top-level so the spread inside
            # ``extract_mechanism`` lifts them onto
            # ``extraction['evidence']`` directly.
            "method": "llm-anthropic",
            "model": model,
            "usage": {
                "cache_read_input_tokens": getattr(
                    usage, "cache_read_input_tokens", 0
                ) if usage else 0,
                "cache_creation_input_tokens": getattr(
                    usage, "cache_creation_input_tokens", 0
                ) if usage else 0,
                "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
                "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
            },
        }

    return llm_fn


__all__ = [
    "PrimitiveLabel",
    "SYSTEM_PROMPT",
    "make_anthropic_extractor",
]
