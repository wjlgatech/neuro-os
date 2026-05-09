"""
Pattern extraction — turn ≥N override events into SkillProposals.

The v0 extractor is intentionally simple: bucket events by
(vertical, drift_mode), emit one SkillProposal per bucket with
``based_on_event_count >= threshold``. The candidate_action picked is
the most-frequent user_action text across the bucket (ties broken by
recency — most-recent wins).

This is the smallest move that respects Garry Tan's "skillify"
pattern: the system notices a workflow you've repeated and offers to
codify it. Smarter clustering (semantic similarity, action sequence
mining) is a follow-up; v0 ships exact-string match because the user
controls the input text and exact repetition IS a signal worth
catching.

The output proposals land in
``~/.neuro_os_skillified/proposals/pending/`` for human review via
``skillify review --cli`` (Law 7).
"""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from agent.skillify.events import (
    OverrideEvent,
    VerticalName,
    read_override_events,
)
from agent.skillify.proposals import (
    SkillProposal,
    list_skill_proposals,
    write_skill_proposal,
)


DEFAULT_THRESHOLD = 5
DEFAULT_WINDOW_DAYS = 30


def _bucket_key(event: OverrideEvent) -> Tuple[str, str]:
    return (event.vertical, event.drift_mode)


def _pick_candidate_action(events: List[OverrideEvent]) -> str:
    """Most-frequent user_action; ties broken by recency (newest wins)."""
    counts = Counter(e.user_action for e in events)
    most_common_count = counts.most_common(1)[0][1]
    candidates = {k for k, c in counts.items() if c == most_common_count}
    # Recency tie-break: walk newest-first, return first one in candidates.
    for ev in sorted(events, key=lambda e: e.ts, reverse=True):
        if ev.user_action in candidates:
            return ev.user_action
    return events[-1].user_action  # fallback (shouldn't reach)


def extract_pattern(
    events: List[OverrideEvent],
    *,
    threshold: int = DEFAULT_THRESHOLD,
    now: Optional[datetime] = None,
) -> List[SkillProposal]:
    """Group ``events`` by (vertical, drift_mode), emit one SkillProposal
    per bucket whose count meets ``threshold``.

    Pure function — does NOT write to disk. The caller decides whether
    to persist via ``write_skill_proposal``.
    """
    when = now or datetime.now(timezone.utc)
    buckets: Dict[Tuple[str, str], List[OverrideEvent]] = {}
    for ev in events:
        buckets.setdefault(_bucket_key(ev), []).append(ev)

    proposals: List[SkillProposal] = []
    for (vertical, drift_mode), bucket_events in buckets.items():
        if len(bucket_events) < threshold:
            continue
        candidate = _pick_candidate_action(bucket_events)
        proposals.append(SkillProposal(
            proposal_id=f"skill-{vertical}-{drift_mode}-{uuid.uuid4().hex[:8]}",
            proposed_at=when,
            status="pending",
            vertical=vertical,
            drift_mode=drift_mode,
            candidate_action=candidate,
            candidate_duration_min=20,
            candidate_tank_credit_pct=5.0,
            based_on_event_count=len(bucket_events),
            based_on_event_ids=[e.event_id for e in bucket_events],
            extracted_at=when,
            notes=(
                f"Extracted from {len(bucket_events)} override events on "
                f"{vertical}/{drift_mode}. Most-frequent user_action selected "
                f"as candidate (ties broken by recency)."
            ),
        ))
    # Stable order for testability:
    proposals.sort(key=lambda p: (p.vertical, p.drift_mode))
    return proposals


def _bucket_already_proposed(
    *,
    vertical: VerticalName,
    drift_mode: str,
    home: Optional[Path] = None,
) -> bool:
    """A bucket has been "already proposed" if a pending OR accepted
    proposal exists for the same (vertical, drift_mode). Rejected
    proposals do NOT count — the user can try the bucket again with
    new override evidence."""
    for status in ("pending", "accepted"):
        existing = list_skill_proposals(home=home, status=status)
        for p in existing:
            if p.vertical == vertical and p.drift_mode == drift_mode:
                return True
    return False


def run_extraction(
    *,
    vertical: Optional[VerticalName] = None,
    threshold: int = DEFAULT_THRESHOLD,
    window_days: int = DEFAULT_WINDOW_DAYS,
    home: Optional[Path] = None,
    now: Optional[datetime] = None,
    skip_already_proposed: bool = True,
) -> List[SkillProposal]:
    """End-to-end: read events from disk, run extract_pattern, optionally
    skip buckets we've already proposed for, and persist the new
    proposals to ``proposals/pending/``.

    Returns the list of NEWLY-WRITTEN proposals (already-proposed
    buckets are silently filtered out unless ``skip_already_proposed=False``).
    """
    when = now or datetime.now(timezone.utc)
    since = when - timedelta(days=window_days)
    events = read_override_events(home=home, vertical=vertical, since=since)
    candidates = extract_pattern(events, threshold=threshold, now=when)

    written: List[SkillProposal] = []
    for proposal in candidates:
        if skip_already_proposed and _bucket_already_proposed(
            vertical=proposal.vertical,
            drift_mode=proposal.drift_mode,
            home=home,
        ):
            continue
        write_skill_proposal(proposal, home=home)
        written.append(proposal)
    return written


__all__ = [
    "DEFAULT_THRESHOLD",
    "DEFAULT_WINDOW_DAYS",
    "extract_pattern",
    "run_extraction",
]
