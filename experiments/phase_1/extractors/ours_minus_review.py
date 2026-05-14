"""Ablation: Ours minus the self-review step.

Same as Ours_full_loop (skillify prior context, schema prompt) but the prompt
is single-shot — no "review your output" instruction. Used to measure the
contribution of the self-review gate alone.

Pairs with B5 (review without skillify prior) and Ours_full_loop (review +
skillify prior) for a clean 2×2 ablation of (skillify, review).
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import ExtractionResult, load_paper_text, get_paper_excerpt, verify_excerpt_in_text
from ._llm_client import call_anthropic, parse_json_blob, MODEL


_SKILLIFY_PRIOR_PATH = Path("tests/fixtures/research/gold/01_kirkpatrick_ewc.json")


def _load_skillify_prior() -> str:
    try:
        data = json.loads(_SKILLIFY_PRIOR_PATH.read_text())
    except FileNotFoundError:
        return ""
    return (
        "Example of a high-quality MechanismCard (the skillify prior):\n"
        f"{{\n"
        f'  "mechanism": "{data["mechanism"]}",\n'
        f'  "invariant": "{data["invariant"]}",\n'
        f'  "prediction": "{data["prediction"]}",\n'
        f'  "failure_mode": "{data["failure_mode"]}",\n'
        f'  "source_excerpt": "<verbatim quote here>"\n'
        f"}}\n"
        "Match this bar.\n"
    )


PROMPT_MINUS_REVIEW = """\
You extract a MechanismCard from a research paper using a high-quality
template (the skillify prior).

{skillify_prior}

Extract a card from the new paper. The card has these fields:
- mechanism (≤600 chars): What CAUSAL STRUCTURE generates the paper's behavior?
- invariant (≤400 chars): What stays the same across all the cases?
- prediction (≤400 chars): A falsifiable consequence of the mechanism.
- failure_mode (≤400 chars): A condition under which the mechanism breaks.
- source_excerpt (≤500 chars): A VERBATIM quote from the paper text that
  supports the mechanism field.

Output ONLY a single JSON object. No commentary, no self-review.
"""


def extract(paper_id: str, paper_title: str, paper_path: str) -> ExtractionResult:
    text = load_paper_text(paper_path)
    excerpt_window = get_paper_excerpt(text, start=0, length=8000)

    skillify_prior = _load_skillify_prior()
    prompt_template = PROMPT_MINUS_REVIEW.format(skillify_prior=skillify_prior)
    prompt = f"{prompt_template}\n\nPaper title: {paper_title}\n\nPaper text:\n{excerpt_window}"

    response, tokens_in, tokens_out = call_anthropic(prompt, max_tokens=1500)
    parsed = parse_json_blob(response) or {}

    mechanism = (parsed.get("mechanism") or "")[:600]
    invariant = (parsed.get("invariant") or "")[:400]
    prediction = (parsed.get("prediction") or "")[:400]
    failure_mode = (parsed.get("failure_mode") or "")[:400]
    source_excerpt = (parsed.get("source_excerpt") or "")[:500]

    pinned = verify_excerpt_in_text(source_excerpt, text)

    return ExtractionResult(
        system="Ours_minus_review",
        paper_id=paper_id,
        paper_title=paper_title,
        mechanism=mechanism,
        invariant=invariant,
        prediction=prediction,
        failure_mode=failure_mode,
        source_excerpt=source_excerpt,
        has_schema=bool(mechanism and invariant and prediction and failure_mode),
        pinned_provenance=pinned,
        review_gate_passed=False,                       # ABLATION: no review
        skillify_prior_used=True,                       # still has skillify prior
        llm_tokens_in=tokens_in,
        llm_tokens_out=tokens_out,
        extraction_method=f"llm-{MODEL}-skillify-no-review",
    )
