"""
Research-vertical proposals queue.

On-disk layout under ``~/.neuro_os_research/proposals/`` (or any
``home`` passed by tests):

    proposals/
    ├── pending/   <id>.json   ← one MechanismCardProposal per file
    ├── accepted/  <id>.json
    └── rejected/  <id>.json

The status field on disk MUST match the parent directory; that
invariant is asserted on every read. This makes the queue trivially
auditable: ``ls proposals/pending/ | wc -l`` is exactly the
human-review backlog.

Acceptance is the ONLY path that calls
``agent.research.config.write_mechanism_card`` — the ingestion sensor
NEVER writes mechanism cards directly. That keeps Law 7 (human-in-loop
truth control) intact: the sensor proposes, the user disposes.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional, Set

from agent.research.ontology import MechanismCardProposal


ProposalStatus = Literal["pending", "accepted", "rejected"]


# ---------------------------------------------------------------------------
# Mechanism-level dedup (Gap 2 + Gap 3).
#
# Two proposals are considered the same mechanism if their normalized
# (mechanism, invariant) text matches exactly. Normalization: lowercased,
# whitespace-collapsed, punctuation stripped. The hash is short (16 hex
# chars) and stored only in memory / response payloads — no schema change.
# ---------------------------------------------------------------------------

_NORM_RE = re.compile(r"[^a-z0-9]+")


def _normalize_text(s: str) -> str:
    return _NORM_RE.sub(" ", (s or "").lower()).strip()


def compute_mechanism_hash(mechanism: str, invariant: str) -> str:
    """Stable 16-hex-char hash of (mechanism + invariant), case- and
    whitespace-insensitive. Two proposals with the same hash describe
    the same idea (within the limits of normalized text equality)."""
    payload = _normalize_text(mechanism) + " || " + _normalize_text(invariant)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def proposal_hash(p: MechanismCardProposal) -> str:
    """Hash for a `MechanismCardProposal`. Convenience wrapper."""
    return compute_mechanism_hash(p.mechanism, p.invariant)


def existing_mechanism_hashes(
    *,
    home: Optional[Path] = None,
    statuses: tuple = ("pending", "accepted"),
) -> Set[str]:
    """Return the set of mechanism hashes already on disk across the
    given statuses. Used by ingest to skip writing a proposal whose
    mechanism is already in the queue (or already accepted)."""
    out: Set[str] = set()
    for status in statuses:
        for prop in list_proposals(home=home, status=status):
            out.add(proposal_hash(prop))
    return out


def _proposals_root(home: Optional[Path] = None) -> Path:
    base = home or (Path.home() / ".neuro_os_research")
    return base / "proposals"


def _status_dir(home: Optional[Path], status: ProposalStatus) -> Path:
    return _proposals_root(home) / status


def ensure_dirs(home: Optional[Path] = None) -> None:
    """Create pending/accepted/rejected if they don't already exist."""
    for status in ("pending", "accepted", "rejected"):
        _status_dir(home, status).mkdir(parents=True, exist_ok=True)  # type: ignore[arg-type]


def write_proposal(
    proposal: MechanismCardProposal,
    *,
    home: Optional[Path] = None,
) -> Path:
    """Atomically write one proposal to ``proposals/<status>/<id>.json``.

    The write is atomic (temp-file + rename) so a crash mid-write
    doesn't leave a half-written JSON file in the queue.
    """
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
        # Best-effort cleanup; swallow if tmp_path already moved.
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise
    return target


def read_proposal(
    proposal_id: str,
    *,
    home: Optional[Path] = None,
    status: ProposalStatus = "pending",
) -> MechanismCardProposal:
    """Read one proposal by id from a specific status directory."""
    path = _status_dir(home, status) / f"{proposal_id}.json"
    return MechanismCardProposal.model_validate_json(path.read_text(encoding="utf-8"))


def list_proposals(
    *,
    home: Optional[Path] = None,
    status: ProposalStatus = "pending",
    limit: Optional[int] = None,
) -> List[MechanismCardProposal]:
    """Return all proposals in ``proposals/<status>/``, sorted by
    ``proposed_at`` ascending. ``limit`` caps the return (None = all)."""
    sdir = _status_dir(home, status)
    if not sdir.exists():
        return []
    paths = sorted(sdir.glob("*.json"))
    out: List[MechanismCardProposal] = []
    for p in paths:
        try:
            out.append(
                MechanismCardProposal.model_validate_json(p.read_text(encoding="utf-8"))
            )
        except Exception:
            # Malformed file in the queue — skip rather than crash the whole
            # review surface. The user can inspect the bad file manually.
            continue
    out.sort(key=lambda x: x.proposed_at)
    return out[:limit] if limit else out


def transition_proposal(
    proposal_id: str,
    *,
    home: Optional[Path] = None,
    from_status: ProposalStatus = "pending",
    to_status: ProposalStatus,
) -> MechanismCardProposal:
    """Move a proposal from one status directory to another, returning
    the updated (frozen) proposal with the new status field set.

    Implementation: read → produce a new frozen proposal with
    ``status=to_status`` → write to to_status dir → delete the source
    file. The two-step write+delete is the closest we get to atomic
    cross-directory move within a single filesystem.
    """
    if from_status == to_status:
        raise ValueError(
            f"transition_proposal: from_status == to_status ({from_status!r})"
        )
    src = _status_dir(home, from_status) / f"{proposal_id}.json"
    if not src.exists():
        raise FileNotFoundError(f"proposal {proposal_id!r} not found in {from_status}/")
    original = MechanismCardProposal.model_validate_json(src.read_text(encoding="utf-8"))
    updated = original.model_copy(update={"status": to_status})
    write_proposal(updated, home=home)
    src.unlink()
    return updated


def now_utc() -> datetime:
    """Helper used by extractors so tests can monkeypatch it."""
    return datetime.now(timezone.utc)
