"""
gbrain → MechanismCardProposal adapter (Plan B for the L0–L1 ingestion sensor).

Treats `garrytan/gbrain <https://github.com/garrytan/gbrain>`_ as a
first-class upstream sensor: gbrain owns L0–L2 (raw input → entity
graph) + L8 (retrieval); the research vertical owns L3+ (drift catalogs,
calibration, cross-vertical privacy). The contract between them is one
schema (``MechanismCardProposal``) and one transport (gbrain MCP).

This module ships the **translation layer** only. v0 implementation
notes:

* ``fetch_entities`` is the gbrain MCP call site. v0 ships a
  ``call_gbrain`` callable parameter so tests inject a deterministic
  fixture and the production wiring (a real MCP client) can be added
  later without changing the contract.
* ``translate`` is conservative: borderline entities are skipped
  (``None`` returned) rather than emitted as low-quality proposals. The
  skip reason is logged for the audit trail.
* ``ingest`` is the public entry point: glue between fetch → translate
  → ``proposals.write_proposal``.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from agent.research.ontology import (
    GbrainEntity,
    GbrainQuerySpec,
    IngestionRun,
    MechanismCardProposal,
)
from agent.research.proposals import write_proposal


logger = logging.getLogger(__name__)


# Sentinel for a fetch callable signature. The callable receives the
# pinned query spec and returns a JSON-deserializable list of dicts that
# will be parsed into ``GbrainEntity``. Keeping the wire format as
# ``list[dict]`` (rather than ``list[GbrainEntity]``) lets us validate at
# the boundary — a malformed gbrain response raises a typed
# ValidationError instead of silently producing garbage proposals.
GbrainFetchCallable = Callable[[GbrainQuerySpec], List[dict]]


# ---------------------------------------------------------------------------
# Translation policy (the heart of the adapter).
# ---------------------------------------------------------------------------


# Verbs that suggest causal structure, used to detect mechanism-shaped claims
# in the gbrain body excerpt. These are intentionally conservative — false
# negatives (we skip a real mechanism) are recoverable in /research-review;
# false positives flood the queue with junk.
_MECHANISM_VERBS = re.compile(
    r"\b(cause|causes|because|drives?|forces?|produces?|results? in|"
    r"leads? to|implies|requires?|generates?|breaks? when|fails? when)\b",
    re.IGNORECASE,
)

# "When X happens, Y occurs" — a cheap falsifiable-prediction shape.
_PREDICTION_PATTERN = re.compile(
    r"\b(when|if)\b[^.]{5,}\b(then|will|should|expect|predict)\b",
    re.IGNORECASE,
)


def translate(
    entity: GbrainEntity,
    *,
    source_query: str,
    now: Optional[datetime] = None,
) -> Optional[MechanismCardProposal]:
    """Translate one gbrain entity into a ``MechanismCardProposal``.

    Returns ``None`` if the entity isn't mechanism-shaped enough to
    fill 4 fields confidently. The skip reason is logged at INFO level
    so ``research ingest --debug`` can show the audit trail.

    Conservative skip rules:
      1. ``page_kind != "claim"`` — people / companies / topics aren't
         mechanisms by themselves (those become entity-graph nodes in
         Lane 4, not proposal candidates here).
      2. body excerpt < 100 chars — too thin to support 4 distinct
         fields.
      3. no causal-verb match in the body excerpt — probably a
         description, not a mechanism (Law 2, prompt-time enforcement).
    """
    when = now or datetime.now(timezone.utc)

    if entity.page_kind != "claim":
        logger.info(
            "gbrain_adapter.translate: skip slug=%r reason=non-claim kind=%s",
            entity.slug, entity.page_kind,
        )
        return None
    if len(entity.body_excerpt) < 100:
        logger.info(
            "gbrain_adapter.translate: skip slug=%r reason=thin len=%d",
            entity.slug, len(entity.body_excerpt),
        )
        return None
    if not _MECHANISM_VERBS.search(entity.body_excerpt):
        logger.info(
            "gbrain_adapter.translate: skip slug=%r reason=no-causal-verb",
            entity.slug,
        )
        return None

    # Mechanism = first 500 chars of the body excerpt (gbrain does the
    # heavy lifting upstream; we trust its synthesis).
    mechanism = entity.body_excerpt[:500].strip()

    # Invariant = first typed_relationship of "causes" / "requires" /
    # "entails" if present, else a default scaffold the user can edit
    # in /research-review.
    invariant = _pick_invariant(entity)

    # Prediction = the first sentence containing a falsifiable shape
    # ("when X then Y"), else a default scaffold.
    prediction = _pick_prediction(entity)

    # Failure mode = a default scaffold; gbrain doesn't reliably extract
    # this. The user fills it in during /research-review unless --no-haiku
    # is set (Haiku-call path is a follow-up PR).
    failure_mode = (
        "TODO during review: when does this mechanism break? "
        "(adapter could not extract automatically)"
    )

    confidence = entity.confidence_hint or "low"

    return MechanismCardProposal(
        proposal_id=f"gbrain-{entity.slug}-{uuid.uuid4().hex[:8]}",
        proposed_at=when,
        status="pending",
        paper_title=entity.title,
        paper_source=f"gbrain:{entity.slug}",
        mechanism=mechanism,
        invariant=invariant,
        prediction=prediction,
        failure_mode=failure_mode,
        thesis_id=None,
        source_id=f"gbrain:{entity.slug}",
        source_excerpt=entity.body_excerpt[:1000],
        line_range=None,
        extraction_method="gbrain-mcp",
        extraction_model=None,
        confidence=confidence,
        reasoning=(
            f"Pulled from gbrain entity {entity.slug!r} via query {source_query!r}; "
            f"body_excerpt contained at least one causal verb match. "
            f"backlinks={entity.backlinks}, "
            f"typed_relationships={entity.typed_relationships}."
        ),
    )


def _pick_invariant(entity: GbrainEntity) -> str:
    causal_kinds = ("causes", "requires", "entails", "depends_on")
    for rel in entity.typed_relationships:
        for kind in causal_kinds:
            if rel.lower().startswith(kind):
                return f"{kind}: {rel}"[:400]
    # Fallback: title-cased subject — user edits in review.
    return f"Subject: {entity.title}"[:400]


def _pick_prediction(entity: GbrainEntity) -> str:
    match = _PREDICTION_PATTERN.search(entity.body_excerpt)
    if match:
        # Pull the sentence containing the match.
        start = entity.body_excerpt.rfind(".", 0, match.start()) + 1
        end = entity.body_excerpt.find(".", match.end())
        if end == -1:
            end = len(entity.body_excerpt)
        sentence = entity.body_excerpt[start:end].strip()
        return sentence[:400]
    return (
        "TODO during review: what falsifiable consequence follows from this mechanism?"
    )


# ---------------------------------------------------------------------------
# Fetch + ingest entry point.
# ---------------------------------------------------------------------------


def fetch_entities(
    spec: GbrainQuerySpec,
    *,
    call_gbrain: GbrainFetchCallable,
) -> List[GbrainEntity]:
    """Issue ``spec`` to gbrain via ``call_gbrain``, parse the response
    through ``GbrainEntity`` (Pydantic validation at the boundary).

    ``call_gbrain`` is a callable so the production wiring (real MCP
    client) and the test wiring (fixture loader) are interchangeable.
    The production wiring lives in a follow-up commit; this adapter
    ships with no live MCP dependency so v0 is fully testable without
    a running gbrain process.
    """
    raw = call_gbrain(spec)
    out: List[GbrainEntity] = []
    for i, row in enumerate(raw):
        try:
            out.append(GbrainEntity.model_validate(row))
        except Exception as e:
            logger.warning(
                "gbrain_adapter.fetch_entities: dropped row %d (validation error): %s",
                i, e,
            )
    return out


def fetch_from_export_file(
    export_path: Path,
) -> GbrainFetchCallable:
    """Helper: return a fetch callable that reads a JSON file produced
    by ``gbrain export``. Useful for offline ingestion AND for
    deterministic tests."""

    def _call(spec: GbrainQuerySpec) -> List[dict]:
        body = json.loads(export_path.read_text(encoding="utf-8"))
        if not isinstance(body, list):
            raise ValueError(f"gbrain export at {export_path} is not a JSON list")
        # v0: ignore spec filters; export files are pre-filtered. The query
        # spec is still recorded in the IngestionRun for audit.
        return body[: spec.limit]

    return _call


def ingest(
    *,
    spec: GbrainQuerySpec,
    call_gbrain: GbrainFetchCallable,
    home: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> IngestionRun:
    """End-to-end: fetch from gbrain → translate → write proposals.

    Returns an ``IngestionRun`` summarizing the invocation. The run is
    NOT auto-appended to ``ingestion_runs.jsonl`` — that's the CLI's
    job, so tests can inspect the return value without writing to the
    user's home dir.
    """
    started = now or datetime.now(timezone.utc)
    entities = fetch_entities(spec, call_gbrain=call_gbrain)

    proposals: List[MechanismCardProposal] = []
    for ent in entities:
        prop = translate(ent, source_query=spec.query, now=started)
        if prop is not None:
            proposals.append(prop)

    for prop in proposals:
        write_proposal(prop, home=home)

    finished = datetime.now(timezone.utc)
    return IngestionRun(
        run_id=uuid.uuid4().hex[:12],
        started_at=started,
        finished_at=finished,
        sources_scanned=len(entities),
        sources_skipped_unchanged=0,  # gbrain handles dedup upstream
        proposals_emitted=len(proposals),
        extraction_method="gbrain-mcp",
        cost_usd_estimate=0.0,  # v0 is zero-LLM in the adapter; Haiku path is follow-up
    )


def append_run_log(
    run: IngestionRun,
    *,
    home: Optional[Path] = None,
) -> Path:
    """Append one IngestionRun row to ``ingestion_runs.jsonl``.

    Separated from ``ingest`` so tests can call it explicitly and the
    CLI is the only path that mutates the user's home dir."""
    base = home or (Path.home() / ".neuro_os_research")
    base.mkdir(parents=True, exist_ok=True)
    log_path = base / "ingestion_runs.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(run.model_dump_json() + "\n")
    return log_path


__all__ = [
    "GbrainFetchCallable",
    "translate",
    "fetch_entities",
    "fetch_from_export_file",
    "ingest",
    "append_run_log",
]
