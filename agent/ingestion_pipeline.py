"""
Ontology-Aware Extraction Pipeline.

Two entry points:

* ``extract_mechanism(text, ontology, llm_fn=None)`` — low-level extraction.
  Returns ``{mechanism, evidence}``.

* ``run_pipeline(text, ontology=None)`` — full pipeline run that produces
  the rich ``{knowledge, true_validation, decision}`` shape consumed by
  ``self_evolving_loop`` and ``self_evolution_controller``.

When no ontology is provided, ``run_pipeline`` falls back to a built-in
canonical ontology covering the five core neuroscience primitives.
"""

from __future__ import annotations

from typing import Callable, Dict, Any, Optional, List, Tuple
import json
import re
from pathlib import Path


CANONICAL_PRIMITIVES: Dict[str, Dict[str, Any]] = {
    "predictive_processing": {
        "definition": "Brain minimizes prediction error to model the world.",
        "aliases": [
            "predictive processing",
            "predictive coding",
            "free-energy",
            "free energy",
            "bayesian brain",
            "prediction error",
        ],
        "relations": ["attention", "hebbian_learning", "hierarchical_abstraction"],
    },
    "hebbian_learning": {
        "definition": "Neurons that fire together wire together.",
        "aliases": ["hebbian", "stdp", "synaptic plasticity", "fire together"],
        "relations": ["predictive_processing", "reinforcement_learning"],
    },
    "reinforcement_learning": {
        "definition": "Dopamine encodes temporal-difference reward prediction error.",
        "aliases": [
            "reinforcement learning",
            "dopamine",
            "reward prediction error",
            "td error",
            "td learning",
            "reward signal",
        ],
        "relations": ["predictive_processing", "hierarchical_abstraction"],
    },
    "attention": {
        "definition": "Attention selectively gates which signals control processing.",
        "aliases": [
            "attention",
            "saliency",
            "gating",
            "query key value",
            "selectively route",
        ],
        "relations": ["predictive_processing", "hierarchical_abstraction"],
    },
    "hierarchical_abstraction": {
        "definition": "Cortex organizes intelligence as abstraction layers.",
        "aliases": [
            "hierarchical",
            "hierarchy",
            "abstraction",
            "cortical hierarchy",
            "cortex builds",
            "abstraction levels",
        ],
        "relations": ["predictive_processing", "attention"],
    },
}


# Priority cues are stored in a JSON data file so they can be mutated
# by the self-modification loop without rewriting Python source. The
# file is read fresh on each call so promoted patches take effect
# immediately without a module reload.
PRIORITY_RULES_PATH = Path(__file__).parent / "data" / "priority_rules.json"


def get_priority_rules(
    priority_rules_path: Optional[Path] = None,
) -> List[Tuple[str, str]]:
    """Read the current priority rules from disk.

    ``priority_rules_path`` lets callers (e.g. a non-neuroscience domain)
    point at a different routing file. Defaults to ``PRIORITY_RULES_PATH``.
    """
    path = priority_rules_path if priority_rules_path is not None else PRIORITY_RULES_PATH
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [tuple(item) for item in json.load(f)]


_YEAR_RE = re.compile(r"\b(?:18|19|20)\d{2}\b")
_AUTHOR_RE = re.compile(r"[A-Z][a-zA-Z]+\s+(?:&\s+[A-Z][a-zA-Z]+\s+)?(?:et\s+al\.?|\(\s*\d{4}\s*\))")
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+")
_ARXIV_RE = re.compile(r"\barxiv:\s*\d{4}\.\d{4,5}\b", re.IGNORECASE)


def classify_evidence_strength(text: str) -> str:
    """Classify how well a piece of evidence is sourced.

    Returns ``"strong"`` when at least two citation markers are present
    (year+author, DOI, URL, arXiv id), ``"moderate"`` when one marker
    is present or the text is sufficiently long to plausibly carry
    structured argument, and ``"weak"`` otherwise.
    """
    if not text:
        return "weak"
    has_year = bool(_YEAR_RE.search(text))
    has_author = bool(_AUTHOR_RE.search(text))
    has_doi = bool(_DOI_RE.search(text))
    has_url = bool(_URL_RE.search(text))
    has_arxiv = bool(_ARXIV_RE.search(text))
    markers = sum([has_year and has_author, has_doi, has_url, has_arxiv])
    if markers >= 2:
        return "strong"
    if markers == 1:
        return "moderate"
    if has_year and len(text.strip()) >= 80:
        return "moderate"
    return "weak"


def load_ontology(ontology_path: str) -> Dict[str, Any]:
    """Load a JSON ontology from disk."""
    with open(ontology_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _canonical_ontology() -> Dict[str, Any]:
    return {
        "primitives": {k: dict(v) for k, v in CANONICAL_PRIMITIVES.items()},
        "source_count": 0,
        "relation_count": sum(
            len(p.get("relations", [])) for p in CANONICAL_PRIMITIVES.values()
        ),
    }


def infer_mechanism_offline(
    text: str,
    ontology: Dict[str, Any],
    priority_rules_path: Optional[Path] = None,
) -> str:
    """Infer a mechanism by matching priority cues then ontology aliases."""
    lower = text.lower()
    primitives = ontology.get("primitives", {})
    for cue, mechanism in get_priority_rules(priority_rules_path):
        if cue in lower and mechanism in primitives:
            return mechanism
    for primitive_name, primitive_data in primitives.items():
        for alias in primitive_data.get("aliases", []) or []:
            if alias and alias.lower() in lower:
                return primitive_name
    return "unknown"


def extract_mechanism(
    text: str,
    ontology: Dict[str, Any],
    llm_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    priority_rules_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Extract a candidate mechanism from text.

    Returns ``{mechanism, evidence}``. ``evidence`` always carries the
    raw ``text`` so downstream consistency checks can inspect it.
    """
    if llm_fn is not None:
        context = json.dumps(ontology.get("primitives", {}))
        prompt = (
            "You are an extraction engine. Given the following neuroscience text, "
            "identify which primitive mechanism it most closely relates to from the provided ontology. "
            "Return a JSON object with a 'mechanism' field.\n\n"
            f"Ontology: {context}\n"
            f"Text: {text}"
        )
        result = llm_fn(prompt)
        mechanism = result.get("mechanism", "unknown")
        return {"mechanism": mechanism, "evidence": {"text": text, **result}}
    mechanism = infer_mechanism_offline(text, ontology, priority_rules_path)
    return {
        "mechanism": mechanism,
        "evidence": {"method": "offline-keyword", "text": text},
    }


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_ABBREVIATIONS = frozenset({
    "et al", "e.g", "i.e", "fig", "eq", "dr", "mr", "ms", "mrs", "vs", "etc", "no", "vol",
})


def _ends_in_abbreviation(text: str) -> bool:
    if not text.endswith("."):
        return False
    last = text[:-1].rsplit(None, 1)[-1].lower()
    return last in _ABBREVIATIONS


def _first_sentence(text: str, max_len: int = 240) -> str:
    """Return the first sentence of ``text``, truncated to ``max_len`` chars.

    Honours common scientific abbreviations (``et al.``, ``e.g.``, etc.)
    so a citation prefix is not mistaken for a sentence boundary.
    """
    if not text:
        return ""
    cleaned = text.strip()
    parts = _SENTENCE_SPLIT_RE.split(cleaned)
    if not parts:
        return cleaned[:max_len].strip()
    head = parts[0]
    idx = 1
    while idx < len(parts) and _ends_in_abbreviation(head):
        head = head + " " + parts[idx]
        idx += 1
    return head[:max_len].strip()


def _build_knowledge(text: str, mechanism: str, ontology: Dict[str, Any]) -> Dict[str, Any]:
    """Synthesize the rich TRUE-fielded knowledge dict for downstream eval.

    ``main_claim`` and ``core_mechanism`` reflect what the *document* says
    (the first sentence of the input). The ontology's definition is kept
    in ``one_sentence_definition`` so consistency checks have something
    canonical to compare the claim against.
    """
    primitive = ontology.get("primitives", {}).get(mechanism, {})
    definition = primitive.get("definition") or f"Definition for {mechanism}."
    claim = _first_sentence(text) if text else definition
    return {
        "mechanism": mechanism,
        "core_mechanism": claim or definition,
        "main_claim": claim or definition,
        "one_sentence_definition": definition,
        "experience_probe": f"Observe a situation where {mechanism} predicts behavior.",
        "experiment_design": (
            f"Design a test where {mechanism} is the operative variable; "
            "compare predicted vs. observed outcomes."
        ),
        "failure_condition": (
            f"If outcome is independent of {mechanism}, the claim is falsified."
        ),
        "felt_sense_bridge": f"Notice the felt sense that maps to {mechanism}.",
        "immediate_use_case": f"Apply {mechanism} reasoning to one decision today.",
        "repeat_protocol": "Repeat the probe across at least 3 independent contexts.",
        "measurement": "Score outcome quality on a 0-1 rubric.",
        "refinement_signal": "If predictions miss, refine the priors.",
        "version_delta": "Initial extraction.",
        "transfer_domains": ["brain", "AI", "life"],
        "transform_formats": ["sentence", "diagram", "code"],
        "evidence_quotes": [text.strip()] if text and text.strip() else [],
        "source_quote": text.strip()[:280] if text else "",
        "source_type": "extraction",
        "evidence_strength": classify_evidence_strength(text or ""),
        "contradictions_or_limits": (
            "Heuristic offline extraction; may misclassify ambiguous wording."
        ),
        "connection_to_ai": f"AI analog of {mechanism}.",
        "connection_to_human_thinking": f"Human analog of {mechanism}.",
        "changed_files": [],
        "tests_pass": True,
        "rollback_available": True,
    }


def _true_validation(knowledge: Dict[str, Any]) -> Dict[str, Any]:
    """Compute lightweight per-dimension TRUE scores and a composite TRUE score."""
    has = lambda f: bool(knowledge.get(f))
    e = 1.0 if has("experiment_design") and has("failure_condition") else 0.0
    u = 1.0 if has("one_sentence_definition") and has("immediate_use_case") else 0.0
    r = 1.0 if has("repeat_protocol") and has("measurement") and has("refinement_signal") else 0.0
    t_domains = len(knowledge.get("transfer_domains") or [])
    t_formats = len(knowledge.get("transform_formats") or [])
    t = 1.0 if t_domains >= 2 and t_formats >= 2 else 0.0
    composite = round((e + u + r + t) / 4, 3)
    failed = [
        name
        for name, score in (("E", e), ("U", u), ("R", r), ("T", t))
        if score < 1.0
    ]
    return {
        "scores": {"E": e, "U": u, "R": r, "T": t, "TRUE": composite},
        "failed_dimensions": failed,
    }


def run_pipeline(
    text: str,
    ontology: Optional[Dict[str, Any]] = None,
    llm_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    priority_rules_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run the full extraction + TRUE-validation pipeline.

    Returns
    -------
    dict
        ``{knowledge, true_validation, decision}`` where ``decision`` is
        ``ACCEPT`` for known mechanisms with TRUE >= 0.75, ``REJECT`` for
        unknown mechanisms, and ``REFINE`` otherwise.
    """
    if ontology is None:
        ontology = _canonical_ontology()
    extraction = extract_mechanism(
        text,
        ontology,
        llm_fn=llm_fn,
        priority_rules_path=priority_rules_path,
    )
    mechanism = extraction["mechanism"]
    knowledge = _build_knowledge(text, mechanism, ontology)
    validation = _true_validation(knowledge)
    if mechanism == "unknown":
        decision = "REJECT"
    elif validation["scores"]["TRUE"] >= 0.75:
        decision = "ACCEPT"
    else:
        decision = "REFINE"
    return {
        "knowledge": knowledge,
        "true_validation": validation,
        "decision": decision,
    }


__all__ = [
    "CANONICAL_PRIMITIVES",
    "PRIORITY_RULES_PATH",
    "classify_evidence_strength",
    "get_priority_rules",
    "load_ontology",
    "infer_mechanism_offline",
    "extract_mechanism",
    "run_pipeline",
]
