"""Ontology builder for Neuro-OS.

Builds a machine-readable ontology from the canonical neuroscience source index
and accepted primitive feedback records.

The ontology is intentionally simple: primitives, sources, relationships,
evaluation metrics, and feedback-derived definitions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

CANONICAL_PRIMITIVES = {
    "predictive_processing": ["predictive processing", "bayesian brain", "free-energy", "free energy"],
    "hebbian_learning": ["hebbian", "stdp", "synaptic plasticity"],
    "reinforcement_learning": ["reinforcement learning", "dopamine", "reward"],
    "attention": ["attention", "saliency", "gating"],
    "hierarchical_abstraction": ["hierarchical", "hierarchy", "cortex", "abstraction"],
}

SOURCE_TYPES = ["Papers", "GitHub Repos", "Blog Posts"]


def empty_ontology() -> Dict[str, Any]:
    return {
        "primitives": {
            name: {
                "aliases": aliases,
                "definition": "",
                "sources": [],
                "relations": [],
                "evaluation": {},
                "feedback": [],
            }
            for name, aliases in CANONICAL_PRIMITIVES.items()
        },
        "source_count": 0,
        "relation_count": 0,
    }


def infer_primitive(text: str) -> str | None:
    lower = text.lower()
    for primitive, aliases in CANONICAL_PRIMITIVES.items():
        if any(alias in lower for alias in aliases):
            return primitive
    return None


def parse_source_index(text: str) -> Dict[str, Any]:
    ontology = empty_ontology()
    current_primitive: str | None = None
    current_source_type: str | None = None
    current_title: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        header_match = re.match(r"##\s+\d+\.\s+(.+)", line)
        if header_match:
            current_primitive = infer_primitive(header_match.group(1))
            current_source_type = None
            current_title = None
            continue

        if line.startswith("### "):
            label = line.replace("###", "").strip()
            current_source_type = label if label in SOURCE_TYPES else None
            current_title = None
            continue

        if line.startswith("- **") and current_primitive:
            title = line.split("**", 2)[1] if "**" in line else line[2:]
            current_title = title.strip()
            ontology["primitives"][current_primitive]["sources"].append({
                "title": current_title,
                "type": current_source_type or "Unknown",
                "url": "",
                "key_idea": "",
            })
            ontology["source_count"] += 1
            continue

        if current_primitive and current_title and line.startswith("URL:"):
            ontology["primitives"][current_primitive]["sources"][-1]["url"] = line.replace("URL:", "").strip()
            continue

        if current_primitive and current_title and line.startswith("Key idea:"):
            idea = line.replace("Key idea:", "").strip()
            ontology["primitives"][current_primitive]["sources"][-1]["key_idea"] = idea
            if not ontology["primitives"][current_primitive]["definition"]:
                ontology["primitives"][current_primitive]["definition"] = idea
            continue

    # Hard-code canonical source-index graph because it is explicitly declared in source_index.md.
    relations = [
        ("predictive_processing", "USES", "attention"),
        ("predictive_processing", "IMPLEMENTED_BY", "hebbian_learning"),
        ("predictive_processing", "BIASED_BY", "reinforcement_learning"),
        ("predictive_processing", "ORGANIZED_ACROSS", "hierarchical_abstraction"),
        ("hebbian_learning", "GENERALIZED_BY", "reinforcement_learning"),
        ("reinforcement_learning", "SCALED_BY", "hierarchical_abstraction"),
        ("hierarchical_abstraction", "UNIFIES", "predictive_processing"),
        ("hierarchical_abstraction", "UNIFIES", "attention"),
    ]
    for src, rel, dst in relations:
        ontology["primitives"][src]["relations"].append({"relation": rel, "target": dst})
        ontology["relation_count"] += 1

    return ontology


def merge_primitive_feedback(ontology: Dict[str, Any], records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    for record in records:
        if record.get("decision") != "ACCEPT":
            continue
        update = record.get("update", {})
        primitive = update.get("primitive_name")
        if primitive not in ontology["primitives"]:
            continue
        ontology["primitives"][primitive]["feedback"].append(record)
        definition = update.get("one_sentence_definition")
        if definition:
            ontology["primitives"][primitive]["definition"] = definition
    return ontology


def write_ontology(ontology: Dict[str, Any], path: str = "parsed/ontology.json") -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(ontology, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import sys

    source_path = sys.argv[1] if len(sys.argv) > 1 else "sources/source_index.md"
    ontology = parse_source_index(Path(source_path).read_text(encoding="utf-8"))
    write_ontology(ontology)
    print(json.dumps({"source_count": ontology["source_count"], "relation_count": ontology["relation_count"]}, indent=2))
