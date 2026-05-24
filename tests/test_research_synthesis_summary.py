"""
Regression tests for the cluster mechanism_summary builder.

The original code did ``str(card["mechanism"])[:140]`` — a blind slice
that cut words in half (the '...context a' bug in the living-knowledge
view) and ignored each card's purpose-built ``one_sentence_compression``.
These tests pin the fixed behaviour:

  * prefer ``one_sentence_compression`` over the raw mechanism;
  * never cut mid-word;
  * single-member clusters keep their full compression sentence.
"""
from __future__ import annotations

from agent.research.synthesis import (
    _member_summary,
    _summarize_members,
    _word_safe_truncate,
    _heuristic_cluster,
)


def test_word_safe_truncate_no_midword_cut():
    text = "LLMs monitor their own context-window usage and prematurely wrap up"
    out = _word_safe_truncate(text, 30)
    assert len(out) <= 31  # limit + ellipsis slack
    assert out.endswith("…")
    # The visible part ends on a whole word (no half-word before the ellipsis).
    assert not out[:-1].rstrip().endswith("contex")
    assert " " not in out[-2:]  # didn't leave a dangling space before …


def test_word_safe_truncate_passthrough_when_short():
    assert _word_safe_truncate("short text", 100) == "short text"


def test_member_summary_prefers_compression():
    card = {
        "mechanism": "A very long mechanism description that goes on and on...",
        "one_sentence_compression": "Crisp compression.",
    }
    assert _member_summary(card) == "Crisp compression."


def test_member_summary_falls_back_to_mechanism():
    card = {"mechanism": "Just the mechanism."}
    assert _member_summary(card) == "Just the mechanism."


def test_summarize_single_member_keeps_full_compression():
    card = {
        "mechanism": "x" * 500,
        "one_sentence_compression": "Agents quit early from 'context anxiety', not because they're done.",
    }
    out = _summarize_members([card])
    assert out == "Agents quit early from 'context anxiety', not because they're done."
    assert "…" not in out  # nothing was truncated


def test_summarize_multi_member_fits_budget_word_safe():
    cards = [
        {"one_sentence_compression": "Sentence one " + "alpha " * 60},
        {"one_sentence_compression": "Sentence two " + "beta " * 60},
        {"one_sentence_compression": "Sentence three " + "gamma " * 60},
    ]
    out = _summarize_members(cards)
    assert len(out) <= 1000
    assert out.count(" | ") == 2  # three members joined
    # No half-words: every space-delimited token is a real word we put in.
    for token in out.replace(" | ", " ").replace("…", "").split():
        assert token in {"Sentence", "one", "two", "three", "alpha", "beta", "gamma"}


def test_heuristic_cluster_uses_compression_not_140_cut():
    """End-to-end: a single card whose mechanism is long but which has a
    short compression should yield a clean summary, not a 140-char slice."""
    long_mech = (
        "LLMs monitor their own context-window usage and prematurely "
        "'wrap up' as it fills — a built-in clock-out instinct Anthropic "
        "named 'context anxiety' in late-2025 research, and this matters."
    )
    cards = [{
        "id": "c1",
        "mechanism": long_mech,
        "one_sentence_compression": "Agents quit early from context anxiety.",
    }]
    clusters, _ = _heuristic_cluster(cards, threshold=0.1, min_cluster_size=1)
    assert len(clusters) == 1
    summary = clusters[0].mechanism_summary
    assert summary == "Agents quit early from context anxiety."
    # The old bug produced exactly len==140 mid-word; assert we're not that.
    assert not (len(summary) == 140 and not summary.endswith("."))
