"""
Plan A — native LLM extractor for the research vertical.

Reads ``.txt`` / ``.md`` / ``.pdf`` source files, produces
``MechanismCardProposal`` rows for the same on-disk queue Lane 1
(gbrain adapter) feeds. The two extractors share Plan A/B downstream
infrastructure (queue, review surface, accept pipeline); only the
input → MechanismCardProposal step differs.

Pipeline (4 stages):

1. ``_extract_text(path)`` — dispatch by file extension. Decode .txt/.md
   as UTF-8; extract .pdf via pypdf (page-by-page text). Raises
   ``UnsupportedSourceFormat`` for everything else.
2. ``load_sources(source_dir)`` — walk the directory, build typed
   ``RawSource`` records, dedup against existing pending proposals via
   sha256.
3. ``extract_mechanisms(source, *, llm_fn)`` — one source → 0..K
   ``MechanismCardProposal`` candidates. ``llm_fn`` is injectable so
   tests pin every code path; production wires it to Anthropic Haiku
   via ``agent.llm_extractors.make_anthropic_extractor``. A regex
   heuristic fallback fires when no API key is set (emits low-confidence
   proposals so the reviewer knows the heuristic ran, not the LLM).
4. ``ingest(source_dir, *, llm_fn, home)`` — glue: load → extract →
   ``write_proposal`` → return ``IngestionRun``.

Cost discipline: ``extract_mechanisms`` runs ONE Haiku call per source,
not per chunk. For long sources we trim to ``MAX_CHARS_PER_SOURCE``
(50_000) — captures introduction + early body of typical papers /
book chapters, which is where mechanism statements concentrate.
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from agent.research.framework import EMPTY_FRAMEWORK, Framework
from agent.research.ontology import (
    FrameworkAxisNote,
    IngestionRun,
    MechanismCardProposal,
    RawSource,
)
from agent.research.proposals import list_proposals, write_proposal


logger = logging.getLogger(__name__)


SUPPORTED_EXTS = {".txt", ".md", ".pdf"}
MAX_CHARS_PER_SOURCE = 50_000


# An LLM callable for tests/production. Takes (system_prompt, user_text)
# and returns a list of dicts that will be parsed via
# MechanismCardProposal.model_validate. Returning dicts (not models)
# means malformed LLM output is rejected at the boundary, not silently
# dropped.
LLMCallable = Callable[[str, str], List[dict]]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnsupportedSourceFormat(ValueError):
    """Raised when a file extension isn't in SUPPORTED_EXTS."""


# ---------------------------------------------------------------------------
# Stage 1: text extraction
# ---------------------------------------------------------------------------


def _extract_text(path: Path) -> str:
    """Return the text content of a source file. Dispatches by extension."""
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise UnsupportedSourceFormat(
            f"unsupported source format: {ext!r} "
            f"(supported: {sorted(SUPPORTED_EXTS)})"
        )
    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")

    # .pdf: use pypdf for pure-Python extraction.
    from pypdf import PdfReader  # imported lazily — only when a PDF is seen

    reader = PdfReader(str(path))
    pages: List[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as e:
            # Image-only / corrupted pages produce empty text — that's a
            # skip, not a hard failure. Log and continue.
            logger.info(
                "ingest._extract_text: skipped page in %s (extract failed: %s)",
                path.name, e,
            )
    return "\n\n".join(p for p in pages if p.strip())


# ---------------------------------------------------------------------------
# Stage 2: load_sources (walk + dedup)
# ---------------------------------------------------------------------------


_FRONT_MATTER_PATTERN = re.compile(
    r"^---\s*\n(?P<body>.*?)\n---\s*\n",
    re.DOTALL,
)


def _parse_front_matter(text: str) -> tuple[Optional[dict], str]:
    """If text starts with --- ... ---, parse the YAML-ish key:value
    block (lightweight; doesn't require pyyaml) and return (meta, body).
    Otherwise return (None, text).
    """
    m = _FRONT_MATTER_PATTERN.match(text)
    if not m:
        return (None, text)
    block = m.group("body")
    body = text[m.end():]
    meta: dict = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return (meta, body)


def _filename_to_default_meta(path: Path) -> dict:
    """Extract a sensible default title/author from the filename when no
    front-matter is present. Format expected (loose): ``<author>__<slug>``
    or just ``<slug>``."""
    stem = path.stem
    if "__" in stem:
        author, slug = stem.split("__", 1)
        title = slug.replace("-", " ").replace("_", " ").strip().title()
        return {"title": title, "author": author.strip().title()}
    title = stem.replace("-", " ").replace("_", " ").strip().title()
    return {"title": title, "author": "unknown"}


def _existing_source_ids(home: Optional[Path]) -> set[str]:
    """Read the pending proposal queue and return the set of source_ids
    we've already ingested. Used for sha256-based dedup at load time."""
    out: set[str] = set()
    for status in ("pending", "accepted", "rejected"):
        for prop in list_proposals(home=home, status=status):
            out.add(prop.source_id)
    return out


def load_sources(
    source_dir: Path,
    *,
    home: Optional[Path] = None,
) -> tuple[List[RawSource], int]:
    """Walk ``source_dir``, build ``RawSource`` for each supported file,
    skip files whose sha256 already appears in any proposal status dir.

    Returns ``(sources, skipped_unchanged_count)``. Files that fail to
    read (e.g. PDF when ``pypdf`` is not installed) are tracked on the
    module attribute ``last_read_failures`` so callers can surface them
    to users instead of silently dropping them.
    """
    if not source_dir.exists():
        raise FileNotFoundError(f"source dir not found: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"not a directory: {source_dir}")

    existing = _existing_source_ids(home)
    sources: List[RawSource] = []
    skipped = 0
    read_failures: List[tuple[str, str]] = []

    for path in sorted(source_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        try:
            text = _extract_text(path)
        except UnsupportedSourceFormat:
            continue
        except Exception as e:
            logger.warning(
                "ingest.load_sources: failed to read %s (%s); skipping", path, e,
            )
            read_failures.append((path.name, str(e)))
            continue

        meta_yaml, body = _parse_front_matter(text)
        defaults = _filename_to_default_meta(path)
        meta = {**defaults, **(meta_yaml or {})}

        sha = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()
        source_id = f"local:{path.name}:{sha[:12]}"
        if source_id in existing:
            skipped += 1
            continue

        sources.append(RawSource(
            source_id=source_id,
            path=path.resolve(),
            title=meta.get("title", "Untitled")[:400],
            author=meta.get("author", "unknown")[:200],
            publish_date=meta.get("publish_date"),
            source_url=meta.get("source_url"),
            topic_tags=[
                t.strip() for t in meta.get("topic_tags", "").split(",")
                if t.strip()
            ] if meta.get("topic_tags") else [],
            word_count=len(body.split()),
            sha256=sha,
        ))
    # Expose read failures to the caller (HTTP handler reads this).
    # Module-level attribute so we don't change the signature.
    load_sources.last_read_failures = read_failures  # type: ignore[attr-defined]
    return (sources, skipped)


# ---------------------------------------------------------------------------
# Stage 3: extract_mechanisms (LLM or heuristic)
# ---------------------------------------------------------------------------


# System prompt for the LLM. Cached / static so prompt-caching can apply
# in production. The user message is the source body (trimmed) plus an
# optional framework hint built per-call by _build_framework_directive.
_SYSTEM_PROMPT = (
    "You extract MechanismCard proposals from one source document. A "
    "MechanismCard is a structured claim with FOUR required fields: "
    "(1) `mechanism` — the causal story (≤ 500 chars); what generates "
    "the observed behavior. "
    "(2) `invariant` — the load-bearing relationship that doesn't "
    "change with surface conditions (≤ 200 chars). "
    "(3) `prediction` — a falsifiable forecast that follows from the "
    "mechanism (≤ 200 chars). "
    "(4) `failure_mode` — the specific condition under which the "
    "mechanism breaks (≤ 200 chars). "
    "RULES: extract 0-5 candidates per source, quality over count; "
    "every candidate MUST cite a `source_excerpt` of ≤ 1000 chars from "
    "the input; if a passage is descriptive but doesn't name a "
    "mechanism, SKIP it (description is not a mechanism); if a passage "
    "names a mechanism but no falsifiable prediction follows, mark "
    "`confidence: low`.\n\n"
    "OPTIONAL deeper fields (leave null when the text doesn't support them): "
    "`first_principle` (≤ 400 chars) — the most general truth the mechanism "
    "rests on, often unstated in the paper, transferable BEYOND the paper's "
    "domain; `anti_pattern` (≤ 400 chars) — the way this mechanism is "
    "commonly misunderstood or misapplied; `transferability_test` (≤ 400 "
    "chars) — one concrete domain (in or out of the paper's field) where "
    "this mechanism also applies (if you can't name one, leave null — the "
    "mechanism may be a local optimization not a principle); `verdict` "
    "(one of 'foundational' | 'useful' | 'misleading' | 'skip') — your "
    "judgment of the paper's value; `one_sentence_compression` (≤ 280 "
    "chars) — tweet-length distillation; `framework_alignment` — a list "
    "of {axis_name, note} pairs ONLY for axes named in the user-supplied "
    "framework (preceding the source text). If no framework is supplied, "
    "omit framework_alignment.\n\n"
    "Respond as a JSON array of objects with keys: mechanism, invariant, "
    "prediction, failure_mode, source_excerpt, confidence ('low' | "
    "'medium' | 'high'), reasoning, and optionally: first_principle, "
    "anti_pattern, transferability_test, verdict, one_sentence_compression, "
    "framework_alignment."
)


def _build_framework_directive(framework: Framework) -> str:
    """Format the user's framework axes as a short directive prepended to
    the source body. Empty framework → empty string (no directive)."""
    if not framework.axes:
        return ""
    lines = [
        "USER FRAMEWORK — when extracting `framework_alignment`, consider "
        "ONLY these axes (skip ones the text doesn't support):"
    ]
    for axis in framework.axes:
        desc = f" — {axis.description}" if axis.description else ""
        lines.append(f"  - {axis.name}{desc}")
    lines.append("")
    return "\n".join(lines)


# Heuristic-fallback regex: finds sentences that contain a causal verb
# AND a falsifiable shape. Same vocabulary as Lane 1's translate().
_HEURISTIC_VERBS = re.compile(
    r"\b(cause|causes|because|drives?|forces?|produces?|results? in|"
    r"leads? to|implies|requires?|generates?|breaks? when|fails? when)\b",
    re.IGNORECASE,
)
_HEURISTIC_PREDICTION = re.compile(
    r"\b(when|if)\b[^.]{5,}\b(then|will|should|expect|predict)\b",
    re.IGNORECASE,
)


def _heuristic_extract(body: str) -> List[dict]:
    """Find sentences that contain BOTH a causal verb and a prediction
    pattern. Emits low-confidence candidates so the reviewer knows the
    heuristic ran, not the LLM."""
    sentences = re.split(r"(?<=[.!?])\s+", body)
    out: List[dict] = []
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 30:
            continue
        if not _HEURISTIC_VERBS.search(sent):
            continue
        if not _HEURISTIC_PREDICTION.search(sent):
            continue
        out.append({
            "mechanism": sent[:500],
            "invariant": "Heuristic match — user fills at /research-review.",
            "prediction": sent[:200],
            "failure_mode": "Heuristic match — user fills at /research-review.",
            "source_excerpt": sent[:1000],
            "confidence": "low",
            "reasoning": (
                "Heuristic: sentence contains both a causal verb and a "
                "falsifiable shape. No LLM was called. Edit at review."
            ),
        })
        if len(out) >= 5:
            break
    return out


_VALID_VERDICTS = {"foundational", "useful", "misleading", "skip"}


def _parse_framework_alignment(raw: object) -> List[FrameworkAxisNote]:
    """LLM may return framework_alignment as a list of dicts; coerce
    each into a FrameworkAxisNote, drop malformed entries silently."""
    if not isinstance(raw, list):
        return []
    out: List[FrameworkAxisNote] = []
    for item in raw[:10]:  # max_length on the field is 10
        if not isinstance(item, dict):
            continue
        axis = item.get("axis_name") or item.get("axis")
        note = item.get("note")
        if not isinstance(axis, str) or not isinstance(note, str):
            continue
        try:
            out.append(FrameworkAxisNote(axis_name=axis[:80], note=note[:400]))
        except Exception:
            continue
    return out


def _coerce_optional_str(raw: object, *, max_len: int) -> Optional[str]:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    return s[:max_len] if s else None


def _coerce_verdict(raw: object) -> Optional[str]:
    if isinstance(raw, str) and raw in _VALID_VERDICTS:
        return raw
    return None


def extract_mechanisms(
    source: RawSource,
    *,
    llm_fn: Optional[LLMCallable] = None,
    now: Optional[datetime] = None,
    framework: Optional[Framework] = None,
) -> List[MechanismCardProposal]:
    """One source → 0..K MechanismCardProposal candidates.

    If ``llm_fn`` is None, falls back to ``_heuristic_extract``.
    Otherwise calls the LLM, validates each row through
    ``MechanismCardProposal.model_validate`` (Pydantic at the boundary —
    malformed LLM output is dropped with a warning, not silently kept).

    ``framework`` (optional) is the user's framework from
    ``agent.research.framework.load_framework``. When supplied with
    axes, a short axes directive is prepended to the user message so
    the LLM can populate ``framework_alignment`` per proposal.
    """
    when = now or datetime.now(timezone.utc)
    fw = framework or EMPTY_FRAMEWORK
    body = source.path.read_text(encoding="utf-8", errors="replace") \
        if source.path.suffix.lower() in (".txt", ".md") \
        else _extract_text(source.path)
    body_trimmed = body[:MAX_CHARS_PER_SOURCE]
    user_message = _build_framework_directive(fw) + body_trimmed

    if llm_fn is None:
        raw_rows = _heuristic_extract(body_trimmed)
        method = "fallback-heuristic"
        model = None
    else:
        try:
            raw_rows = llm_fn(_SYSTEM_PROMPT, user_message)
        except Exception as e:
            logger.warning(
                "ingest.extract_mechanisms: llm_fn failed for %s (%s); "
                "falling back to heuristic", source.source_id, e,
            )
            # Surface the failure so callers can show it to users
            # (the HTTP handler reads this).
            fails = getattr(extract_mechanisms, "last_llm_errors", [])
            fails.append((source.source_id, str(e)))
            extract_mechanisms.last_llm_errors = fails  # type: ignore[attr-defined]
            raw_rows = _heuristic_extract(body_trimmed)
            method = "fallback-heuristic"
            model = None
        else:
            method = "llm-anthropic"
            model = "claude-haiku-4-5"

    proposals: List[MechanismCardProposal] = []
    for i, row in enumerate(raw_rows):
        try:
            proposal = MechanismCardProposal(
                proposal_id=f"local-{source.source_id.split(':')[-1]}-{uuid.uuid4().hex[:8]}",
                proposed_at=when,
                status="pending",
                paper_title=source.title,
                paper_source=source.source_url or f"local:{source.path.name}",
                mechanism=str(row.get("mechanism", ""))[:500] or "Mechanism unspecified",
                invariant=str(row.get("invariant", ""))[:400] or "Invariant unspecified",
                prediction=str(row.get("prediction", ""))[:400] or "Prediction unspecified",
                failure_mode=str(row.get("failure_mode", ""))[:400] or "Failure mode unspecified",
                thesis_id=None,
                source_id=source.source_id,
                source_excerpt=str(row.get("source_excerpt", ""))[:1000] or body_trimmed[:1000],
                line_range=None,
                extraction_method=method,
                extraction_model=model,
                confidence=row.get("confidence", "low") if row.get("confidence") in ("low", "medium", "high") else "low",
                reasoning=str(row.get("reasoning", ""))[:1000] or "No reasoning supplied.",
                first_principle=_coerce_optional_str(row.get("first_principle"), max_len=400),
                anti_pattern=_coerce_optional_str(row.get("anti_pattern"), max_len=400),
                transferability_test=_coerce_optional_str(row.get("transferability_test"), max_len=400),
                verdict=_coerce_verdict(row.get("verdict")),
                one_sentence_compression=_coerce_optional_str(row.get("one_sentence_compression"), max_len=280),
                framework_alignment=_parse_framework_alignment(row.get("framework_alignment")),
                source_tier=source.tier,
            )
            proposals.append(proposal)
        except Exception as e:
            logger.warning(
                "ingest.extract_mechanisms: dropped row %d from %s "
                "(validation error: %s)",
                i, source.source_id, e,
            )
    return proposals


# ---------------------------------------------------------------------------
# Stage 4: ingest (end-to-end glue)
# ---------------------------------------------------------------------------


def ingest(
    *,
    source_dir: Path,
    llm_fn: Optional[LLMCallable] = None,
    home: Optional[Path] = None,
    now: Optional[datetime] = None,
    framework: Optional[Framework] = None,
) -> IngestionRun:
    """End-to-end: load sources → extract per source → write proposals.

    Returns an ``IngestionRun`` summarizing the invocation. Does NOT
    auto-append to ``ingestion_runs.jsonl`` — the CLI does that so tests
    can inspect the return value without writing to ``home``.

    ``framework`` defaults to ``load_framework(home)`` so a user-edited
    ``~/.neuro_os_research/framework.json`` flows in automatically; pass
    an explicit ``Framework`` to override (tests do this).
    """
    started = now or datetime.now(timezone.utc)
    # Reset per-run diagnostic attrs so callers see only THIS run's
    # failures, not a stale accumulation.
    load_sources.last_read_failures = []  # type: ignore[attr-defined]
    extract_mechanisms.last_llm_errors = []  # type: ignore[attr-defined]
    sources, skipped = load_sources(source_dir, home=home)

    if framework is None:
        from agent.research.framework import load_framework
        framework = load_framework(home=home)

    all_proposals: List[MechanismCardProposal] = []
    for src in sources:
        all_proposals.extend(extract_mechanisms(
            src, llm_fn=llm_fn, now=started, framework=framework,
        ))

    # Gap 2 — proposal-level dedup. Compute the set of mechanism hashes
    # already on disk (pending + accepted) ONCE, then skip any new
    # proposal whose normalized (mechanism, invariant) hash collides.
    # Also dedup against earlier proposals within this same run.
    from agent.research.proposals import (
        existing_mechanism_hashes,
        proposal_hash,
    )
    seen_hashes = existing_mechanism_hashes(home=home)
    proposals_written: List[MechanismCardProposal] = []
    skipped_duplicate = 0
    for prop in all_proposals:
        h = proposal_hash(prop)
        if h in seen_hashes:
            skipped_duplicate += 1
            continue
        seen_hashes.add(h)
        write_proposal(prop, home=home)
        proposals_written.append(prop)

    finished = datetime.now(timezone.utc)
    used_method = (
        "llm-anthropic" if llm_fn is not None else "fallback-heuristic"
    )
    return IngestionRun(
        run_id=uuid.uuid4().hex[:12],
        started_at=started,
        finished_at=finished,
        sources_scanned=len(sources),
        sources_skipped_unchanged=skipped,
        proposals_emitted=len(proposals_written),
        proposals_skipped_duplicate=skipped_duplicate,
        extraction_method=used_method,
        cost_usd_estimate=0.0,  # llm_fn callers wire real cost; v0 default 0
    )


__all__ = [
    "SUPPORTED_EXTS",
    "MAX_CHARS_PER_SOURCE",
    "LLMCallable",
    "UnsupportedSourceFormat",
    "extract_mechanisms",
    "ingest",
    "load_sources",
]
