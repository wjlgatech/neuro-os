"""
Visualization helpers for the Streamlit UI — Graphviz DOT.

Streamlit's ``st.graphviz_chart`` renders DOT strings via a bundled
JS renderer (no system ``dot`` binary required). DOT is a deterministic
text format, so the output is stable across runs and is what the GIF
recorder captures.

Two graphs:

* ``ontology_dot(ontology, baseline=None)`` — five neuroscience
  primitives as nodes, canonical relations as edges. Node fill scales
  with source count; nodes whose source list grew vs ``baseline`` get
  a thick green border.

* ``routing_dot(rules, canonical_rules=None)`` — bipartite: cues on
  the left, mechanisms on the right. Edge color marks state:

      blue   — canonical and present
      green  — present but missing from canonical (freshly added by flywheel)
      gray   — missing from current rules (degraded; canonical only)
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple


# Neuroscience palette stays pinned: these names must always render with
# their established colors so the existing tabs are visually unchanged.
_PRIMITIVE_COLORS: Dict[str, str] = {
    "predictive_processing": "#3b82f6",   # blue
    "reinforcement_learning": "#10b981",  # emerald
    "hebbian_learning": "#f59e0b",        # amber
    "attention": "#8b5cf6",               # violet
    "hierarchical_abstraction": "#ec4899",  # pink
}

# Stable fallback palette for any primitive not in ``_PRIMITIVE_COLORS``.
# We hash the primitive name to pick a slot, so colors are deterministic
# across runs and across machines (no `random` calls).
_FALLBACK_PALETTE: List[str] = [
    "#0ea5e9",  # sky
    "#14b8a6",  # teal
    "#22c55e",  # green
    "#eab308",  # yellow
    "#f97316",  # orange
    "#ef4444",  # red
    "#a855f7",  # purple
    "#d946ef",  # fuchsia
]


def _color_for(name: str) -> str:
    """Return a deterministic color for a primitive name."""
    if name in _PRIMITIVE_COLORS:
        return _PRIMITIVE_COLORS[name]
    digest = hashlib.md5(name.encode("utf-8")).digest()
    return _FALLBACK_PALETTE[digest[0] % len(_FALLBACK_PALETTE)]


def domain_colors(ontology: Dict[str, Any]) -> Dict[str, str]:
    """Return ``{primitive_name: hex_color}`` for every primitive in the ontology.

    Neuroscience names use their pinned colors; anything else gets a
    stable hash-bucket color from the fallback palette.
    """
    primitives = ontology.get("primitives", {}) or {}
    return {name: _color_for(name) for name in primitives}


def _esc(s: str) -> str:
    """Escape a string for use as a DOT label."""
    return str(s).replace('"', '\\"').replace("\n", "\\n")


def _safe_id(s: str) -> str:
    out = []
    for ch in str(s):
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    return "".join(out) or "n"


def _pretty_label(name: str) -> str:
    return name.replace("_", "\n")


def ontology_dot(
    ontology: Dict[str, Any],
    baseline: Optional[Dict[str, Any]] = None,
) -> str:
    """Render the ontology as a DOT string for ``st.graphviz_chart``."""
    primitives = ontology.get("primitives", {}) or {}
    baseline_primitives = (baseline or {}).get("primitives", {}) if baseline else {}

    lines: List[str] = [
        "graph ontology {",
        '  bgcolor="white";',
        "  layout=circo;",
        "  mindist=1.0;",
        '  node [shape=circle, style="filled", fontname="Helvetica", fontsize=10,'
        " fixedsize=true];",
        '  edge [color="#9ca3af", fontname="Helvetica", fontsize=8, penwidth=1.5];',
    ]

    for name, primitive in primitives.items():
        color = _color_for(name)
        baseline_sources = (
            len(baseline_primitives.get(name, {}).get("sources", []) or [])
            if baseline else None
        )
        current_sources = len(primitive.get("sources", []) or [])
        grew = baseline_sources is not None and current_sources > baseline_sources
        border = "#16a34a" if grew else "#374151"
        penwidth = 4 if grew else 1
        # source count gives a small width bump
        width = 0.75 + 0.06 * min(current_sources, 5)
        lines.append(
            f'  {_safe_id(name)} ['
            f'label="{_esc(_pretty_label(name))}",'
            f' fillcolor="{color}", color="{border}", penwidth={penwidth},'
            f' fontcolor="white", fixedsize=true, width={width:.2f}, height={width:.2f}];'
        )

    seen_pairs = set()
    for name, primitive in primitives.items():
        for rel in primitive.get("relations", []) or []:
            if rel not in primitives:
                continue
            pair = tuple(sorted([name, rel]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            lines.append(f"  {_safe_id(pair[0])} -- {_safe_id(pair[1])};")

    lines.append("}")
    return "\n".join(lines)


def routing_dot(
    rules: List[Tuple[str, str]],
    canonical_rules: Optional[List[Tuple[str, str]]] = None,
    freshly_promoted: Optional[List[Tuple[str, str]]] = None,
) -> str:
    """Render the routing rules as a bipartite DOT string.

    ``freshly_promoted`` is an explicit set of rules promoted by the
    most recent flywheel run; those edges are drawn in green even if
    they're also canonical. This makes the post-repair frame visually
    distinct from a canonical state.
    """
    rule_set = {tuple(r) for r in rules}
    canonical_set = {tuple(r) for r in (canonical_rules or [])}
    fresh_set = {tuple(r) for r in (freshly_promoted or [])}
    cues = sorted({c for c, _ in (canonical_set | rule_set)})
    mechanisms = sorted({m for _, m in (canonical_set | rule_set)})

    lines: List[str] = [
        "digraph routing {",
        '  bgcolor="white";',
        "  rankdir=LR;",
        "  nodesep=0.08;",
        "  ranksep=1.0;",
        '  node [shape=box, style="filled,rounded", fontname="Helvetica", fontsize=9,'
        " width=1.5, height=0.3, fixedsize=true];",
        '  edge [fontname="Helvetica", fontsize=9, arrowsize=0.6, penwidth=2];',
    ]

    # Group cues into a left "rank" cluster (still no actual cluster styling).
    lines.append("  { rank=source;")
    for cue in cues:
        lines.append(
            f'    cue_{_safe_id(cue)} [label="{_esc(cue)}",'
            f' fillcolor="#e0f2fe", color="#0284c7"];'
        )
    lines.append("  }")

    lines.append("  { rank=sink;")
    for mech in mechanisms:
        color = _color_for(mech)
        lines.append(
            f'    mech_{_safe_id(mech)} [label="{_esc(_pretty_label(mech))}",'
            f' fillcolor="{color}", color="#1f2937", fontcolor="white"];'
        )
    lines.append("  }")

    for pair in canonical_set | rule_set:
        cue, mech = pair
        in_current = pair in rule_set
        in_canonical = pair in canonical_set
        if pair in fresh_set:
            # Highlight rules promoted in the most recent flywheel run.
            color, width, style = "#16a34a", 3.5, "solid"
        elif in_current and not in_canonical:
            color, width, style = "#16a34a", 3.5, "solid"
        elif in_current and in_canonical:
            color, width, style = "#0284c7", 1.6, "solid"
        else:
            color, width, style = "#d1d5db", 1.6, "dashed"
        lines.append(
            f'  cue_{_safe_id(cue)} -> mech_{_safe_id(mech)} '
            f'[color="{color}", penwidth={width}, style={style}];'
        )

    lines.append("}")
    return "\n".join(lines)


__all__ = ["ontology_dot", "routing_dot", "domain_colors"]
