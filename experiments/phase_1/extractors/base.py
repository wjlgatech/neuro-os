"""Shared types and helpers for Phase 1 extractors.

Every extractor produces an ExtractionResult per paper. Different baselines
populate different fields:
  - B1/B2/B3 produce free_text outputs and leave structured fields empty;
    they cannot pass provenance audit by construction.
  - B4/B5/Ours produce MechanismCard-shaped outputs with pinned excerpts.
The metrics layer reads ExtractionResult and computes the 5 paper metrics
from whatever fields are populated.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ExtractionResult:
    """One per (system, paper) pair. Frozen-style — write once, read many."""

    system: str                            # extractor name, e.g. "B1_vanilla_rag"
    paper_id: str                          # short slug, e.g. "ewc-kirkpatrick-2017"
    paper_title: str

    # Free-text outputs (B1/B2/B3 populate these; structured systems leave empty).
    free_text_output: str = ""
    retrieved_chunks: list[str] = field(default_factory=list)

    # MechanismCard-shaped fields (B4/B5/Ours populate these; baselines leave empty).
    mechanism: str = ""
    invariant: str = ""
    prediction: str = ""
    failure_mode: str = ""

    # Provenance fields — REQUIRED for Law 1 audit; empty for B1/B2/B3.
    source_excerpt: str = ""               # ≤500 chars; exact text from paper

    # Metadata for analysis.
    has_schema: bool = False               # True iff structured (B4/B5/Ours)
    pinned_provenance: bool = False        # True iff source_excerpt is verifiable
    review_gate_passed: bool = False       # True iff B5/Ours (Law 7 human review)
    skillify_prior_used: bool = False      # True iff Ours (closed loop)

    # Cost tracking.
    llm_tokens_in: int = 0
    llm_tokens_out: int = 0
    extraction_method: str = "heuristic"   # or "llm-anthropic-sonnet-4-6"

    def to_dict(self) -> dict:
        return asdict(self)


def load_paper_text(paper_path: str) -> str:
    """Read a paper text file from research_practice/inbox/."""
    from pathlib import Path
    return Path(paper_path).read_text(encoding="utf-8", errors="ignore")


def get_paper_excerpt(text: str, start: int = 0, length: int = 3000) -> str:
    """Extract a text window (default first 3000 chars after the abstract).
    Used as the input to LLM-based extractors so we don't blow context budgets.
    """
    # Strip the first ~500 chars (usually arxiv banners + author lists)
    return text[start:start + length].strip()


def verify_excerpt_in_text(excerpt: str, full_text: str) -> bool:
    """Provenance audit: does the claimed excerpt actually appear in the paper?

    Returns True iff the excerpt (after light normalization) substring-matches
    the paper text. This is Law 1 in action.
    """
    if not excerpt:
        return False
    # Light normalization: collapse whitespace, lowercase.
    import re

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.lower().strip())

    return norm(excerpt) in norm(full_text)
