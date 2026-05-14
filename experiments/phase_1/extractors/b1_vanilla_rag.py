"""B1 — Vanilla RAG baseline.

Chunks the paper into ~500-char windows, retrieves top-K chunks for a fixed
set of queries ("what is the core mechanism", "what is the prediction", etc).
Outputs concatenated free text. NO schema; NO provenance pinning.

This is the dominant pattern in AI-for-research today. It fails our
mechanism-survival metric by construction: there's no falsifiable prediction
field, no invariant field, and the retrieved chunks are not pinned to specific
excerpts in a way the downstream decisions can audit.
"""

from __future__ import annotations

import re

from .base import ExtractionResult, load_paper_text


QUERIES = [
    "what is the core mechanism that makes this technique work",
    "what does this paper predict about future behavior",
    "what is the failure mode of this approach",
    "what is the invariant property across all the cases",
]


def _chunk(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """Sliding-window chunker; produces overlapping windows."""
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i + chunk_size])
        i += chunk_size - overlap
    return chunks


def _tfidf_score(query: str, chunk: str) -> float:
    """Simple BM25-ish scoring without external deps.
    Returns the fraction of distinct query terms that appear in the chunk,
    weighted by inverse chunk length (favors short, relevant chunks).
    """
    q_terms = set(re.findall(r"\w+", query.lower()))
    c_text = chunk.lower()
    matched = sum(1 for t in q_terms if t in c_text)
    if not q_terms:
        return 0.0
    base = matched / len(q_terms)
    # Length penalty: favor chunks where matches are dense
    length_penalty = 1.0 / (1.0 + len(chunk) / 1000.0)
    return base * length_penalty


def _retrieve_top_k(query: str, chunks: list[str], k: int = 2) -> list[str]:
    scored = [(c, _tfidf_score(query, c)) for c in chunks]
    scored.sort(key=lambda x: -x[1])
    return [c for c, s in scored[:k] if s > 0]


def extract(paper_id: str, paper_title: str, paper_path: str) -> ExtractionResult:
    text = load_paper_text(paper_path)
    chunks = _chunk(text, chunk_size=500, overlap=100)

    retrieved: list[str] = []
    for q in QUERIES:
        retrieved.extend(_retrieve_top_k(q, chunks, k=2))

    free_text = "\n\n---\n\n".join(retrieved[:8])  # cap to keep it readable

    return ExtractionResult(
        system="B1_vanilla_rag",
        paper_id=paper_id,
        paper_title=paper_title,
        free_text_output=free_text,
        retrieved_chunks=retrieved[:8],
        # No schema fields — that's the whole point of this baseline.
        has_schema=False,
        pinned_provenance=False,
        review_gate_passed=False,
        skillify_prior_used=False,
        extraction_method="heuristic-bm25-retrieval",
    )
