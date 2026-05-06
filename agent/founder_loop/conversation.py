"""
Conversational onboarding for the daily contract.

The user speaks plain English; Claude calls structured tools to extract
``Priority`` objects. The server tracks accumulated priorities and the
conversation history in memory. When Claude calls ``ready_to_sign``,
the UI reveals the Sign button.

Without an API key, falls back to a deterministic state-machine
conversation that's worse but still works (one field at a time).

Public API
----------

* ``ConversationManager`` — stateful, per-daemon-instance.
  * ``start()`` → ``(conversation_id, greeting)``
  * ``respond(conversation_id, user_message)`` → ``ChatTurn``
  * ``priorities_for(conversation_id)`` → ``List[Priority]``
  * ``settings_for(conversation_id)`` → ``ContractSettings``
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, get_args

from agent.founder_loop.state import (
    EvidenceType,
    Priority,
)

log = logging.getLogger("founder_loop.conversation")

EVIDENCE_VOCAB: tuple[str, ...] = tuple(get_args(EvidenceType))


# ---------------------------------------------------------------------------
# System prompt — the personality / philosophy lives here
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are the morning-ritual assistant for Founder Loop, a daily \
productivity contract system. Today's user is signing a contract for \
themselves: 1–5 priorities, each with a tangible "done" signal, plus a \
ration of entertainment time they unlock once they hit 90% completion.

Your job: help the user articulate today's priorities in plain language. \
Speak warmly and briefly. One question at a time. Never mention internal \
field names (no "evidence_type", no "weight"); translate them into natural \
questions.

For each priority, you need to discover three things:
  1. A concise title.
  2. How they'll verify it's done — a TANGIBLE artifact: a merged PR, a \
pushed commit, a published doc, a count reached, a person's signoff, an \
uploaded artifact. If they say "do work on X", press for what specifically \
proves it's done.
  3. How important: 1=nice-to-have, 2=should-do, 3=must-do today.

When you've crystallized a priority, immediately call the \
``record_priority`` tool. Do this in the SAME turn — you can call multiple \
tools per turn. The user sees priorities populate a side panel as you \
record them; this is motivating.

When you have at least one priority and the user signals they're done \
adding (or you've reached 5), ask how long they want for entertainment \
after they hit 90% — default 60 minutes. Then call ``ready_to_sign`` and \
in your final assistant message, summarize the contract and tell them to \
click "Sign contract" below.

Tone notes:
  * Yesterday-self writing tomorrow's signature, not a productivity coach.
  * Push back gently if the user proposes more than 5 priorities ("fewer \
is better — pick the three that actually matter").
  * Push back if a priority has no tangible "done" signal ("how will we \
know that's done?").
  * Don't over-clarify obvious things. If the title and target are clear, \
record it and move on.
  * Don't ever invent the user's priorities or evidence targets. Ask.

You are helping them keep a promise to themselves. That's the whole job."""


# ---------------------------------------------------------------------------
# Tools — the structured surface Claude uses to record priorities
# ---------------------------------------------------------------------------


def _tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "record_priority",
            "description": (
                "Record one priority you've crystallized with the user. Call "
                "as soon as you have title, evidence type, evidence target, "
                "and weight. You can call this multiple times in one turn."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Concise title, like 'ship founder_loop PR'.",
                    },
                    "evidence_type": {
                        "type": "string",
                        "enum": list(EVIDENCE_VOCAB),
                        "description": (
                            "How will we verify done? Translate the user's "
                            "language: 'merge the PR' → pr_merged; 'push 2 "
                            "commits' → commit_pushed; 'publish the doc' → "
                            "doc_published; 'send 50 emails' → "
                            "count_reached; 'get manager approval' → "
                            "human_signoff; 'upload to S3' → "
                            "artifact_uploaded; 'open the PR' → pr_opened."
                        ),
                    },
                    "evidence_target": {
                        "type": "string",
                        "description": (
                            "Specific target: a PR number like 'neuro-os#142', "
                            "a count like '2_commits' or 'count:50', a name "
                            "like 'manager_alice', a path like 's3://.../v1.bin'."
                        ),
                    },
                    "weight": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 3,
                        "description": "1=nice-to-have, 2=should-do, 3=must-do.",
                    },
                },
                "required": ["title", "evidence_type", "evidence_target", "weight"],
            },
        },
        {
            "name": "ready_to_sign",
            "description": (
                "Indicate the user has finalized priorities AND chosen an "
                "entertainment ration. Server reveals the Sign button to "
                "the user. Only call this once everything is settled."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "entertainment_ration_min": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 720,
                        "description": "Minutes of entertainment unlocked once tank ≥ threshold.",
                    },
                    "threshold_pct": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Percent tank required before entertainment unlocks. Default 90.",
                    },
                },
                "required": ["entertainment_ration_min"],
            },
        },
    ]


# ---------------------------------------------------------------------------
# State containers
# ---------------------------------------------------------------------------


@dataclass
class ContractSettings:
    entertainment_ration_min: int = 60
    threshold_pct: int = 90


@dataclass
class _ConvoState:
    history: List[Dict[str, Any]] = field(default_factory=list)
    priorities: List[Priority] = field(default_factory=list)
    settings: ContractSettings = field(default_factory=ContractSettings)
    can_sign: bool = False
    # For the deterministic fallback only:
    fallback_step: str = "title"
    fallback_buffer: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatTurn:
    conversation_id: str
    assistant_text: str
    priorities: List[Priority]
    settings: ContractSettings
    can_sign: bool
    using_llm: bool

    def to_jsonable(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "assistant_text": self.assistant_text,
            "priorities": [json.loads(p.model_dump_json()) for p in self.priorities],
            "settings": {
                "entertainment_ration_min": self.settings.entertainment_ration_min,
                "threshold_pct": self.settings.threshold_pct,
            },
            "can_sign": self.can_sign,
            "using_llm": self.using_llm,
        }


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class ConversationManager:
    """Per-daemon instance. In-memory state."""

    GREETING = (
        "Good morning. What's important today? "
        "Tell me in your own words — I'll help make it concrete."
    )

    def __init__(
        self,
        *,
        use_llm: bool = True,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
    ) -> None:
        self.use_llm = use_llm
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.max_tokens = max_tokens
        self.convos: Dict[str, _ConvoState] = {}

        self._client = None
        if self.use_llm and self.api_key:
            try:
                import anthropic  # noqa: WPS433
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except Exception as exc:  # pragma: no cover
                log.warning("anthropic SDK unavailable: %s", exc)
                self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> tuple[str, str]:
        cid = uuid.uuid4().hex[:12]
        self.convos[cid] = _ConvoState()
        self.convos[cid].history.append(
            {"role": "assistant", "content": [{"type": "text", "text": self.GREETING}]}
        )
        return cid, self.GREETING

    def respond(self, conversation_id: str, user_message: str) -> ChatTurn:
        state = self.convos.get(conversation_id)
        if state is None:
            # Unknown id — start fresh and discard.
            conversation_id, _ = self.start()
            state = self.convos[conversation_id]

        state.history.append(
            {"role": "user", "content": [{"type": "text", "text": user_message}]}
        )

        if self._client is not None:
            try:
                text = self._llm_turn(state)
                using_llm = True
            except Exception as exc:
                log.exception("LLM turn failed; falling back: %s", exc)
                text = self._fallback_turn(state, user_message)
                using_llm = False
        else:
            text = self._fallback_turn(state, user_message)
            using_llm = False

        return ChatTurn(
            conversation_id=conversation_id,
            assistant_text=text,
            priorities=list(state.priorities),
            settings=state.settings,
            can_sign=state.can_sign,
            using_llm=using_llm,
        )

    def priorities_for(self, conversation_id: str) -> List[Priority]:
        s = self.convos.get(conversation_id)
        return list(s.priorities) if s else []

    def settings_for(self, conversation_id: str) -> ContractSettings:
        s = self.convos.get(conversation_id)
        return s.settings if s else ContractSettings()

    # ------------------------------------------------------------------
    # LLM path (Claude with tool use)
    # ------------------------------------------------------------------

    def _llm_turn(self, state: _ConvoState) -> str:
        """One round-trip; loop on tool_use until Claude emits final text."""
        assert self._client is not None
        rounds = 0
        last_text = ""
        while rounds < 4:  # safety bound
            rounds += 1
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                tools=_tools(),
                messages=self._llm_history(state),
            )
            # Append assistant message (with both tool_use and text blocks).
            state.history.append({
                "role": "assistant",
                "content": [_block_to_jsonable(b) for b in response.content],
            })

            # Collect text + handle tool calls.
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]
            last_text = "\n\n".join(b.text for b in text_blocks).strip()

            if not tool_uses:
                return last_text

            # Process tool calls; build tool_result content list.
            results: List[Dict[str, Any]] = []
            for tu in tool_uses:
                ok, msg = self._apply_tool(state, tu.name, tu.input or {})
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": msg,
                    "is_error": not ok,
                })
            state.history.append({"role": "user", "content": results})

            if response.stop_reason != "tool_use":
                # Claude is done.
                return last_text
        # If we hit the round bound, return the last text.
        return last_text or "(no response — please try again)"

    def _llm_history(self, state: _ConvoState) -> List[Dict[str, Any]]:
        # Anthropic expects the first message to be role=user. The opening
        # greeting we stored as 'assistant' is just for the UI; strip it.
        out: List[Dict[str, Any]] = []
        for msg in state.history:
            if not out and msg["role"] == "assistant":
                continue
            out.append(msg)
        return out

    def _apply_tool(
        self, state: _ConvoState, name: str, args: Dict[str, Any]
    ) -> tuple[bool, str]:
        try:
            if name == "record_priority":
                p = Priority(
                    title=args["title"],
                    evidence_type=args["evidence_type"],
                    evidence_target=args["evidence_target"],
                    weight=int(args["weight"]),
                )
                # Avoid dupes by title.
                state.priorities = [
                    x for x in state.priorities if x.title != p.title
                ]
                if len(state.priorities) >= 5:
                    return False, (
                        "Already have 5 priorities. Cap is 5 — drop one before "
                        "adding more."
                    )
                state.priorities.append(p)
                return True, f"recorded: {p.title}"

            if name == "ready_to_sign":
                state.settings.entertainment_ration_min = int(
                    args.get("entertainment_ration_min", 60)
                )
                state.settings.threshold_pct = int(args.get("threshold_pct", 90))
                if not state.priorities:
                    return False, "Cannot sign — no priorities recorded yet."
                state.can_sign = True
                return True, "ready to sign"
        except Exception as exc:
            return False, f"tool error: {exc}"
        return False, f"unknown tool: {name}"

    # ------------------------------------------------------------------
    # Fallback path (no API key) — strict state-machine, plain regex
    # ------------------------------------------------------------------

    def _fallback_turn(self, state: _ConvoState, user_message: str) -> str:
        msg = user_message.strip()

        # If user signals done → ask for ration if not set, else mark sign.
        if state.fallback_step == "title" and re.match(
            r"^\s*(done|that's it|sign( me)? up|ready)\s*$", msg, re.I
        ):
            if not state.priorities:
                return (
                    "I don't have any priorities recorded yet. "
                    "Tell me one thing you want to ship today, and how you'll "
                    "know it's done."
                )
            state.fallback_step = "ration"
            return (
                "Got it — that's your set. How long do you want for "
                "entertainment after you hit 90%? "
                "Default is 60 minutes. Say a number."
            )

        if state.fallback_step == "ration":
            m = re.search(r"(\d{1,3})", msg)
            if not m:
                return "I need a number of minutes. e.g. '60'."
            state.settings.entertainment_ration_min = int(m.group(1))
            state.can_sign = True
            state.fallback_step = "title"
            ps = "\n".join(
                f"  • {p.title} ({p.evidence_type}: {p.evidence_target}) "
                f"[weight {p.weight}]"
                for p in state.priorities
            )
            return (
                f"Locking in:\n{ps}\n"
                f"Ration: {state.settings.entertainment_ration_min} min · "
                f"Threshold: {state.settings.threshold_pct}%\n\n"
                "Click 'Sign contract' below."
            )

        # Title step: take user message as a title; ask for evidence next.
        if state.fallback_step == "title":
            state.fallback_buffer = {"title": msg[:120]}
            state.fallback_step = "evidence_type"
            return (
                f"'{state.fallback_buffer['title']}' — how will we know it's "
                "done? Pick one:\n"
                "  • commit_pushed  • pr_opened  • pr_merged\n"
                "  • doc_published  • count_reached  • human_signoff\n"
                "  • artifact_uploaded\n\n"
                "Type one of those words."
            )

        if state.fallback_step == "evidence_type":
            picked = next(
                (e for e in EVIDENCE_VOCAB if e in msg.lower()),
                None,
            )
            if not picked:
                return (
                    "I didn't catch a valid one. Pick from: " +
                    ", ".join(EVIDENCE_VOCAB)
                )
            state.fallback_buffer["evidence_type"] = picked
            state.fallback_step = "evidence_target"
            return (
                "And the specific target? "
                "(e.g. 'neuro-os#142' for a PR, '2_commits' for a count, "
                "'manager_alice' for a signoff)"
            )

        if state.fallback_step == "evidence_target":
            state.fallback_buffer["evidence_target"] = msg[:120]
            state.fallback_step = "weight"
            return (
                "How important — 1 (nice-to-have), 2 (should-do), or 3 (must-do)?"
            )

        if state.fallback_step == "weight":
            m = re.search(r"[1-3]", msg)
            if not m:
                return "Please answer 1, 2, or 3."
            buf = state.fallback_buffer
            try:
                p = Priority(
                    title=buf["title"],
                    evidence_type=buf["evidence_type"],
                    evidence_target=buf["evidence_target"],
                    weight=int(m.group(0)),
                )
            except Exception as exc:
                state.fallback_buffer = {}
                state.fallback_step = "title"
                return f"That didn't validate ({exc}). Tell me another priority."
            state.priorities.append(p)
            state.fallback_buffer = {}
            state.fallback_step = "title"
            count = len(state.priorities)
            if count >= 5:
                state.fallback_step = "ration"
                return (
                    f"Recorded ({count}/5). That's the cap. "
                    f"How long do you want for entertainment after 90%? "
                    "(default 60 min — say a number)"
                )
            return (
                f"Recorded — {count} so far. "
                "Tell me another priority, or type 'done' to finish."
            )

        # Should not reach here.
        state.fallback_step = "title"
        return "Tell me one priority for today."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _block_to_jsonable(block: Any) -> Dict[str, Any]:
    """Anthropic returns typed objects; we need plain dicts for re-send."""
    if hasattr(block, "model_dump"):
        return block.model_dump()
    if isinstance(block, dict):
        return block
    # Fallback: pull common attrs.
    out = {"type": getattr(block, "type", "unknown")}
    for attr in ("text", "id", "name", "input"):
        if hasattr(block, attr):
            out[attr] = getattr(block, attr)
    return out


__all__ = [
    "ConversationManager",
    "ContractSettings",
    "ChatTurn",
]
