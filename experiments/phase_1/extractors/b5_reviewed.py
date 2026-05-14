"""B5 — Reviewed MechanismCard baseline.

Same as B4 but with a self-review step: the LLM is asked to produce an
initial card, then evaluate it against the schema and produce a revised
version. This simulates a human Law-7 review gate, but the reviewer is
the LLM itself rather than a separate human. No skillify prior.
"""

from __future__ import annotations

from .base import ExtractionResult, load_paper_text, get_paper_excerpt, verify_excerpt_in_text
from ._llm_client import call_anthropic, parse_json_blob, MODEL


SYSTEM_PROMPT_B5 = """\
You extract a MechanismCard from a research paper, then review and revise it.

Step 1: Produce an initial card with fields:
- mechanism (≤600 chars): What CAUSAL STRUCTURE generates the paper's behavior?
- invariant (≤400 chars): What stays the same across all the cases?
- prediction (≤400 chars): A falsifiable consequence of the mechanism.
- failure_mode (≤400 chars): A condition under which the mechanism breaks.
- source_excerpt (≤500 chars): An EXACT quote from the paper supporting mechanism.

Step 2: Review your initial card. Check:
- Is `mechanism` describing a CAUSAL structure (not just naming the technique)?
- Is `invariant` a transferable property (not a paper-specific result)?
- Is `prediction` falsifiable (not a tautology)?
- Is `failure_mode` a specific condition (not "needs more research")?
- Does `source_excerpt` appear verbatim in the paper?

Step 3: Output the REVISED card as a single JSON object. No commentary.
"""


def extract(paper_id: str, paper_title: str, paper_path: str) -> ExtractionResult:
    text = load_paper_text(paper_path)
    excerpt_window = get_paper_excerpt(text, start=0, length=8000)

    prompt = f"{SYSTEM_PROMPT_B5}\n\nPaper title: {paper_title}\n\nPaper text:\n{excerpt_window}"

    response, tokens_in, tokens_out = call_anthropic(prompt, max_tokens=2000)
    parsed = parse_json_blob(response) or {}

    mechanism = (parsed.get("mechanism") or "")[:600]
    invariant = (parsed.get("invariant") or "")[:400]
    prediction = (parsed.get("prediction") or "")[:400]
    failure_mode = (parsed.get("failure_mode") or "")[:400]
    source_excerpt = (parsed.get("source_excerpt") or "")[:500]

    pinned = verify_excerpt_in_text(source_excerpt, text)

    return ExtractionResult(
        system="B5_reviewed_mechanism_card",
        paper_id=paper_id,
        paper_title=paper_title,
        mechanism=mechanism,
        invariant=invariant,
        prediction=prediction,
        failure_mode=failure_mode,
        source_excerpt=source_excerpt,
        has_schema=bool(mechanism and invariant and prediction and failure_mode),
        pinned_provenance=pinned,
        review_gate_passed=True,           # LLM self-review acts as the gate
        skillify_prior_used=False,
        llm_tokens_in=tokens_in,
        llm_tokens_out=tokens_out,
        extraction_method=f"llm-{MODEL}-self-reviewed",
    )
