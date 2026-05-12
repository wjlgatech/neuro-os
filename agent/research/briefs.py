"""
Layer-3 briefs for the research vertical — turn a MechanismCluster into
a decision-ready document grounded in a user-supplied ProjectContext.

A cluster (Layer 2) names a shared mechanism + first principle +
anti-pattern across multiple papers. A brief (Layer 3) answers: given
THIS user's current project, current questions, and pending decisions,
what does this cluster imply they should DO?

The ProjectContext is generic — it knows nothing about the substrate's
verticals or any specific framework. It just round-trips:

* project_name        — short tag the user gives the work
* current_questions   — 1–5 specific questions the project is trying to answer
* collaborators       — optional named people the brief might address
* pending_decisions   — optional list of decisions waiting on this synthesis
* framework_name      — optional cross-ref to ~/.neuro_os_research/framework.json

The substrate refuses to hard-code domains. A founder reading agent-engineering
papers and an investor reading 10-Ks both use the same ProjectContext shape.

Storage: one file per brief at
``~/.neuro_os_research/briefs/<brief_id>.json`` AND a sibling
``<brief_id>.md`` for human reading.

Read-only over MechanismCards and synthesis runs; never mutates them.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from agent.research.synthesis import MechanismCluster

logger = logging.getLogger(__name__)


# Brief generator callable: takes (system_prompt, user_text) → one dict
# (NOT a list — briefs are single-shot per cluster).
LLMBriefCallable = Callable[[str, str], Optional[dict]]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProjectContext(BaseModel):
    """User-supplied context for the brief generator. Generic — no
    vertical-specific fields. The user authors this once per project
    and points ``research brief --context-file`` at it.
    """

    model_config = ConfigDict(frozen=True)

    project_name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=600)
    current_questions: Tuple[str, ...] = Field(min_length=1, max_length=10)
    collaborators: Tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    pending_decisions: Tuple[str, ...] = Field(default_factory=tuple, max_length=10)
    framework_name: Optional[str] = Field(default=None, max_length=80)


class QuestionForCollaborator(BaseModel):
    """A question the brief surfaces for the user to ask a specific
    collaborator (or the team) the next time they talk."""

    model_config = ConfigDict(frozen=True)

    collaborator_name: Optional[str] = Field(default=None, max_length=80)
    question: str = Field(min_length=1, max_length=400)
    why_this_question: Optional[str] = Field(default=None, max_length=400)


class DecisionBrief(BaseModel):
    """Layer-3 output — what the user should DO with the cluster's insight.

    Frozen: a brief is a record of a moment of synthesis; revisions are
    new briefs, not mutations.
    """

    model_config = ConfigDict(frozen=True)

    brief_id: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    cluster_id: str = Field(min_length=1, max_length=64)
    synthesis_run_id: str = Field(min_length=1, max_length=64)
    project_name: str = Field(min_length=1, max_length=120)
    method: Literal["llm-anthropic", "fallback-heuristic"]

    project_implications: Tuple[str, ...] = Field(default_factory=tuple, max_length=10)
    next_decisions: Tuple[str, ...] = Field(default_factory=tuple, max_length=10)
    next_experiments: Tuple[str, ...] = Field(default_factory=tuple, max_length=10)
    questions_for_collaborators: Tuple[QuestionForCollaborator, ...] = Field(
        default_factory=tuple, max_length=20,
    )
    framework_alignment_summary: Optional[str] = Field(default=None, max_length=600)


# ---------------------------------------------------------------------------
# Disk helpers
# ---------------------------------------------------------------------------


def _research_home(home: Optional[Path]) -> Path:
    return home or (Path.home() / ".neuro_os_research")


def briefs_dir(home: Optional[Path] = None) -> Path:
    return _research_home(home) / "briefs"


def _atomic_write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=path.suffix + ".tmp", dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def write_brief(brief: DecisionBrief, *, home: Optional[Path] = None) -> Tuple[Path, Path]:
    """Write the brief twice: a JSON file for machine reading and a
    markdown rendering for the human. Returns (json_path, md_path)."""
    json_target = briefs_dir(home) / f"{brief.brief_id}.json"
    md_target = briefs_dir(home) / f"{brief.brief_id}.md"
    _atomic_write(json_target, brief.model_dump_json(indent=2))
    _atomic_write(md_target, render_markdown(brief))
    return (json_target, md_target)


def list_briefs(
    *,
    home: Optional[Path] = None,
    limit: Optional[int] = None,
) -> List[DecisionBrief]:
    """Most-recent first by generated_at."""
    d = briefs_dir(home)
    if not d.exists():
        return []
    out: List[DecisionBrief] = []
    for p in d.glob("*.json"):
        try:
            out.append(DecisionBrief.model_validate_json(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    out.sort(key=lambda b: b.generated_at, reverse=True)
    return out[:limit] if limit else out


# ---------------------------------------------------------------------------
# Heuristic brief (no LLM)
# ---------------------------------------------------------------------------


def _heuristic_brief(
    *,
    cluster: MechanismCluster,
    context: ProjectContext,
    synthesis_run_id: str,
    now: datetime,
) -> DecisionBrief:
    """Templated brief — uses the cluster's existing fields + the
    project context to populate the brief without calling an LLM. Less
    rich than the LLM path, but proves the pipeline works offline."""

    implications: List[str] = []
    implications.append(
        f"Cluster '{cluster.label}' bundles {len(cluster.member_card_ids)} "
        f"mechanism card(s). Project '{context.project_name}' should "
        f"interrogate whether this shared mechanism applies to its "
        f"current questions."
    )
    if cluster.shared_first_principle:
        implications.append(
            f"Shared first principle: {cluster.shared_first_principle}"
        )
    if cluster.recurring_anti_pattern:
        implications.append(
            f"Anti-pattern to avoid: {cluster.recurring_anti_pattern}"
        )
    if cluster.false_consensus_flag:
        implications.append(
            f"False-consensus flag: {cluster.false_consensus_flag}"
        )

    next_decisions: List[str] = []
    for decision in context.pending_decisions:
        next_decisions.append(
            f"Re-evaluate '{decision}' against the cluster's shared mechanism."
        )
    if not next_decisions:
        next_decisions.append(
            "No pending decisions listed in context; consider what decision "
            "this cluster ought to clarify before scaling."
        )

    next_experiments: List[str] = []
    for q in context.current_questions[:3]:
        next_experiments.append(
            f"Design a cheap test that would falsify the cluster's mechanism "
            f"as applied to: \"{q}\""
        )

    questions: List[QuestionForCollaborator] = []
    for collab in context.collaborators[:5]:
        questions.append(QuestionForCollaborator(
            collaborator_name=collab,
            question=(
                f"What evidence would change your view of '{cluster.label}' "
                f"as applied to {context.project_name}?"
            ),
            why_this_question=(
                "Template question — designed to surface the collaborator's "
                "load-bearing assumption that the cluster's mechanism would "
                "either confirm or contradict."
            ),
        ))

    fw_summary: Optional[str] = None
    if cluster.framework_axes_touched:
        axes = ", ".join(cluster.framework_axes_touched)
        fw_summary = (
            f"Cluster touches framework axes: {axes}. "
            f"Consider where these axes are weakest in {context.project_name}."
        )

    return DecisionBrief(
        brief_id=f"brief-{uuid.uuid4().hex[:10]}",
        generated_at=now,
        cluster_id=cluster.cluster_id,
        synthesis_run_id=synthesis_run_id,
        project_name=context.project_name,
        method="fallback-heuristic",
        project_implications=tuple(implications),
        next_decisions=tuple(next_decisions),
        next_experiments=tuple(next_experiments),
        questions_for_collaborators=tuple(questions),
        framework_alignment_summary=fw_summary,
    )


# ---------------------------------------------------------------------------
# LLM brief
# ---------------------------------------------------------------------------


_LLM_BRIEF_SYSTEM_PROMPT = (
    "You write a decision-ready brief for one MechanismCluster, "
    "grounded in a specific ProjectContext. The brief answers: given "
    "the user's project, current questions, and pending decisions, "
    "what should they DO with this cluster's insight?\n\n"
    "Input: one MechanismCluster (label, mechanism_summary, "
    "shared_first_principle, recurring_anti_pattern, frontier_position, "
    "false_consensus_flag, framework_axes_touched) + one ProjectContext "
    "(project_name, current_questions, collaborators, pending_decisions, "
    "framework_name).\n\n"
    "Output: a JSON object with these keys:\n"
    "  - project_implications: list of 2-5 bullets, each ≤ 280 chars, "
    "naming what the cluster MEANS for this specific project (not "
    "generic platitudes — name a concrete implication).\n"
    "  - next_decisions: list of 1-5 bullets, each ≤ 280 chars, naming a "
    "decision the user should make BECAUSE of this cluster.\n"
    "  - next_experiments: list of 1-5 bullets, each ≤ 280 chars, naming "
    "a cheap test that would falsify the cluster's applicability to this "
    "project (NOT a generic experiment).\n"
    "  - questions_for_collaborators: list of 0-5 objects, each "
    "{collaborator_name (optional), question (≤ 400 chars), "
    "why_this_question (optional, ≤ 400 chars)}.\n"
    "  - framework_alignment_summary: optional string ≤ 600 chars, only "
    "if the cluster touches axes named in the user's framework.\n\n"
    "RULES: be specific to the project; refuse generic advice; if the "
    "cluster doesn't speak to the project's current questions, say so "
    "explicitly in project_implications rather than inventing connections."
)


def _build_llm_brief_user_message(
    cluster: MechanismCluster, context: ProjectContext,
) -> str:
    payload = {
        "cluster": {
            "label": cluster.label,
            "mechanism_summary": cluster.mechanism_summary,
            "shared_first_principle": cluster.shared_first_principle,
            "recurring_anti_pattern": cluster.recurring_anti_pattern,
            "frontier_position": cluster.frontier_position,
            "false_consensus_flag": cluster.false_consensus_flag,
            "framework_axes_touched": list(cluster.framework_axes_touched),
            "member_card_count": len(cluster.member_card_ids),
        },
        "project_context": {
            "project_name": context.project_name,
            "description": context.description,
            "current_questions": list(context.current_questions),
            "collaborators": list(context.collaborators),
            "pending_decisions": list(context.pending_decisions),
            "framework_name": context.framework_name,
        },
    }
    return json.dumps(payload, indent=2, default=str)


def _opt_str(raw: object, max_len: int) -> Optional[str]:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    return s[:max_len] if s else None


def _parse_questions(raw: object) -> List[QuestionForCollaborator]:
    if not isinstance(raw, list):
        return []
    out: List[QuestionForCollaborator] = []
    for item in raw[:20]:
        if not isinstance(item, dict):
            continue
        q = item.get("question")
        if not isinstance(q, str) or not q.strip():
            continue
        try:
            out.append(QuestionForCollaborator(
                collaborator_name=_opt_str(item.get("collaborator_name"), 80),
                question=q.strip()[:400],
                why_this_question=_opt_str(item.get("why_this_question"), 400),
            ))
        except Exception:
            continue
    return out


def _llm_brief(
    *,
    cluster: MechanismCluster,
    context: ProjectContext,
    synthesis_run_id: str,
    llm_fn: LLMBriefCallable,
    now: datetime,
) -> Optional[DecisionBrief]:
    user_msg = _build_llm_brief_user_message(cluster, context)
    try:
        raw = llm_fn(_LLM_BRIEF_SYSTEM_PROMPT, user_msg)
    except Exception as e:
        logger.warning("briefs._llm_brief: llm_fn failed (%s)", e)
        return None
    if not isinstance(raw, dict):
        return None

    def _coerce_bullets(key: str, max_len: int) -> Tuple[str, ...]:
        items = raw.get(key)
        if not isinstance(items, list):
            return ()
        bullets: List[str] = []
        for it in items[:10]:
            if not isinstance(it, str):
                continue
            s = it.strip()
            if s:
                bullets.append(s[:max_len])
        return tuple(bullets)

    try:
        return DecisionBrief(
            brief_id=f"brief-{uuid.uuid4().hex[:10]}",
            generated_at=now,
            cluster_id=cluster.cluster_id,
            synthesis_run_id=synthesis_run_id,
            project_name=context.project_name,
            method="llm-anthropic",
            project_implications=_coerce_bullets("project_implications", 280),
            next_decisions=_coerce_bullets("next_decisions", 280),
            next_experiments=_coerce_bullets("next_experiments", 280),
            questions_for_collaborators=tuple(
                _parse_questions(raw.get("questions_for_collaborators"))
            ),
            framework_alignment_summary=_opt_str(
                raw.get("framework_alignment_summary"), 600,
            ),
        )
    except Exception as e:
        logger.warning("briefs._llm_brief: validation failed (%s)", e)
        return None


# ---------------------------------------------------------------------------
# Public entry point + rendering
# ---------------------------------------------------------------------------


def generate_brief(
    *,
    cluster: MechanismCluster,
    context: ProjectContext,
    synthesis_run_id: str,
    llm_fn: Optional[LLMBriefCallable] = None,
    now: Optional[datetime] = None,
) -> DecisionBrief:
    """Generate one brief. LLM path with heuristic fallback on any
    failure — the user always gets a brief, the method field tells them
    which path produced it."""
    when = now or datetime.now(timezone.utc)
    if llm_fn is not None:
        brief = _llm_brief(
            cluster=cluster,
            context=context,
            synthesis_run_id=synthesis_run_id,
            llm_fn=llm_fn,
            now=when,
        )
        if brief is not None:
            return brief
    return _heuristic_brief(
        cluster=cluster,
        context=context,
        synthesis_run_id=synthesis_run_id,
        now=when,
    )


def render_markdown(
    brief: DecisionBrief, *, cluster: Optional[MechanismCluster] = None,
) -> str:
    """Render the brief as a markdown document for the user to read or
    paste into their notes. The cluster (optional) lets the renderer
    surface the cluster header up top."""
    lines: List[str] = []
    lines.append(f"# Brief — {brief.project_name}")
    when = brief.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    lines.append(f"_Generated {when}; method `{brief.method}`._")
    lines.append("")
    if cluster is not None:
        lines.append(f"## Cluster: {cluster.label}")
        lines.append("")
        lines.append(f"**Mechanism summary.** {cluster.mechanism_summary}")
        if cluster.shared_first_principle:
            lines.append("")
            lines.append(f"**Shared first principle.** {cluster.shared_first_principle}")
        if cluster.recurring_anti_pattern:
            lines.append("")
            lines.append(f"**Anti-pattern.** {cluster.recurring_anti_pattern}")
        lines.append("")
    if brief.project_implications:
        lines.append("## What this means for the project")
        for b in brief.project_implications:
            lines.append(f"- {b}")
        lines.append("")
    if brief.next_decisions:
        lines.append("## Next decisions")
        for b in brief.next_decisions:
            lines.append(f"- {b}")
        lines.append("")
    if brief.next_experiments:
        lines.append("## Next experiments")
        for b in brief.next_experiments:
            lines.append(f"- {b}")
        lines.append("")
    if brief.questions_for_collaborators:
        lines.append("## Questions for collaborators")
        for q in brief.questions_for_collaborators:
            who = q.collaborator_name or "(unspecified)"
            lines.append(f"- **{who}** — {q.question}")
            if q.why_this_question:
                lines.append(f"  _why:_ {q.why_this_question}")
        lines.append("")
    if brief.framework_alignment_summary:
        lines.append("## Framework alignment")
        lines.append(brief.framework_alignment_summary)
        lines.append("")
    return "\n".join(lines)


__all__ = [
    "ProjectContext",
    "QuestionForCollaborator",
    "DecisionBrief",
    "LLMBriefCallable",
    "briefs_dir",
    "write_brief",
    "list_briefs",
    "generate_brief",
    "render_markdown",
]
