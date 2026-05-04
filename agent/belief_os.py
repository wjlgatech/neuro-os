"""
Belief OS — public consumption API for the ``personal_epistemic_v1`` domain.

Belief OS is a **primitive**, not a product. Other tools in the wjlgatech
ecosystem are the consumers:

* **company-os Founder OS** — call ``check_decision()`` before promoting
  an intent to a PLAN.md. Surface the reasoning-pattern flag to the
  approval gate.
* **money-os** — call ``ingest()`` when a user captures an investment
  thesis. Surface contradictions with prior theses before allowing
  position-sizing.
* **research-os** (hypothetical) — call ``ingest(source_type="research_paper")``
  when a user pastes a key claim from a paper. Build a per-user belief
  graph that survives across sessions.

This module wraps the underlying ``personal_epistemic_v1`` machinery
(extractor + L1 loop + LLM with keyword fallback) behind a small, typed
surface so consumers never have to know about ontologies, golden cases,
or priority rules.

Everything else in the wjlgatech ecosystem can talk to Belief OS through
this file alone.

Three entry points:

* ``BeliefOS`` — class. Holds per-consumer state (which ontology file to
  persist to, whether to use the LLM, optional API key). Build once per
  user / product / context, reuse for the lifetime of that scope.
* ``classify_belief(text)`` — stateless one-off function. No
  persistence. For products that just need the reasoning pattern of a
  single string and don't care about a belief graph.
* ``check_decision_text(text)`` — stateless one-off function. Same
  classification but framed as "should this decision be flagged for
  human review?" — the Founder-OS pattern.

Failure-mode primitives (``survivorship_bias``, ``falsifiability``) are
flagged for review by default. Sound-reasoning primitives
(``bayesian_updating``, ``base_rate_reasoning``, ``expected_value``,
``second_order_thinking``) are NOT flagged — invoking them is usually a
good sign, not a bug. Consumers can override the flagged set per-call.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

try:
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - pydantic is a transitive dep
    raise ImportError(
        "pydantic is required for the Belief OS public API. "
        "It ships with the anthropic SDK; install it with: pip install pydantic"
    ) from exc

import agent.personal_epistemic_domain  # noqa: F401 — registers the domain
from agent.api import ingest_documents
from agent.ingestion_pipeline import classify_evidence_strength
from agent.personal_epistemic_domain import (
    PERSONAL_EPISTEMIC_GOLDEN_CASES,
    PERSONAL_EPISTEMIC_PRIMITIVES,
    PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH,
    disable_llm,
    enable_llm,
    personal_epistemic_extractor,
)


# ---------------------------------------------------------------------------
# Public defaults
# ---------------------------------------------------------------------------

# These primitives describe a *failure mode* of reasoning (a bug to
# watch for). When an intent or claim invokes one of these, downstream
# products should flag it for human review.
FAILURE_MODE_PRIMITIVES: Set[str] = {
    "survivorship_bias",
    "falsifiability",  # i.e., the claim is unfalsifiable
}

# These primitives describe a *sound-reasoning pattern*. Invoking them
# is usually a good sign — the speaker is reasoning carefully — and
# should not be flagged.
SOUND_REASONING_PRIMITIVES: Set[str] = {
    "bayesian_updating",
    "base_rate_reasoning",
    "expected_value",
    "second_order_thinking",
}

# All known labels (the ontology + 'unknown'). Locked here so consumers
# can build dropdowns / filters / dashboards without reading from
# private internals.
KNOWN_PRIMITIVES: List[str] = sorted(PERSONAL_EPISTEMIC_PRIMITIVES.keys()) + ["unknown"]


# ---------------------------------------------------------------------------
# Typed result models
# ---------------------------------------------------------------------------


class ClassificationResult(BaseModel):
    """The pattern that a single claim invokes, plus how we got there."""

    mechanism: str = Field(
        description=(
            "One of the six reasoning primitives or 'unknown'. "
            "See ``KNOWN_PRIMITIVES`` for the full set."
        )
    )
    decision: str = Field(
        description="ACCEPT (well-formed claim with a known primitive), "
        "REFINE (partial), or REJECT (unknown / off-topic)."
    )
    true_score: float = Field(
        description="Composite TRUE rubric score (0.0–1.0). Higher is "
        "more transferable, repeatable, usable, experimentable."
    )
    method: str = Field(
        description="How the mechanism was extracted: 'offline-keyword' "
        "(deterministic), 'llm-anthropic' (Claude classifier), or "
        "'llm-error' (LLM call failed; result was the keyword fallback)."
    )
    confidence: Optional[str] = Field(
        default=None,
        description="LLM-only: 'low' | 'medium' | 'high'. None when the "
        "keyword path produced the result.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="LLM-only: one-sentence justification for the "
        "classification. None when the keyword path produced the result.",
    )
    evidence_strength: str = Field(
        description="Citation strength of the input text (DOI / arXiv / "
        "year+author markers): 'strong' | 'moderate' | 'weak'."
    )


class DecisionCheckResult(BaseModel):
    """Recommendation for a downstream gate (e.g. Founder-OS approval)."""

    classification: ClassificationResult = Field(
        description="The underlying classification of the decision text."
    )
    flag_for_review: bool = Field(
        description="True iff the classified primitive is in the "
        "failure-mode set. The downstream product decides what to do "
        "with the flag (block, warn, ask the user)."
    )
    flag_reason: Optional[str] = Field(
        default=None,
        description="Human-readable reason the flag fired, or None if "
        "no flag.",
    )


class IngestResult(BaseModel):
    """Outcome of adding a claim to a persistent belief graph."""

    classification: ClassificationResult
    merge_status: str = Field(
        description="One of: 'no_proposal' (consistent with priors, "
        "nothing to merge), 'merged' (refinement passed evaluation + "
        "golden gate), 'reverted_on_regression' (refinement would have "
        "broken golden cases), 'accepted_no_merge' (eval passed but "
        "merge was disabled), 'evaluated' (proposal scored but did not "
        "ACCEPT)."
    )
    primitive_updated: Optional[str] = Field(
        default=None,
        description="If a merge was applied, which primitive's "
        "definition was overwritten.",
    )
    contradicts_prior: bool = Field(
        description="True iff the loop detected an ontology contradiction "
        "that triggered a refinement proposal — even if the merge was "
        "later reverted by the golden gate."
    )
    ontology_path: Optional[str] = Field(
        default=None,
        description="Path the updated ontology was persisted to, or None "
        "if no path was configured (in-memory only).",
    )


class BeliefRecord(BaseModel):
    """A single primitive's current state in a user's belief graph."""

    primitive: str
    definition: str
    aliases: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    relations: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# BeliefOS — class for stateful per-consumer use
# ---------------------------------------------------------------------------


class BeliefOS:
    """Public surface for products that want to use Belief OS as a primitive.

    A ``BeliefOS`` instance is parameterized by:

    * ``ontology_path`` — where the user's persistent belief graph lives.
      ``None`` means in-memory only (every call starts from the canonical
      ontology). For real consumer products, set this to a per-user file
      so beliefs accumulate across sessions.
    * ``use_llm`` — whether to route classification through Claude Haiku.
      Off by default: deterministic, no API key needed. Turn on for
      slang and natural-language input.
    * ``api_key`` / ``llm_model`` — passed through to the Anthropic
      client when ``use_llm=True``.
    * ``failure_mode_primitives`` — override the default set of
      primitives that trigger ``flag_for_review=True``.

    Single-instance per user-context. Cheap to construct; safe to keep
    around.
    """

    def __init__(
        self,
        *,
        ontology_path: Optional[Union[str, Path]] = None,
        use_llm: bool = False,
        llm_model: str = "claude-haiku-4-5",
        api_key: Optional[str] = None,
        failure_mode_primitives: Optional[Set[str]] = None,
    ) -> None:
        self.ontology_path = Path(ontology_path) if ontology_path else None
        self.use_llm = use_llm
        self.llm_model = llm_model
        self.api_key = api_key
        self.failure_mode_primitives = (
            failure_mode_primitives
            if failure_mode_primitives is not None
            else FAILURE_MODE_PRIMITIVES
        )

    # --- internal helpers ------------------------------------------------

    def _ensure_llm_state(self) -> None:
        """Toggle the global LLM flag on/off based on ``self.use_llm``.

        The underlying domain holds a process-wide ``_llm_fn``; each
        public method flips it before/after the call so multiple
        ``BeliefOS`` instances with different ``use_llm`` settings
        don't step on each other.
        """
        if self.use_llm:
            try:
                enable_llm(model=self.llm_model, api_key=self.api_key)
            except Exception:
                # Surface as graceful fallback — the extractor will
                # report 'llm-error' on the failed call.
                disable_llm()
        else:
            disable_llm()

    def _result_to_classification(self, result: Dict[str, Any], text: str) -> ClassificationResult:
        knowledge = result.get("knowledge", {}) or {}
        validation = result.get("true_validation", {}) or {}
        scores = validation.get("scores", {}) or {}
        evidence = knowledge.get("extraction_evidence", {}) or {}
        return ClassificationResult(
            mechanism=str(knowledge.get("mechanism", "unknown")),
            decision=str(result.get("decision", "REJECT")),
            true_score=float(scores.get("TRUE", 0.0)),
            method=str(evidence.get("method", "offline-keyword")),
            confidence=evidence.get("confidence"),
            reasoning=evidence.get("reasoning"),
            evidence_strength=classify_evidence_strength(text or ""),
        )

    def _load_ontology(self) -> Dict[str, Any]:
        """Read the persisted ontology if it exists, else fall back to canonical."""
        if self.ontology_path and self.ontology_path.exists():
            with self.ontology_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "primitives": {
                k: dict(v) for k, v in PERSONAL_EPISTEMIC_PRIMITIVES.items()
            },
        }

    # --- public API ------------------------------------------------------

    def classify(self, text: str) -> ClassificationResult:
        """Stateless single-shot classification.

        Does not modify the persisted belief graph. Use this when you
        want to know what pattern a claim invokes without committing to
        anything.
        """
        self._ensure_llm_state()
        try:
            raw = personal_epistemic_extractor(text)
        finally:
            # Leave the global flag as the caller set it. Don't toggle off
            # here — other concurrent BeliefOS instances may want it on.
            pass
        return self._result_to_classification(raw, text)

    def check_decision(
        self,
        decision_text: str,
        *,
        flag_unknown: bool = False,
    ) -> DecisionCheckResult:
        """Classify a candidate decision and recommend whether to flag it.

        Returns ``flag_for_review=True`` when the classified primitive
        is in ``self.failure_mode_primitives`` (default:
        ``survivorship_bias``, ``falsifiability``). The caller decides
        what the flag means in their product (block, warn, escalate).

        Set ``flag_unknown=True`` to also flag claims that didn't match
        any primitive — useful when the consumer wants conservative
        defaults (anything we couldn't classify gets a human look).
        """
        cls = self.classify(decision_text)

        flag = False
        reason: Optional[str] = None
        if cls.mechanism in self.failure_mode_primitives:
            flag = True
            reason = (
                f"Decision invokes '{cls.mechanism}', a known reasoning "
                f"failure mode. Confidence: {cls.confidence or 'n/a'}. "
                f"{cls.reasoning or ''}".strip()
            )
        elif flag_unknown and cls.mechanism == "unknown":
            flag = True
            reason = (
                "Decision text did not match any known reasoning pattern; "
                "manual review requested by caller."
            )
        return DecisionCheckResult(
            classification=cls, flag_for_review=flag, flag_reason=reason
        )

    def ingest(
        self,
        text: str,
        *,
        source_type: str = "user_note",
    ) -> IngestResult:
        """Add a claim to the persistent belief graph (if configured).

        Runs the L1 closed loop:
        ``extract → consistency check → propose refinement (if
        contradicting) → TRUE-eval → golden-gate → merge or revert``.

        When ``ontology_path`` was passed to the constructor, the updated
        ontology is persisted to that path. Otherwise the merge happens
        in an ephemeral copy and ``ontology_path`` in the result is
        ``None`` (the call is effectively a dry-run).

        ``source_type`` is recorded on the merge for downstream auditing
        — use values like ``"research_paper"``, ``"investment_thesis"``,
        ``"founder_intent"`` so reviewers can later filter the belief
        graph by where claims came from.
        """
        self._ensure_llm_state()

        # Use a copy of the persisted ontology so a single failed merge
        # doesn't corrupt the caller's state. ingest_documents writes
        # back to ontology_path on success.
        ontology = self._load_ontology()
        ontology_copy = copy.deepcopy(ontology)

        report = ingest_documents(
            [text],
            ontology=ontology_copy,
            ontology_path=self.ontology_path,
            golden_cases=list(PERSONAL_EPISTEMIC_GOLDEN_CASES),
            priority_rules_path=PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH,
        )

        # The pipeline result for the single ingested doc is the first
        # entry in `ingested`. Use it as our classification.
        ingested = report.get("ingested") or [{}]
        cls = self._result_to_classification(ingested[0], text)

        evolutions = report.get("evolutions") or [{}]
        action = evolutions[0].get("action", "NO_ACTION")
        proposal = evolutions[0].get("proposal") or {}
        primitive_updated: Optional[str] = None
        merge_status: str

        if report["merges_applied"] >= 1:
            merge_status = "merged"
            primitive_updated = proposal.get("primitive_name")
        elif report["merges_reverted"] >= 1:
            merge_status = "reverted_on_regression"
            primitive_updated = proposal.get("primitive_name")
        elif action == "PROPOSE_REFINEMENT":
            merge_status = "evaluated"
            primitive_updated = proposal.get("primitive_name")
        elif action == "ESCALATE_REVIEW":
            merge_status = "evaluated"
        else:
            merge_status = "no_proposal"

        return IngestResult(
            classification=cls,
            merge_status=merge_status,
            primitive_updated=primitive_updated,
            contradicts_prior=action in ("PROPOSE_REFINEMENT", "ESCALATE_REVIEW"),
            ontology_path=str(self.ontology_path) if self.ontology_path else None,
        )

    def query(
        self, primitive: Optional[str] = None
    ) -> List[BeliefRecord]:
        """Return the user's current beliefs.

        Reads from the persisted ontology (or the canonical default if
        no persistence is configured). When ``primitive`` is given,
        returns a single-element list with that primitive's current
        state, or an empty list if it isn't in the ontology.
        """
        ontology = self._load_ontology()
        primitives = ontology.get("primitives", {}) or {}
        records: List[BeliefRecord] = []
        for name, p in primitives.items():
            if primitive and name != primitive:
                continue
            records.append(
                BeliefRecord(
                    primitive=name,
                    definition=str(p.get("definition", "")),
                    aliases=list(p.get("aliases") or []),
                    sources=list(p.get("sources") or []),
                    relations=list(p.get("relations") or []),
                )
            )
        return records


# ---------------------------------------------------------------------------
# Stateless module-level convenience functions
# ---------------------------------------------------------------------------


def classify_belief(
    text: str,
    *,
    use_llm: bool = False,
    llm_model: str = "claude-haiku-4-5",
    api_key: Optional[str] = None,
) -> ClassificationResult:
    """One-shot classification with no persistence and no class instance.

    For products that just need the reasoning pattern of a single string.
    """
    return BeliefOS(
        use_llm=use_llm, llm_model=llm_model, api_key=api_key
    ).classify(text)


def check_decision_text(
    decision_text: str,
    *,
    use_llm: bool = False,
    llm_model: str = "claude-haiku-4-5",
    api_key: Optional[str] = None,
    flag_unknown: bool = False,
    failure_mode_primitives: Optional[Set[str]] = None,
) -> DecisionCheckResult:
    """One-shot decision check with no persistence.

    The Founder-OS pattern: surface a flag iff the decision invokes one
    of the failure-mode primitives.
    """
    return BeliefOS(
        use_llm=use_llm,
        llm_model=llm_model,
        api_key=api_key,
        failure_mode_primitives=failure_mode_primitives,
    ).check_decision(decision_text, flag_unknown=flag_unknown)


__all__ = [
    "BeliefOS",
    "ClassificationResult",
    "DecisionCheckResult",
    "IngestResult",
    "BeliefRecord",
    "FAILURE_MODE_PRIMITIVES",
    "SOUND_REASONING_PRIMITIVES",
    "KNOWN_PRIMITIVES",
    "classify_belief",
    "check_decision_text",
]
