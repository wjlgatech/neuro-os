"""
``agent.skillify`` — meta-skill that turns repeated user overrides into
catalog-revision proposals (Lane 2 of the 5-lane plan).

Pattern (Garry Tan's "skillify"):
1. The substrate proposes a ConstructiveExpression for a drift mode.
2. The user picks something else and logs it via
   ``neuro-os skillify log-override --vertical research --drift
   paper_collector --user-action "I extracted into a Markdown brief"``.
3. After ≥N (default 5) overrides on the same (vertical, drift_mode),
   ``neuro-os skillify extract`` proposes a new ConstructiveExpression
   candidate to ``~/.neuro_os_skillified/proposals/pending/``.
4. The user reviews via ``neuro-os skillify review --cli`` and accepts
   or rejects. Acceptance does NOT auto-mutate the catalog (Law 7) —
   it just promotes the proposal file to ``accepted/`` so a human
   author can fold the change into the vertical's catalog.py in a
   follow-up commit.

Storage layout under ``~/.neuro_os_skillified/``:

    events.jsonl                     ← OverrideEvent log (append-only)
    proposals/
        pending/   <id>.json
        accepted/  <id>.json
        rejected/  <id>.json
"""
from __future__ import annotations

from agent.skillify.events import (
    OverrideEvent,
    VerticalName,
    read_override_events,
    write_override_event,
)
from agent.skillify.extract import (
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW_DAYS,
    extract_pattern,
    run_extraction,
)
from agent.skillify.proposals import (
    ProposalStatus,
    SkillProposal,
    list_skill_proposals,
    read_skill_proposal,
    transition_skill_proposal,
    write_skill_proposal,
)


__all__ = [
    # events
    "OverrideEvent",
    "VerticalName",
    "read_override_events",
    "write_override_event",
    # proposals
    "ProposalStatus",
    "SkillProposal",
    "list_skill_proposals",
    "read_skill_proposal",
    "transition_skill_proposal",
    "write_skill_proposal",
    # extraction
    "DEFAULT_THRESHOLD",
    "DEFAULT_WINDOW_DAYS",
    "extract_pattern",
    "run_extraction",
]
