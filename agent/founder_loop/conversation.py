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
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, get_args

from agent.founder_loop.state import (
    EvidenceType,
    Priority,
)

log = logging.getLogger("founder_loop.conversation")

EVIDENCE_VOCAB: tuple[str, ...] = tuple(get_args(EvidenceType))

ConversationKind = Literal["morning", "review", "queues"]
KIND_VOCAB: tuple[ConversationKind, ...] = ("morning", "review", "queues")


# ---------------------------------------------------------------------------
# System prompt — the personality / philosophy lives here
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_MORNING = """\
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


SYSTEM_PROMPT_REVIEW = """\
You are the nightly-review assistant for Founder Loop. The user has just \
finished their day. Your job: help them reflect briefly, then propose \
priorities for TOMORROW based on what's still undone, what they learned \
today, and what they want.

The first user message will contain a structured summary of today: tank \
percent, priorities completed vs pending, MAE and contract-honor rates, \
and any goldens that fired. Read it carefully but don't echo it back.

Your conversation has three phases:

  1. **Reflect** (1–2 turns). Ask one open question like "How did today \
go?" or "Anything surprise you?" Listen. Don't moralize.

  2. **Distill** (1 turn). Acknowledge what stood out. If priorities were \
left undone, ask whether they should roll over to tomorrow.

  3. **Propose tomorrow** (1–2 turns). Propose 1–3 priorities for \
tomorrow based on what they said. For each, call ``record_priority`` with \
the same structure as the morning ritual — title, evidence_type, target, \
weight. Ask their ration for tomorrow (default same as today). Call \
``ready_to_sign`` when done.

Tone: a thoughtful colleague at the end of a long day, not a coach. \
Brief. Don't ask more than two questions in any turn. If a priority \
clearly rolls over (was high-weight, still pending), record it without \
re-asking the same questions you asked this morning."""


SYSTEM_PROMPT_QUEUES = """\
You are the queue-maintenance assistant for Founder Loop. The user has \
three personalized lists that make Sublimation Cards concrete:

  * **bookmarks_queue** — articles to read when novelty-hunger fires.
  * **social_queue** — people to reach when loneliness fires.
  * **rubber_duck_venues** — places to externalize a stuck problem.

The first user message will list current contents. Your job: help the \
user add or remove items in plain language. They might say things like \
"I want to add three articles I bookmarked this week" or "remove the \
TechCrunch one" or "add my friend Sarah".

Tools you have:
  * ``add_bookmark(title, url, est_read_min)``
  * ``add_social_contact(name, channel, why)``
  * ``add_rubber_duck_venue(venue, kind)``  where kind ∈ {discord, voice, text}
  * ``remove_from_queue(queue_name, match)`` — match is a substring.

Speak warmly and briefly. Apply the user's intent immediately via tools \
in the same turn. If the user is vague, ask for the specific thing \
("which TechCrunch article?"), don't guess.

When the user signals they're done ("that's enough", "thanks", "done"), \
acknowledge the changes and tell them to close the tab — the next time \
a relevant urge fires, the cards will reference the new entries."""


SYSTEM_PROMPTS: Dict[str, str] = {
    "morning": SYSTEM_PROMPT_MORNING,
    "review": SYSTEM_PROMPT_REVIEW,
    "queues": SYSTEM_PROMPT_QUEUES,
}

# Backwards compatibility for tests that imported the old name.
SYSTEM_PROMPT = SYSTEM_PROMPT_MORNING


# ---------------------------------------------------------------------------
# Tools — the structured surface Claude uses to record priorities
# ---------------------------------------------------------------------------


_RECORD_PRIORITY_TOOL = {
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
}

_READY_TO_SIGN_TOOL = {
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
}

_QUEUE_TOOLS = [
    {
        "name": "add_bookmark",
        "description": "Add an article to the bookmarks queue (novelty_hunger sublimation).",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "url": {"type": "string"},
                "est_read_min": {"type": "integer", "minimum": 1, "maximum": 90},
            },
            "required": ["title", "url"],
        },
    },
    {
        "name": "add_social_contact",
        "description": "Add a person to the social queue (social-need sublimation).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "channel": {
                    "type": "string",
                    "description": "How to reach them: 'voice', 'text', 'imessage', 'whatsapp', etc.",
                },
                "why": {"type": "string", "description": "One sentence: why now?"},
            },
            "required": ["name", "channel"],
        },
    },
    {
        "name": "add_rubber_duck_venue",
        "description": "Add a venue to the rubber-duck queue (frustration sublimation).",
        "input_schema": {
            "type": "object",
            "properties": {
                "venue": {"type": "string"},
                "kind": {
                    "type": "string",
                    "enum": ["discord", "voice", "text"],
                },
            },
            "required": ["venue", "kind"],
        },
    },
    {
        "name": "remove_from_queue",
        "description": "Remove an item from a queue by substring match.",
        "input_schema": {
            "type": "object",
            "properties": {
                "queue_name": {
                    "type": "string",
                    "enum": ["bookmarks_queue", "social_queue", "rubber_duck_venues"],
                },
                "match": {
                    "type": "string",
                    "description": "Substring of the title/name to remove. First match wins.",
                },
            },
            "required": ["queue_name", "match"],
        },
    },
]


def _tools_for(kind: str) -> List[Dict[str, Any]]:
    if kind in ("morning", "review"):
        return [_RECORD_PRIORITY_TOOL, _READY_TO_SIGN_TOOL]
    if kind == "queues":
        return list(_QUEUE_TOOLS)
    raise ValueError(f"unknown conversation kind: {kind!r}")


# Backwards-compat shim
def _tools() -> List[Dict[str, Any]]:  # pragma: no cover — legacy
    return _tools_for("morning")


# ---------------------------------------------------------------------------
# State containers
# ---------------------------------------------------------------------------


@dataclass
class ContractSettings:
    entertainment_ration_min: int = 60
    threshold_pct: int = 90


@dataclass
class _ConvoState:
    kind: str = "morning"
    history: List[Dict[str, Any]] = field(default_factory=list)
    priorities: List[Priority] = field(default_factory=list)
    settings: ContractSettings = field(default_factory=ContractSettings)
    can_sign: bool = False
    queue_mutations: List[Dict[str, Any]] = field(default_factory=list)
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
    kind: str = "morning"
    queue_mutations: List[Dict[str, Any]] = field(default_factory=list)

    def to_jsonable(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "kind": self.kind,
            "assistant_text": self.assistant_text,
            "priorities": [json.loads(p.model_dump_json()) for p in self.priorities],
            "settings": {
                "entertainment_ration_min": self.settings.entertainment_ration_min,
                "threshold_pct": self.settings.threshold_pct,
            },
            "can_sign": self.can_sign,
            "using_llm": self.using_llm,
            "queue_mutations": self.queue_mutations,
        }


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


_KIND_GREETINGS: Dict[str, str] = {
    "morning": (
        "Good morning. What's important today? "
        "Tell me in your own words — I'll help make it concrete."
    ),
    "review": (
        "Good evening — let's review the day briefly, then plan tomorrow."
    ),
    "queues": (
        "Let's tune your personal queues. Tell me what to add or remove."
    ),
}


class ConversationManager:
    """Per-daemon instance. In-memory state.

    Three conversation kinds are supported (``start(kind=...)``):
      * ``morning``  — bind today's contract (the original flow)
      * ``review``   — nightly reflect; propose tomorrow's contract
      * ``queues``   — add/remove items in the personal queues that
                        sublimation cards reference
    """

    # Backward-compat (one of the existing tests imports it).
    GREETING = _KIND_GREETINGS["morning"]

    def __init__(
        self,
        *,
        use_llm: bool = True,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
        queues_dir: Optional[Path] = None,
    ) -> None:
        self.use_llm = use_llm
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.max_tokens = max_tokens
        self.queues_dir = (
            Path(queues_dir).expanduser() if queues_dir else None
        )
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

    def start(
        self,
        *,
        kind: str = "morning",
        kickoff: Optional[str] = None,
    ) -> tuple[str, str]:
        if kind not in KIND_VOCAB:
            raise ValueError(f"unknown conversation kind: {kind!r}")
        cid = uuid.uuid4().hex[:12]
        state = _ConvoState(kind=kind)
        greeting = _KIND_GREETINGS[kind]
        if kickoff:
            # Inject the runtime context (today's summary / current queues)
            # as the first *user* message so Claude reasons over it.
            state.history.append(
                {"role": "user", "content": [{"type": "text", "text": kickoff}]}
            )
        # Greeting goes into history as the assistant's opening line.
        state.history.append(
            {"role": "assistant", "content": [{"type": "text", "text": greeting}]}
        )
        self.convos[cid] = state
        return cid, greeting

    def respond(self, conversation_id: str, user_message: str) -> ChatTurn:
        state = self.convos.get(conversation_id)
        if state is None:
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
            kind=state.kind,
            assistant_text=text,
            priorities=list(state.priorities),
            settings=state.settings,
            can_sign=state.can_sign,
            using_llm=using_llm,
            queue_mutations=list(state.queue_mutations),
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
        while rounds < 4:
            rounds += 1
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPTS[state.kind],
                tools=_tools_for(state.kind),
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

            if name == "add_bookmark":
                ok, msg = self._mutate_queue(
                    "bookmarks_queue",
                    "add",
                    {
                        "title": args["title"],
                        "url": args["url"],
                        "est_read_min": int(args.get("est_read_min") or 10),
                    },
                )
                if ok:
                    state.queue_mutations.append(
                        {"queue": "bookmarks_queue", "action": "add", "item": args}
                    )
                return ok, msg

            if name == "add_social_contact":
                ok, msg = self._mutate_queue(
                    "social_queue",
                    "add",
                    {
                        "name": args["name"],
                        "channel": args["channel"],
                        "why": args.get("why", ""),
                    },
                )
                if ok:
                    state.queue_mutations.append(
                        {"queue": "social_queue", "action": "add", "item": args}
                    )
                return ok, msg

            if name == "add_rubber_duck_venue":
                ok, msg = self._mutate_queue(
                    "rubber_duck_venues",
                    "add",
                    {"venue": args["venue"], "kind": args["kind"]},
                )
                if ok:
                    state.queue_mutations.append(
                        {"queue": "rubber_duck_venues", "action": "add", "item": args}
                    )
                return ok, msg

            if name == "remove_from_queue":
                ok, msg = self._mutate_queue(
                    args["queue_name"], "remove", {"match": args["match"]}
                )
                if ok:
                    state.queue_mutations.append(
                        {
                            "queue": args["queue_name"],
                            "action": "remove",
                            "match": args["match"],
                        }
                    )
                return ok, msg
        except Exception as exc:
            return False, f"tool error: {exc}"
        return False, f"unknown tool: {name}"

    def _mutate_queue(
        self, queue_name: str, action: str, payload: Dict[str, Any]
    ) -> tuple[bool, str]:
        if self.queues_dir is None:
            return False, "queues_dir not configured on this manager"
        if queue_name not in {
            "bookmarks_queue", "social_queue", "rubber_duck_venues",
        }:
            return False, f"unknown queue: {queue_name}"
        path = self.queues_dir / f"{queue_name}.json"
        items: List[Dict[str, Any]] = []
        if path.is_file():
            try:
                items = json.loads(path.read_text(encoding="utf-8") or "[]")
            except json.JSONDecodeError:
                items = []
        if action == "add":
            # Skip exact duplicates (any equal-string field match).
            sig = json.dumps(payload, sort_keys=True)
            for it in items:
                if json.dumps(it, sort_keys=True) == sig:
                    return True, f"already in {queue_name}"
            items.append(payload)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")
            return True, f"added to {queue_name}"
        if action == "remove":
            match = (payload.get("match") or "").lower()
            kept = []
            removed = 0
            for it in items:
                blob = json.dumps(it).lower()
                if not removed and match in blob:
                    removed += 1
                    continue
                kept.append(it)
            if not removed:
                return False, f"no item in {queue_name} matched {match!r}"
            path.write_text(json.dumps(kept, indent=2) + "\n", encoding="utf-8")
            return True, f"removed 1 from {queue_name}"
        return False, f"unknown action: {action}"

    # ------------------------------------------------------------------
    # Fallback path (no API key) — strict state-machine, plain regex
    # ------------------------------------------------------------------

    def _fallback_turn(self, state: _ConvoState, user_message: str) -> str:
        # Queue maintenance without an LLM is too varied for a clean
        # state machine; tell the user to set an API key.
        if state.kind == "queues":
            return (
                "Queue maintenance needs the LLM (set ANTHROPIC_API_KEY and "
                "restart with --use-llm). For now, you can edit the JSON "
                "files in agent/founder_loop/data/queues/ directly."
            )
        # Review and morning share the same fallback shape — the
        # difference (today vs tomorrow) is server-side at /sign time.
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
