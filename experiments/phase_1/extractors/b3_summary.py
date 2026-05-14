"""B3 — Summarization-only baseline.

Extract the abstract (first paragraph after a recognizable section heading
like "Abstract") + the first 2 sentences after the first "Introduction"
heading. This is the classic 'summarize the paper' baseline that one would
build by piping the paper through a summarizer like TextRank or sumy.

No schema, no provenance, no mechanism/invariant/prediction/failure_mode
fields — just narrative summary text.
"""

from __future__ import annotations

import re

from .base import ExtractionResult, load_paper_text


def _extract_abstract(text: str) -> str:
    # Look for "Abstract" header followed by paragraph.
    m = re.search(
        r"abstract\s*\n+([\s\S]{50,1500}?)(?:\n\s*\n|\n\s*\d+\s*introduction)",
        text,
        re.IGNORECASE,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    # Fallback: first ~1000 chars
    return text[:1000].strip()


def _extract_intro_lede(text: str) -> str:
    m = re.search(
        r"(?:1\s+|^)introduction\s*\n+([\s\S]{50,800}?)(?:\n\s*\n)",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if m:
        sentences = re.split(r"(?<=[.!?])\s+", m.group(1))
        return " ".join(sentences[:2]).strip()
    return ""


def extract(paper_id: str, paper_title: str, paper_path: str) -> ExtractionResult:
    text = load_paper_text(paper_path)
    abstract = _extract_abstract(text)
    intro_lede = _extract_intro_lede(text)
    free_text = (abstract + ("\n\n" + intro_lede if intro_lede else "")).strip()

    return ExtractionResult(
        system="B3_summary",
        paper_id=paper_id,
        paper_title=paper_title,
        free_text_output=free_text,
        has_schema=False,
        pinned_provenance=False,
        review_gate_passed=False,
        skillify_prior_used=False,
        extraction_method="heuristic-abstract-extraction",
    )
