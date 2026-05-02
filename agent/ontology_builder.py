"""
Ontology Builder.

Parses a source-index document into a structured ontology. Supports two
input formats:

* Markdown style — each primitive is introduced by a ``## N. NAME``
  heading, with optional ``### Papers`` / ``### Repos`` subsections and
  ``- **Title**`` source bullets. This is the format used by the curated
  source-index files in this repository.

* Plain ``Primitive: Name`` style — bulleted ``- source: ...`` and
  ``- alias: ...`` lines under each primitive heading.

The resulting ontology dict has shape::

    {
      "primitives": {
        "<snake_case_name>": {
          "definition": str,
          "aliases": [str, ...],
          "sources": [str, ...],
          "relations": [str, ...],
        }
      },
      "source_count": int,
      "relation_count": int,
    }
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Iterable, Union

from agent.ingestion_pipeline import CANONICAL_PRIMITIVES


_HEADING_HASH_RE = re.compile(r"^##\s*\d*\.?\s*(.+?)\s*$")
_HEADING_PRIMITIVE_RE = re.compile(r"^primitive:\s*(.+?)\s*$", re.IGNORECASE)
_BOLD_TITLE_RE = re.compile(r"\*\*([^*]+)\*\*")


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _seed_canonical(name_slug: str) -> Dict[str, Any]:
    """Return a copy of canonical primitive data for ``name_slug`` if known."""
    if name_slug in CANONICAL_PRIMITIVES:
        seed = CANONICAL_PRIMITIVES[name_slug]
        return {
            "definition": seed.get("definition", ""),
            "aliases": list(seed.get("aliases", [])),
            "sources": [],
            "relations": list(seed.get("relations", [])),
        }
    return {"definition": "", "aliases": [], "sources": [], "relations": []}


def _normalize_lines(text_or_lines: Union[str, Iterable[str]]) -> List[str]:
    if isinstance(text_or_lines, str):
        return text_or_lines.splitlines()
    return list(text_or_lines)


def parse_source_index(text_or_lines: Union[str, Iterable[str]]) -> Dict[str, Any]:
    """Parse a source-index document into the ontology dict shape."""
    lines = _normalize_lines(text_or_lines)
    primitives: Dict[str, Dict[str, Any]] = {}
    current: str | None = None

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        primitive_match = _HEADING_PRIMITIVE_RE.match(stripped)
        if primitive_match:
            current = _slugify(primitive_match.group(1))
            primitives.setdefault(current, _seed_canonical(current))
            continue

        if stripped.startswith("##") and not stripped.startswith("###"):
            heading_match = _HEADING_HASH_RE.match(stripped)
            if heading_match:
                current = _slugify(heading_match.group(1))
                primitives.setdefault(current, _seed_canonical(current))
                continue

        if current is None:
            continue

        bullet_match = re.match(r"^[-*]\s*(.*)", stripped)
        if bullet_match:
            entry = bullet_match.group(1).strip()
            lower_entry = entry.lower()
            if lower_entry.startswith("source:"):
                primitives[current]["sources"].append(entry.split(":", 1)[1].strip())
                continue
            if lower_entry.startswith("alias:"):
                primitives[current]["aliases"].append(entry.split(":", 1)[1].strip())
                continue
            bold = _BOLD_TITLE_RE.search(entry)
            if bold:
                primitives[current]["sources"].append(bold.group(1).strip())
                continue
            primitives[current]["sources"].append(entry)
            continue

        if stripped.lower().startswith("key idea:"):
            idea = stripped.split(":", 1)[1].strip()
            if idea and not primitives[current].get("definition"):
                primitives[current]["definition"] = idea

    source_count = sum(len(p.get("sources", [])) for p in primitives.values())
    relation_count = sum(len(p.get("relations", [])) for p in primitives.values())
    return {
        "primitives": primitives,
        "source_count": source_count,
        "relation_count": relation_count,
    }


def build_ontology(source_path: str, output_path: str) -> Dict[str, Any]:
    """Build an ontology from a source-index file and write it to JSON.

    Returns the ontology dict for convenience.
    """
    with open(source_path, "r", encoding="utf-8") as f:
        ontology = parse_source_index(f.read())
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ontology, f, indent=2)
    return ontology


__all__ = ["parse_source_index", "build_ontology"]
