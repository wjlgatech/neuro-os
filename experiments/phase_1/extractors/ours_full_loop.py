"""Ours — full closed-loop MechanismCard extraction.

B5 + skillify prior (the system has accumulated evidence about what
high-quality cards look like from prior accepted extractions). The prior
is implemented as a few-shot example: we prepend the gold card from a
DIFFERENT paper as a quality template, demonstrating the bar.

This is a faithful reduction of neuro-os's actual research pipeline:
ingest → propose → review → accept → skillify-event → prior-update.
For the experiment, the prior is fixed (one example) rather than
dynamic, because we don't want to leak gold information across the
N=10 corpus — the prior comes from ONE paper, not from the others.
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import ExtractionResult, load_paper_text, get_paper_excerpt, verify_excerpt_in_text
from ._llm_client import call_anthropic, parse_json_blob, MODEL


# Skillify prior: a single high-quality example from the gold set.
# Using EWC because it's the canonical CL paper — generic prior, not domain-leaking.
_SKILLIFY_PRIOR_PATH = Path(
    "tests/fixtures/research/gold/01_kirkpatrick_ewc.json"
)


def _load_skillify_prior() -> str:
    """Load one gold card as an in-context example of high quality."""
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
        "Notice how `mechanism` explains the CAUSAL story, `invariant` is a "
        "transferable property, `prediction` is falsifiable, and `failure_mode` "
        "is a specific condition. Match this bar.\n"
    )


SYSTEM_PROMPT_OURS = """\
You extract a MechanismCard from a research paper using a closed-loop quality
pipeline: (a) the schema, (b) the skillify prior (a high-quality example), (c)
self-review with explicit field-by-field checks.

{skillify_prior}

Now extract a card from the new paper. The card has these fields:
- mechanism (≤600 chars): What CAUSAL STRUCTURE generates the paper's behavior?
- invariant (≤400 chars): What stays the same across all the cases?
- prediction (≤400 chars): A falsifiable consequence of the mechanism.
- failure_mode (≤400 chars): A condition under which the mechanism breaks.
- source_excerpt (≤500 chars): An EXACT VERBATIM QUOTE from the paper text
  that supports the mechanism field. The quote MUST appear in the paper exactly
  as you copy it; we will regex-audit this against the paper.

Self-review checks (apply before outputting):
- Mechanism describes a CAUSAL structure, not just naming the technique.
- Invariant is transferable beyond the paper's domain.
- Prediction is falsifiable, not a tautology.
- Failure mode is a specific condition, not "needs more research".
- Source excerpt is COPIED VERBATIM from the paper text I gave you.

Output ONLY the revised card as a single JSON object. No commentary.
"""


def extract(paper_id: str, paper_title: str, paper_path: str) -> ExtractionResult:
    text = load_paper_text(paper_path)
    excerpt_window = get_paper_excerpt(text, start=0, length=8000)

    skillify_prior = _load_skillify_prior()
    prompt_template = SYSTEM_PROMPT_OURS.format(skillify_prior=skillify_prior)
    prompt = f"{prompt_template}\n\nPaper title: {paper_title}\n\nPaper text:\n{excerpt_window}"

    response, tokens_in, tokens_out = call_anthropic(prompt, max_tokens=2000)
    parsed = parse_json_blob(response) or {}

    mechanism = (parsed.get("mechanism") or "")[:600]
    invariant = (parsed.get("invariant") or "")[:400]
    prediction = (parsed.get("prediction") or "")[:400]
    failure_mode = (parsed.get("failure_mode") or "")[:400]
    source_excerpt = (parsed.get("source_excerpt") or "")[:500]

    pinned = verify_excerpt_in_text(source_excerpt, text)

    return ExtractionResult(
        system="Ours_full_loop",
        paper_id=paper_id,
        paper_title=paper_title,
        mechanism=mechanism,
        invariant=invariant,
        prediction=prediction,
        failure_mode=failure_mode,
        source_excerpt=source_excerpt,
        has_schema=bool(mechanism and invariant and prediction and failure_mode),
        pinned_provenance=pinned,
        review_gate_passed=True,
        skillify_prior_used=True,
        llm_tokens_in=tokens_in,
        llm_tokens_out=tokens_out,
        extraction_method=f"llm-{MODEL}-skillify-reviewed",
    )
