"""Tests for the conversational onboarding (``conversation.py``).

Covers the deterministic fallback path (no API key required). The LLM
path is exercised via integration tests when ``ANTHROPIC_API_KEY`` is
set; those tests skip otherwise.
"""
from __future__ import annotations

import os
import pytest

from agent.founder_loop.conversation import (
    EVIDENCE_VOCAB,
    ConversationManager,
)


@pytest.fixture
def manager() -> ConversationManager:
    return ConversationManager(use_llm=False, api_key=None)


def _walk(manager: ConversationManager, cid: str, msgs: list[str]):
    last = None
    for m in msgs:
        last = manager.respond(cid, m)
    return last


def test_evidence_vocab_matches_pydantic_schema():
    """The fallback path leaks the vocabulary to the user; pin it to the
    canonical Literal so they don't drift."""
    assert "pr_merged" in EVIDENCE_VOCAB
    assert "commit_pushed" in EVIDENCE_VOCAB
    assert "human_signoff" in EVIDENCE_VOCAB
    assert len(EVIDENCE_VOCAB) >= 7  # canonical seven


def test_start_returns_greeting_and_id(manager: ConversationManager):
    cid, greeting = manager.start()
    assert isinstance(cid, str) and len(cid) >= 8
    assert "morning" in greeting.lower() or "important" in greeting.lower()


def test_fallback_collects_one_priority(manager: ConversationManager):
    cid, _ = manager.start()
    turn = _walk(manager, cid, [
        "ship the founder_loop PR",
        "pr_merged",
        "neuro-os#999",
        "3",
    ])
    priorities = manager.priorities_for(cid)
    assert len(priorities) == 1
    p = priorities[0]
    assert p.title == "ship the founder_loop PR"
    assert p.evidence_type == "pr_merged"
    assert p.evidence_target == "neuro-os#999"
    assert p.weight == 3
    # Not signable yet — still need ration.
    assert turn.can_sign is False


def test_fallback_advances_to_sign(manager: ConversationManager):
    cid, _ = manager.start()
    _walk(manager, cid, [
        "two deep work blocks",
        "commit_pushed",
        "2_commits",
        "2",
        "done",
        "45",
    ])
    assert manager.settings_for(cid).entertainment_ration_min == 45
    state = manager.convos[cid]
    assert state.can_sign is True


def test_fallback_rejects_invalid_evidence_type(manager: ConversationManager):
    cid, _ = manager.start()
    manager.respond(cid, "do something")
    turn = manager.respond(cid, "asdf")
    assert "valid" in turn.assistant_text.lower() or "pick" in turn.assistant_text.lower()
    # State stays in evidence_type
    assert manager.convos[cid].fallback_step == "evidence_type"


def test_fallback_rejects_invalid_weight(manager: ConversationManager):
    cid, _ = manager.start()
    _walk(manager, cid, [
        "do thing",
        "commit_pushed",
        "1_commit",
    ])
    turn = manager.respond(cid, "five")
    assert "1, 2, or 3" in turn.assistant_text


def test_fallback_done_with_no_priorities_pushes_back(manager: ConversationManager):
    cid, _ = manager.start()
    turn = manager.respond(cid, "done")
    assert "any priorities" in turn.assistant_text.lower()


def test_fallback_caps_at_5_priorities(manager: ConversationManager):
    cid, _ = manager.start()
    for i in range(5):
        _walk(manager, cid, [
            f"priority {i}",
            "commit_pushed",
            f"target_{i}",
            "2",
        ])
    assert len(manager.priorities_for(cid)) == 5
    # Auto-advanced to ration step
    assert manager.convos[cid].fallback_step == "ration"


def test_unknown_conversation_id_starts_fresh(manager: ConversationManager):
    turn = manager.respond("nonexistent-cid-12345", "hi")
    assert turn.conversation_id != "nonexistent-cid-12345"


def test_priorities_serialize_to_jsonable(manager: ConversationManager):
    cid, _ = manager.start()
    _walk(manager, cid, [
        "ship X",
        "pr_merged",
        "repo#1",
        "2",
    ])
    turn_dict = manager.respond(cid, "done").to_jsonable()
    assert "conversation_id" in turn_dict
    assert "priorities" in turn_dict
    assert turn_dict["priorities"][0]["title"] == "ship X"


# ---------------------------------------------------------------------------
# LLM path — runs only with a real API key, otherwise skipped
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="LLM-driven conversation requires ANTHROPIC_API_KEY",
)
def test_llm_path_extracts_priority_in_one_turn():  # pragma: no cover
    m = ConversationManager(use_llm=True)
    cid, _ = m.start()
    turn = m.respond(
        cid,
        "I want to ship the founder_loop PR — it's neuro-os#142, "
        "and it's a must-do today.",
    )
    assert turn.using_llm is True
    # Claude should have called record_priority at least once.
    assert len(m.priorities_for(cid)) >= 1
