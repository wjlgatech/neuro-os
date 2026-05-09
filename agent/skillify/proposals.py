"""
Skill proposals — pattern-extracted candidate ConstructiveExpressions.

When the user has logged ≥N OverrideEvents on the same (vertical,
drift_mode), the extractor proposes a SkillProposal: "users seem to
prefer X over the catalog default — promote X to a new
ConstructiveExpression?". The proposal is then human-gated via
``skillify review --cli`` (Law 7).

Mirror of agent/research/proposals.py shape — same status-dir
invariant (pending / accepted / rejected).
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from agent.skillify.events import VerticalName


ProposalStatus = Literal["pending", "accepted", "rejected"]


class SkillProposal(BaseModel):
    """One pattern-extracted candidate.

    Frozen — once proposed, the proposal is immutable. User edits
    happen via a new proposal that supersedes; rejection moves the
    file to ``rejected/`` (audit trail).
    """

    model_config = ConfigDict(frozen=True)

    proposal_id: str = Field(min_length=1, max_length=128)
    proposed_at: datetime
    status: ProposalStatus = "pending"

    vertical: VerticalName
    drift_mode: str = Field(min_length=1, max_length=64)

    # The proposed ConstructiveExpression (mirrors substrate's
    # ConstructiveExpressionBase shape):
    candidate_action: str = Field(
        min_length=1, max_length=400,
        description="What the new ConstructiveExpression would propose. "
                    "Pulled from the most-frequent user_action across the "
                    "underlying OverrideEvents.",
    )
    candidate_duration_min: int = Field(ge=1, le=240, default=20)
    candidate_tank_credit_pct: float = Field(ge=0.0, le=100.0, default=5.0)

    # Evidence:
    based_on_event_count: int = Field(ge=1, description="N OverrideEvents.")
    based_on_event_ids: List[str] = Field(
        min_length=1, max_length=100,
        description="The OverrideEvent ids this proposal aggregates over.",
    )
    extracted_at: datetime
    notes: Optional[str] = Field(default=None, max_length=1000)


# ---------------------------------------------------------------------------
# Disk layout (mirror of research/proposals.py)
# ---------------------------------------------------------------------------


def _proposals_root(home: Optional[Path] = None) -> Path:
    base = home or (Path.home() / ".neuro_os_skillified")
    return base / "proposals"


def _status_dir(home: Optional[Path], status: ProposalStatus) -> Path:
    return _proposals_root(home) / status


def ensure_dirs(home: Optional[Path] = None) -> None:
    for status in ("pending", "accepted", "rejected"):
        _status_dir(home, status).mkdir(parents=True, exist_ok=True)  # type: ignore[arg-type]


def write_skill_proposal(
    proposal: SkillProposal,
    *,
    home: Optional[Path] = None,
) -> Path:
    """Atomic write to ``proposals/<status>/<id>.json``."""
    ensure_dirs(home)
    target = _status_dir(home, proposal.status) / f"{proposal.proposal_id}.json"
    body = proposal.model_dump_json(indent=2)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{proposal.proposal_id}.",
        suffix=".json.tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise
    return target


def read_skill_proposal(
    proposal_id: str,
    *,
    home: Optional[Path] = None,
    status: ProposalStatus = "pending",
) -> SkillProposal:
    path = _status_dir(home, status) / f"{proposal_id}.json"
    return SkillProposal.model_validate_json(path.read_text(encoding="utf-8"))


def list_skill_proposals(
    *,
    home: Optional[Path] = None,
    status: ProposalStatus = "pending",
    limit: Optional[int] = None,
) -> List[SkillProposal]:
    sdir = _status_dir(home, status)
    if not sdir.exists():
        return []
    out: List[SkillProposal] = []
    for p in sorted(sdir.glob("*.json")):
        try:
            out.append(SkillProposal.model_validate_json(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    out.sort(key=lambda x: x.proposed_at)
    return out[:limit] if limit else out


def transition_skill_proposal(
    proposal_id: str,
    *,
    home: Optional[Path] = None,
    from_status: ProposalStatus = "pending",
    to_status: ProposalStatus,
) -> SkillProposal:
    if from_status == to_status:
        raise ValueError(
            f"transition_skill_proposal: from_status == to_status ({from_status!r})"
        )
    src = _status_dir(home, from_status) / f"{proposal_id}.json"
    if not src.exists():
        raise FileNotFoundError(
            f"skill proposal {proposal_id!r} not found in {from_status}/"
        )
    original = SkillProposal.model_validate_json(src.read_text(encoding="utf-8"))
    updated = original.model_copy(update={"status": to_status})
    write_skill_proposal(updated, home=home)
    src.unlink()
    return updated


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "ProposalStatus",
    "SkillProposal",
    "ensure_dirs",
    "write_skill_proposal",
    "read_skill_proposal",
    "list_skill_proposals",
    "transition_skill_proposal",
    "now_utc",
]
