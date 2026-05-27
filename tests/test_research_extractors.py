"""Tests for agent/research/extractors.py — multi-persona LLM extraction
plus the inline 4-criteria quality filter.
"""
from __future__ import annotations

from typing import Dict, List
from unittest.mock import MagicMock

import pytest

from agent.research.extractors import (
    EVAL_FILTER,
    PERSONAS,
    _row_hash,
    build_persona_prompt,
    extract_multi_persona,
)


# ---------------------------------------------------------------------------
# Persona / prompt-building invariants
# ---------------------------------------------------------------------------

def test_personas_set_has_five_law8_lenses() -> None:
    """Law 8 lists 5 primitives — the extractor surfaces one persona per
    primitive. Pinning the count keeps the doc + extractor in sync."""
    assert len(PERSONAS) == 5
    names = {p.name for p in PERSONAS}
    assert names == {
        "predictive_processing",
        "hebbian",
        "reinforcement_learning",
        "attention",
        "hierarchical_abstraction",
    }


def test_personas_are_frozen() -> None:
    p = PERSONAS[0]
    with pytest.raises(Exception):
        p.name = "other"  # type: ignore[misc]


def test_eval_filter_names_all_four_criteria() -> None:
    """The 4-criteria rubric (compression / transferability / executability
    / falsifiability) must be named verbatim in the prompt so the LLM
    can't ambiguously interpret it."""
    for key in ("COMPRESSION", "TRANSFERABILITY", "EXECUTABILITY", "FALSIFIABILITY"):
        assert key in EVAL_FILTER, f"missing rubric criterion: {key}"


def test_build_persona_prompt_combines_base_lens_filter() -> None:
    base = "BASE_PROMPT_BODY"
    composed = build_persona_prompt(PERSONAS[0], base)
    assert base in composed
    assert PERSONAS[0].lens_description in composed
    assert "FALSIFIABILITY" in composed  # rubric present


# ---------------------------------------------------------------------------
# extract_multi_persona — happy + failure paths
# ---------------------------------------------------------------------------

def _build_fake_llm(per_persona_rows: Dict[str, List[Dict]]):
    """Build an LLM that returns different rows depending on which
    persona name appears in the system prompt. Used to simulate each
    lens surfacing different mechanisms."""
    def _llm(system_prompt: str, user_message: str) -> List[Dict]:
        for name, rows in per_persona_rows.items():
            if f"lens: {name}" in system_prompt.lower() \
               or f"lens — {name.replace('_', ' ')}" in system_prompt.lower():
                return rows
        return []
    return _llm


def test_extract_multi_persona_runs_each_persona_once() -> None:
    calls: List[str] = []

    def _llm(system_prompt: str, user_message: str) -> List[Dict]:
        # Tag each call with which persona name appears.
        for p in PERSONAS:
            if p.lens_description.splitlines()[0] in system_prompt:
                calls.append(p.name)
                return [{
                    "mechanism": f"M from {p.name}",
                    "invariant": f"I for {p.name}",
                }]
        return []

    rows, stats = extract_multi_persona(
        llm_fn=_llm, base_prompt="BASE", user_message="USER",
    )
    assert len(calls) == 5
    assert set(calls) == {p.name for p in PERSONAS}
    # 5 personas, 5 unique mechanisms → 5 deduped rows.
    assert len(rows) == 5
    # Stats sum across personas equal total rows (since they're unique).
    assert sum(stats.values()) == 5
    # Each emitted row got tagged with its persona in `reasoning`.
    for row in rows:
        assert row["reasoning"].startswith("[lens: ")


def test_extract_multi_persona_dedups_overlapping_rows() -> None:
    """If two personas return the same mechanism+invariant, only one row
    survives in the merged output."""
    same = {
        "mechanism": "Same idea X.", "invariant": "Same invariant Y.",
        "reasoning": "from first",
    }

    def _llm(system_prompt: str, user_message: str) -> List[Dict]:
        return [same]

    rows, stats = extract_multi_persona(
        llm_fn=_llm, base_prompt="BASE", user_message="USER",
    )
    assert len(rows) == 1  # collapsed across all 5 personas
    # Only one persona got "credit" for it (whichever ran first).
    assert sum(stats.values()) == 1


def test_extract_multi_persona_per_persona_error_is_isolated() -> None:
    """A single persona blowing up must not abort the whole extraction."""
    call_count = {"n": 0}

    def _llm(system_prompt: str, user_message: str) -> List[Dict]:
        call_count["n"] += 1
        # Fail every 2nd call to simulate flaky network.
        if call_count["n"] % 2 == 0:
            raise RuntimeError("transient network error")
        return [{"mechanism": f"m{call_count['n']}", "invariant": "i"}]

    rows, stats = extract_multi_persona(
        llm_fn=_llm, base_prompt="BASE", user_message="USER",
    )
    # 5 calls total; ~2 raised. The remaining ~3 produced rows.
    assert len(rows) >= 1, "some personas should have succeeded"
    assert sum(stats.values()) >= 1


def test_extract_multi_persona_non_list_response_is_safe() -> None:
    """If a persona's llm_fn returns a non-list (e.g. malformed JSON
    deserialized as a dict), we don't explode."""
    def _llm(system_prompt: str, user_message: str):
        return {"this": "is not a list"}

    rows, stats = extract_multi_persona(
        llm_fn=_llm, base_prompt="BASE", user_message="USER",
    )
    assert rows == []
    assert sum(stats.values()) == 0


def test_extract_multi_persona_empty_personas_returns_empty() -> None:
    """Guard against a misconfigured empty persona tuple."""
    rows, stats = extract_multi_persona(
        llm_fn=MagicMock(), base_prompt="BASE", user_message="USER",
        personas=(),
    )
    assert rows == []
    assert stats == {}


# ---------------------------------------------------------------------------
# Row-hash determinism — must agree with proposals.compute_mechanism_hash
# ---------------------------------------------------------------------------

def test_row_hash_is_deterministic_and_case_insensitive() -> None:
    """Dedup correctness invariant: two rows that differ only by case or
    whitespace must hash to the same value."""
    row_a = {
        "mechanism": "Latent replay stores activations.",
        "invariant": "Activations cheaper than raw inputs.",
    }
    row_b = {
        "mechanism": "  LATENT  REPLAY  stores  activations.",
        "invariant": "activations cheaper than raw inputs!",
    }
    assert _row_hash(row_a) == _row_hash(row_b)
    # Different rows must hash differently.
    row_c = {"mechanism": "Something else.", "invariant": "Different."}
    assert _row_hash(row_a) != _row_hash(row_c)


# ---------------------------------------------------------------------------
# End-to-end via extract_mechanisms() in ingest.py
# ---------------------------------------------------------------------------

def test_ingest_extract_mechanisms_uses_multi_persona_by_default(tmp_path) -> None:
    """When llm_fn is supplied and multi_persona=True (default), the
    extractor must call llm_fn once per persona (5 calls), not once."""
    from agent.research.ingest import extract_mechanisms
    from agent.research.ontology import RawSource

    src_path = tmp_path / "tiny.md"
    src_path.write_text("Paper body about some mechanism.")
    source = RawSource(
        source_id="local:tiny.md:abc",
        title="Tiny",
        path=src_path,
        author="Test Author",
        word_count=4,
        sha256="0" * 64,
    )

    call_count = {"n": 0}

    def _llm(system_prompt: str, user_message: str) -> List[Dict]:
        call_count["n"] += 1
        return [{
            "mechanism": f"M{call_count['n']}",
            "invariant": f"I{call_count['n']}",
            "prediction": "p", "failure_mode": "f",
            "source_excerpt": "ex", "confidence": "medium",
            "reasoning": "r",
        }]

    proposals = extract_mechanisms(source, llm_fn=_llm)
    assert call_count["n"] == 5
    # 5 personas × 1 unique row each = 5 unique proposals (no dedup across
    # them since each call returns a different mechanism string).
    assert len(proposals) == 5


def test_ingest_extract_mechanisms_single_pass_when_opt_out(tmp_path) -> None:
    """Explicit ``multi_persona=False`` reverts to the legacy single
    LLM call. Old tests rely on this for deterministic call counts."""
    from agent.research.ingest import extract_mechanisms
    from agent.research.ontology import RawSource

    src_path = tmp_path / "tiny.md"
    src_path.write_text("Paper body.")
    source = RawSource(
        source_id="local:tiny.md:abc",
        title="Tiny",
        path=src_path,
        author="Test Author",
        word_count=4,
        sha256="0" * 64,
    )

    call_count = {"n": 0}

    def _llm(system_prompt: str, user_message: str) -> List[Dict]:
        call_count["n"] += 1
        return [{
            "mechanism": "M", "invariant": "I",
            "prediction": "p", "failure_mode": "f",
            "source_excerpt": "ex", "confidence": "medium",
            "reasoning": "r",
        }]

    proposals = extract_mechanisms(source, llm_fn=_llm, multi_persona=False)
    assert call_count["n"] == 1
    assert len(proposals) == 1
