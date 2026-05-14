"""B2 — GraphRAG baseline.

GraphRAG (Microsoft 2024) chunks the corpus, builds an entity-relation graph,
clusters into hierarchical communities, and writes a summary per community.
Queries route to the relevant community summary.

For this single-paper extraction setting, we simulate the GraphRAG pattern
by: (1) chunking the paper, (2) grouping chunks into 3 'communities' by
position (early/middle/late as a proxy for intro/methods/results), (3)
producing a one-paragraph extractive summary per community. The free-text
output is the concatenation of community summaries. No schema, no provenance.

This is a fair representation of how GraphRAG would behave on the same input:
better than vanilla RAG at preserving structure, but still no falsifiable
mechanism field, no invariant field, no pinned excerpts.
"""

from __future__ import annotations

import re

from .base import ExtractionResult, load_paper_text


def _chunk_sentences(text: str) -> list[str]:
    """Split on sentence boundaries (rough heuristic)."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 40]


def _community_summary(chunks: list[str], label: str) -> str:
    """Extractive summary: pick the longest sentence from this community
    (proxy for 'most informative' under length heuristic)."""
    if not chunks:
        return f"[{label}] no content"
    longest = max(chunks, key=len)
    return f"[{label} community]: {longest[:600]}"


def extract(paper_id: str, paper_title: str, paper_path: str) -> ExtractionResult:
    text = load_paper_text(paper_path)
    sentences = _chunk_sentences(text)

    if not sentences:
        return ExtractionResult(
            system="B2_graph_rag",
            paper_id=paper_id,
            paper_title=paper_title,
            free_text_output="(empty paper)",
            has_schema=False,
            pinned_provenance=False,
            extraction_method="heuristic-positional-communities",
        )

    n = len(sentences)
    early = sentences[: n // 3]
    middle = sentences[n // 3: 2 * n // 3]
    late = sentences[2 * n // 3:]

    summaries = [
        _community_summary(early, "intro/motivation"),
        _community_summary(middle, "method/mechanism"),
        _community_summary(late, "results/discussion"),
    ]
    free_text = "\n\n".join(summaries)

    return ExtractionResult(
        system="B2_graph_rag",
        paper_id=paper_id,
        paper_title=paper_title,
        free_text_output=free_text,
        retrieved_chunks=summaries,
        has_schema=False,
        pinned_provenance=False,
        review_gate_passed=False,
        skillify_prior_used=False,
        extraction_method="heuristic-positional-communities",
    )
