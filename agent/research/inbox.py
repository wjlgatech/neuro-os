"""
URL-to-Living-Knowledge inbox — typed JSONL contract for external producers.

External producers (Hermes Gmail watcher, Telegram bot, browser
share-target, manual curl) drop pre-extracted text into a single
append-only JSONL file at ``~/.neuro_os_research/inbox.jsonl``. The
neuro-os ingestor reads new records, optionally filters by sender
allowlist, then funnels each record through the existing
``extract_mechanisms`` pipeline so the downstream review / compress /
expression layers don't need to know the source was a URL.

Two design choices worth knowing:

* **No new extraction layer.** The inbox does NOT call an LLM itself.
  It accepts pre-extracted body text (the producer has already pulled
  the YouTube transcript / blog markdown / X thread / PDF page text)
  and stages it as a ``RawSource`` so ``extract_mechanisms`` runs as if
  it were a local file. This keeps a single extractor code path.

* **Cursor file, not delete-on-consume.** The inbox is append-only;
  the consumer writes a sibling ``inbox.cursor`` recording the highest
  line offset already processed. Re-running ingest is idempotent;
  losing the cursor at worst re-extracts (sha256 dedup catches it).

Law-compliance notes:
  * Law 1: ``InboxRecord`` is a frozen Pydantic model. Malformed JSON
    lines are skipped with a logged warning, not silently accepted.
  * Law 5: ``InboxRunSummary`` is frozen and returned to callers; no
    dict escape hatch.
  * Law 11: inbox.jsonl + inbox.cursor + inbox_allowlist.json all live
    under ``~/.neuro_os_research/`` (already in .gitignore).
"""
from __future__ import annotations

import hashlib
import json
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from agent.research.framework import EMPTY_FRAMEWORK, Framework
from agent.research.ingest import LLMCallable, extract_mechanisms
from agent.research.ontology import MechanismCardProposal, RawSource
from agent.research.proposals import list_proposals, write_proposal


logger = logging.getLogger(__name__)


# Source type the producer is telling us about. Open vocabulary —
# anything not in the list falls under "other" and still ingests.
InboxSourceType = Literal[
    "youtube",
    "blog",
    "twitter",
    "pdf",
    "email-body",
    "other",
]


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class InboxRecord(BaseModel):
    """One pre-extracted source the producer dropped into inbox.jsonl.

    Frozen — the inbox is an immutable append-only log; consumers
    transform records into ``RawSource`` + proposals, they don't mutate
    the inbox row.
    """

    model_config = ConfigDict(frozen=True)

    url: str = Field(
        min_length=1,
        max_length=2000,
        description="Original URL the producer ingested. Becomes the "
                    "MechanismCardProposal.paper_source.",
    )
    source_type: InboxSourceType
    title: str = Field(min_length=1, max_length=400)
    author: str = Field(default="unknown", min_length=1, max_length=200)
    extracted_text: str = Field(
        min_length=1,
        max_length=400_000,
        description="Body text the producer already pulled (transcript / "
                    "markdown / thread text). Hermes does its own "
                    "source-type-specific extraction upstream.",
    )
    extracted_at: datetime
    sender: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Producer-attested sender identity (e.g. email "
                    "From: header). Checked against the optional "
                    "allowlist at ingest time. None means anonymous.",
    )
    urge_tag: Optional[str] = Field(
        default=None,
        max_length=64,
        description="If the producer knows this URL was sent during an "
                    "active founder-loop drift mode (novelty / social / "
                    "frustration / fatigue / decision_fatigue / "
                    "embodied), tag it here. None means unknown.",
    )
    topic_tags: List[str] = Field(default_factory=list, max_length=20)


class InboxRunSummary(BaseModel):
    """End-of-run audit for one ``process_inbox`` invocation.

    Frozen so the audit trail can't be mutated post-write. Returned to
    CLI / HTTP callers (Law 5: no dict returns to user surfaces).
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1, max_length=64)
    started_at: datetime
    finished_at: datetime
    records_seen: int = Field(ge=0)
    records_skipped_disallowed: int = Field(
        ge=0,
        description="Skipped because sender wasn't on the allowlist.",
    )
    records_skipped_duplicate: int = Field(
        ge=0,
        description="Skipped because a proposal with the same source_id "
                    "already exists (sha256-based dedup).",
    )
    proposals_emitted: int = Field(ge=0)
    cursor_advanced_to: int = Field(
        ge=0,
        description="The highest 0-indexed line offset consumed by this "
                    "run. Persisted to inbox.cursor.",
    )


# --------------------------------------------------------------------------
# Filesystem layout
# --------------------------------------------------------------------------


def _research_home(home: Optional[Path]) -> Path:
    return home if home is not None else (Path.home() / ".neuro_os_research")


def default_inbox_path(home: Optional[Path] = None) -> Path:
    return _research_home(home) / "inbox.jsonl"


def default_cursor_path(home: Optional[Path] = None) -> Path:
    return _research_home(home) / "inbox.cursor"


def default_allowlist_path(home: Optional[Path] = None) -> Path:
    return _research_home(home) / "inbox_allowlist.json"


# --------------------------------------------------------------------------
# Append / read
# --------------------------------------------------------------------------


def append_to_inbox(
    record: InboxRecord,
    *,
    home: Optional[Path] = None,
) -> int:
    """Append one record to inbox.jsonl. Returns the new line offset.

    Producers (Hermes, curl, shell) call this OR write the JSON line
    themselves — both forms are equivalent because the schema is the
    contract.
    """
    path = default_inbox_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        json.loads(record.model_dump_json()),
        ensure_ascii=False,
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    # Return the new offset (0-indexed line of this record).
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def fetch_url_to_inbox(
    url: str,
    *,
    source_type: str = "auto",
    home: Optional[Path] = None,
    stored_url: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    sender: Optional[str] = None,
    urge_tag: Optional[str] = None,
    topic_tags: Optional[List[str]] = None,
    now: Optional[datetime] = None,
) -> Tuple[int, InboxRecord]:
    """Standalone path: fetch ``url`` over the network, extract its text,
    and append one :class:`InboxRecord` to the inbox — no external
    producer required.

    This is the library entry point behind ``research inbox append
    --fetch-url``. ``source_type="auto"`` detects from the URL host.
    ``stored_url`` / ``title`` / ``author`` override the fetched values
    when given (None = use what the fetcher derived).

    Raises :class:`~agent.research.fetch.FetchError` for an unreachable
    URL, an empty page, or a non-fetchable source type (pdf /
    email-body). The fetch step is the only network access in the inbox
    pipeline; everything downstream is local.

    Returns ``(line_offset, record)``.
    """
    from agent.research.fetch import fetch_url

    fetched = fetch_url(url, source_type=source_type)
    record = InboxRecord(
        url=stored_url or fetched.url,
        source_type=fetched.source_type,
        title=title or fetched.title,
        author=author or fetched.author,
        extracted_text=fetched.extracted_text,
        extracted_at=now or datetime.now(timezone.utc),
        sender=sender,
        urge_tag=urge_tag,
        topic_tags=list(topic_tags or []),
    )
    offset = append_to_inbox(record, home=home)
    return offset, record


def _read_cursor(home: Optional[Path]) -> int:
    cursor = default_cursor_path(home)
    if not cursor.exists():
        return -1
    try:
        return int(cursor.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return -1


def _write_cursor(home: Optional[Path], offset: int) -> None:
    cursor = default_cursor_path(home)
    cursor.parent.mkdir(parents=True, exist_ok=True)
    cursor.write_text(str(offset), encoding="utf-8")


def read_pending(
    *,
    home: Optional[Path] = None,
) -> List[Tuple[int, InboxRecord]]:
    """Return ``(line_offset, record)`` pairs for all inbox lines whose
    offset is greater than the cursor.

    Malformed JSON lines are skipped with a logged warning so a single
    bad row from a producer doesn't block the queue. Pydantic
    validation runs per-line (Law 1).
    """
    path = default_inbox_path(home)
    if not path.exists():
        return []
    cursor = _read_cursor(home)
    out: List[Tuple[int, InboxRecord]] = []
    with path.open("r", encoding="utf-8") as f:
        for offset, raw in enumerate(f):
            if offset <= cursor:
                continue
            raw = raw.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.warning(
                    "inbox.read_pending: dropped line %d (bad JSON: %s)",
                    offset, e,
                )
                continue
            try:
                record = InboxRecord.model_validate(payload)
            except Exception as e:
                logger.warning(
                    "inbox.read_pending: dropped line %d (schema: %s)",
                    offset, e,
                )
                continue
            out.append((offset, record))
    return out


# --------------------------------------------------------------------------
# Allowlist
# --------------------------------------------------------------------------


def load_allowlist(home: Optional[Path] = None) -> Optional[set[str]]:
    """Return the set of allowed senders, or None if no allowlist file
    exists.

    Empty file / missing file = no restriction (every record passes).
    This keeps the inbox usable for solo / personal use; teams or
    public-facing deployments populate the file with the allowed
    From: addresses.
    """
    path = default_allowlist_path(home)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(
            "inbox.load_allowlist: failed to parse %s (%s); treating "
            "as no restriction",
            path, e,
        )
        return None
    if isinstance(payload, list):
        return {str(s).strip().lower() for s in payload if str(s).strip()}
    if isinstance(payload, dict) and isinstance(payload.get("senders"), list):
        return {
            str(s).strip().lower()
            for s in payload["senders"]
            if str(s).strip()
        }
    logger.warning(
        "inbox.load_allowlist: %s has unexpected shape; expected "
        "list[str] or {senders: list[str]}",
        path,
    )
    return None


def _sender_allowed(record: InboxRecord, allowlist: Optional[set[str]]) -> bool:
    if allowlist is None or len(allowlist) == 0:
        return True
    if record.sender is None:
        return False
    return record.sender.strip().lower() in allowlist


# --------------------------------------------------------------------------
# Stage record → RawSource → proposals
# --------------------------------------------------------------------------


def _stage_record_as_raw_source(
    record: InboxRecord,
    *,
    home: Optional[Path],
) -> Tuple[Optional[RawSource], str]:
    """Materialize one InboxRecord into a (RawSource, tempfile_path) pair.

    The temp file holds the body so ``extract_mechanisms`` can read it
    via its existing path-based contract. Caller is responsible for
    unlinking the temp file once extraction completes.

    Returns ``(None, "")`` when the record would be a duplicate of an
    existing proposal (sha256 dedup). In that case nothing is written.
    """
    body = record.extracted_text
    sha = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()
    source_id = f"inbox:{record.source_type}:{sha[:12]}"

    # Reuse the same dedup signal Plan A uses.
    existing: set[str] = set()
    for status in ("pending", "accepted", "rejected"):
        for prop in list_proposals(home=home, status=status):
            existing.add(prop.source_id)
    if source_id in existing:
        return (None, "")

    # Stage to a temp file inside the research home so the path stays
    # readable for the lifetime of the run. We unlink after extraction.
    home_dir = _research_home(home)
    home_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = home_dir / ".inbox_stage"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        prefix="inbox_",
        suffix=".txt",
        dir=str(tmp_dir),
    )
    tmp_path = Path(tmp_path_str)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(body)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    source = RawSource(
        source_id=source_id,
        path=tmp_path,
        title=record.title[:400],
        author=record.author[:200],
        publish_date=None,
        source_url=record.url,
        topic_tags=list(record.topic_tags),
        word_count=len(body.split()),
        sha256=sha,
    )
    return (source, str(tmp_path))


def _attach_urge_tag_to_proposals(
    proposals: List[MechanismCardProposal],
    urge_tag: Optional[str],
) -> List[MechanismCardProposal]:
    """Append the urge tag (if any) as the first topic_tags entry on the
    underlying RawSource — but RawSource isn't carried into the proposal.
    Instead, we surface it via ``reasoning`` prefix so the reviewer sees
    "this URL came in during a `novelty` urge" right at the review
    surface. Frozen models → return new instances.
    """
    if not urge_tag:
        return proposals
    tagged: List[MechanismCardProposal] = []
    prefix = f"[urge:{urge_tag}] "
    for prop in proposals:
        # Skip re-tagging if the prefix is already present (idempotent).
        new_reasoning = (
            prop.reasoning
            if prop.reasoning.startswith(prefix)
            else (prefix + prop.reasoning)[:1000]
        )
        tagged.append(prop.model_copy(update={"reasoning": new_reasoning}))
    return tagged


# --------------------------------------------------------------------------
# End-to-end
# --------------------------------------------------------------------------


def process_inbox(
    *,
    llm_fn: Optional[LLMCallable] = None,
    home: Optional[Path] = None,
    framework: Optional[Framework] = None,
    allowlist: Optional[set[str]] = None,
    now: Optional[datetime] = None,
) -> InboxRunSummary:
    """End-to-end: read pending inbox records → optional allowlist filter
    → stage as RawSource → extract → write proposals → advance cursor.

    ``allowlist`` defaults to the disk allowlist when None. Pass an
    explicit empty set to force "deny all unauthenticated"; pass an
    explicit set to override the disk file.
    """
    started = now or datetime.now(timezone.utc)
    if allowlist is None:
        allowlist = load_allowlist(home)
    if framework is None:
        from agent.research.framework import load_framework
        framework = load_framework(home=home)
    framework = framework or EMPTY_FRAMEWORK

    pending = read_pending(home=home)
    records_skipped_disallowed = 0
    records_skipped_duplicate = 0
    proposals_emitted = 0
    highest_offset_consumed = _read_cursor(home)

    for offset, record in pending:
        if not _sender_allowed(record, allowlist):
            records_skipped_disallowed += 1
            highest_offset_consumed = offset
            logger.info(
                "inbox.process_inbox: skipping line %d (sender %r not on "
                "allowlist)", offset, record.sender,
            )
            continue

        try:
            source, tmp_path_str = _stage_record_as_raw_source(
                record, home=home,
            )
        except Exception as e:
            logger.warning(
                "inbox.process_inbox: failed to stage line %d (%s); "
                "advancing cursor anyway", offset, e,
            )
            highest_offset_consumed = offset
            continue

        if source is None:
            records_skipped_duplicate += 1
            highest_offset_consumed = offset
            continue

        try:
            proposals = extract_mechanisms(
                source,
                llm_fn=llm_fn,
                now=started,
                framework=framework,
            )
            proposals = _attach_urge_tag_to_proposals(
                proposals, record.urge_tag,
            )
            for prop in proposals:
                write_proposal(prop, home=home)
            proposals_emitted += len(proposals)
        finally:
            # Clean up the staged temp file unconditionally.
            try:
                Path(tmp_path_str).unlink(missing_ok=True)
            except OSError as e:
                logger.info(
                    "inbox.process_inbox: temp file cleanup failed (%s); "
                    "harmless but worth a note", e,
                )
        highest_offset_consumed = offset

    if highest_offset_consumed >= 0:
        _write_cursor(home, highest_offset_consumed)

    finished = datetime.now(timezone.utc)
    return InboxRunSummary(
        run_id=uuid.uuid4().hex[:12],
        started_at=started,
        finished_at=finished,
        records_seen=len(pending),
        records_skipped_disallowed=records_skipped_disallowed,
        records_skipped_duplicate=records_skipped_duplicate,
        proposals_emitted=proposals_emitted,
        cursor_advanced_to=max(highest_offset_consumed, 0),
    )


__all__ = [
    "InboxRecord",
    "InboxRunSummary",
    "InboxSourceType",
    "append_to_inbox",
    "default_allowlist_path",
    "default_cursor_path",
    "default_inbox_path",
    "fetch_url_to_inbox",
    "load_allowlist",
    "process_inbox",
    "read_pending",
]
