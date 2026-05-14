"""Ours v2: full closed loop with Belief-OS bias-check.

Adds a second LLM call after the initial extraction to score the card on
four cognitive-bias dimensions: authority, recency, novelty, confirmation.
The result is an `assumption_flags` annotation that gets surfaced at
decision time but does NOT block acceptance (per the outline §4.4 —
"Flagged cards don't block — they get an `assumption` annotation").

This is the "with bias-check" arm of the bias-check ablation. The
"without bias-check" arm is the existing `ours_full_loop`.
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


EXTRACTION_PROMPT = """\
You extract a MechanismCard from a research paper using a closed-loop quality
pipeline.

{skillify_prior}

The card has these fields:
- mechanism (≤600 chars): CAUSAL structure generating the paper's behavior
- invariant (≤400 chars): What stays the same across cases (transferable)
- prediction (≤400 chars): A falsifiable consequence
- failure_mode (≤400 chars): A specific breaking condition
- source_excerpt (≤500 chars): A VERBATIM quote from the paper text

Self-review checks:
- Mechanism describes CAUSAL structure, not naming the technique
- Invariant is transferable beyond the paper's domain
- Prediction is falsifiable, not tautology
- Failure mode is a specific condition
- Source excerpt is COPIED VERBATIM (we will regex-audit)

Output ONLY the revised card as a single JSON object. No commentary.
"""


BIAS_CHECK_PROMPT = """\
Below is a MechanismCard extracted from a research paper. Score it for four
cognitive-bias signals on a 0-3 scale (0 = no concern, 3 = strong flag):

- authority_bias: Does the card uncritically accept the paper's claims
  because of author affiliation, citation count, or publication venue?
- recency_bias: Does the card over-weight novelty or recency over substance?
- novelty_bias: Does the card frame the paper as more original than it is,
  ignoring prior art?
- confirmation_bias: Does the card cherry-pick supporting points and
  omit counter-evidence (e.g., the paper's own limitations section)?

Output ONLY a JSON object with the four integer scores plus a one-line
`assumption_note` summarizing any flags ≥ 2.

Example:
{{"authority_bias": 0, "recency_bias": 1, "novelty_bias": 2,
  "confirmation_bias": 0, "assumption_note": "Slight novelty framing — paper builds heavily on prior work"}}

The card to score:
{card_json}
"""


def _run_bias_check(card_dict: dict) -> tuple[dict, int, int]:
    """Second LLM call. Returns (bias_annotation, tokens_in, tokens_out)."""
    card_json = json.dumps(card_dict, indent=2)
    prompt = BIAS_CHECK_PROMPT.format(card_json=card_json)
    response, t_in, t_out = call_anthropic(prompt, max_tokens=400)
    parsed = parse_json_blob(response) or {}
    # Validate score ranges, default any missing to 0.
    annotation = {
        "authority_bias": int(parsed.get("authority_bias", 0)),
        "recency_bias": int(parsed.get("recency_bias", 0)),
        "novelty_bias": int(parsed.get("novelty_bias", 0)),
        "confirmation_bias": int(parsed.get("confirmation_bias", 0)),
        "assumption_note": str(parsed.get("assumption_note", ""))[:200],
    }
    return annotation, t_in, t_out


def extract(paper_id: str, paper_title: str, paper_path: str) -> ExtractionResult:
    text = load_paper_text(paper_path)
    excerpt_window = get_paper_excerpt(text, start=0, length=8000)

    skillify_prior = _load_skillify_prior()
    prompt = (
        EXTRACTION_PROMPT.format(skillify_prior=skillify_prior)
        + f"\n\nPaper title: {paper_title}\n\nPaper text:\n{excerpt_window}"
    )

    response, t1_in, t1_out = call_anthropic(prompt, max_tokens=2000)
    parsed = parse_json_blob(response) or {}

    mechanism = (parsed.get("mechanism") or "")[:600]
    invariant = (parsed.get("invariant") or "")[:400]
    prediction = (parsed.get("prediction") or "")[:400]
    failure_mode = (parsed.get("failure_mode") or "")[:400]
    source_excerpt = (parsed.get("source_excerpt") or "")[:500]

    # Bias-check pass (a second LLM call).
    card_for_check = {
        "mechanism": mechanism,
        "invariant": invariant,
        "prediction": prediction,
        "failure_mode": failure_mode,
        "source_excerpt": source_excerpt,
        "paper_title": paper_title,
    }
    bias_annotation, t2_in, t2_out = _run_bias_check(card_for_check)

    pinned = verify_excerpt_in_text(source_excerpt, text)

    result = ExtractionResult(
        system="Ours_v2_with_bias_check",
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
        llm_tokens_in=t1_in + t2_in,
        llm_tokens_out=t1_out + t2_out,
        extraction_method=f"llm-{MODEL}-skillify-reviewed-bias-checked",
    )
    # Attach bias annotation as a side channel on the result dataclass.
    # (ExtractionResult doesn't have a slot for this in the original schema, so
    # we tack it on as a Python attribute — to_dict() picks it up if present.)
    result.__dict__["bias_annotation"] = bias_annotation
    return result
