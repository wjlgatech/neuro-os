"""Shared data loaders for the world-os v0 Streamlit app.

All loaders read REAL data from disk:
  - 60 Sonnet 4.6 extractions from experiments/phase_1/results/extractions/
  - 10 hand-extracted gold cards from tests/fixtures/research/gold/
  - Real paper text from research_practice/inbox/*.txt (folded into neuro-os
    on 2026-05-14; was previously a sibling project research-os/)
  - Inter-rater judge results from experiments/phase_1/results/inter_rater_agreement.json

Anti-goal: nothing in this module loads from decisions/synthetic.py or
decisions/outcomes.py. Those modules are v1 prototype and are deliberately
invisible in the v0 UI (see DESIGN_BRIEF.md anti-goals).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE1_RESULTS = REPO_ROOT / "experiments" / "phase_1" / "results"
EXTRACTIONS_DIR = PHASE1_RESULTS / "extractions"
GOLD_DIR = REPO_ROOT / "tests" / "fixtures" / "research" / "gold"
PAPERS_DIR = REPO_ROOT / "research_practice" / "inbox"


# Maps short paper_id to the paper's text file under research_practice/inbox/.
PAPER_TXT_BY_ID = {
    "ewc-kirkpatrick-2017": "01_kirkpatrick_2017_ewc.txt",
    "world-models-ha-schmidhuber-2018": "02_world_models.txt",
    "latent-replay-pellegrini-2019": "03_latent_replay.txt",
    "gem-lopez-paz-2017": "04_lopez-paz_2017_gem.txt",
    "progressive-networks-rusu-2016": "05_rusu_2016_progressive_networks.txt",
    "dreamer-v3-hafner-2023": "06_hafner_2023_dreamer_v3.txt",
    "iris-micheli-2023": "07_micheli_2023_iris.txt",
    "rt2-brohan-2023": "08_brohan_2023_rt2.txt",
    "open-x-embodiment-2023": "09_open_x_embodiment_2023.txt",
    "helm-liang-2022": "10_liang_2022_helm.txt",
}


SYSTEMS = [
    "B1_vanilla_rag",
    "B2_graph_rag",
    "B3_summary",
    "B4_single_shot_mechanism_card",
    "B5_reviewed_mechanism_card",
    "Ours_full_loop",
    "Ours_v2_with_bias_check",
    "Ours_minus_review",
]


def list_systems() -> list[str]:
    """Return only systems that have at least one extraction on disk."""
    return [s for s in SYSTEMS if (EXTRACTIONS_DIR / s).exists()]


def list_papers() -> list[tuple[str, str]]:
    """Return [(paper_id, title), ...] for the N=10 corpus."""
    out = []
    for path in sorted(GOLD_DIR.glob("*.json")):
        c = json.loads(path.read_text())
        out.append((c["id"], c["paper_title"]))
    return out


def load_extraction(system: str, paper_id: str) -> Optional[dict]:
    """Load one (system, paper) extraction; None if not present."""
    path = EXTRACTIONS_DIR / system / f"{paper_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_gold(paper_id: str) -> Optional[dict]:
    """Load the gold card for a paper."""
    for path in GOLD_DIR.glob("*.json"):
        data = json.loads(path.read_text())
        if data["id"] == paper_id:
            return data
    return None


def load_paper_text(paper_id: str) -> str:
    """Return the full text of the paper (pdftotext output)."""
    fname = PAPER_TXT_BY_ID.get(paper_id)
    if not fname:
        return ""
    path = PAPERS_DIR / fname
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def verify_excerpt_in_text(excerpt: str, full_text: str) -> bool:
    """Substring match after whitespace + case normalization.

    Same logic as experiments.phase_1.extractors.base.verify_excerpt_in_text;
    duplicated here to keep world_os/ independent of phase_1 imports.
    """
    if not excerpt:
        return False
    norm = lambda s: re.sub(r"\s+", " ", s.lower().strip())
    return norm(excerpt) in norm(full_text)


def locate_excerpt_in_text(excerpt: str, full_text: str) -> Optional[tuple[int, int]]:
    """Return (start, end) char offsets of the excerpt in the paper, or None.

    Returns the position in the ORIGINAL text (not normalized) so the UI
    can highlight in place. Uses a normalized-text fallback for matching;
    if a match is found in normalized space, we re-scan the original to
    find the closest matching span.
    """
    if not excerpt:
        return None
    # Try a direct case-insensitive search first.
    lower = full_text.lower()
    needle = excerpt.lower()
    idx = lower.find(needle)
    if idx >= 0:
        return (idx, idx + len(needle))

    # Whitespace-normalize both sides; find normalized span; map back.
    def norm_with_map(s: str) -> tuple[str, list[int]]:
        """Return (normalized, original_index_per_normalized_char)."""
        norm_chars = []
        idx_map = []
        prev_ws = True
        for i, c in enumerate(s):
            if c.isspace():
                if not prev_ws:
                    norm_chars.append(" ")
                    idx_map.append(i)
                    prev_ws = True
            else:
                norm_chars.append(c.lower())
                idx_map.append(i)
                prev_ws = False
        return "".join(norm_chars), idx_map

    norm_text, idx_map = norm_with_map(full_text)
    norm_excerpt, _ = norm_with_map(excerpt)
    pos = norm_text.find(norm_excerpt)
    if pos < 0:
        return None
    start_orig = idx_map[pos]
    end_norm = pos + len(norm_excerpt) - 1
    end_orig = idx_map[min(end_norm, len(idx_map) - 1)] + 1
    return (start_orig, end_orig)


def load_inter_rater_data() -> Optional[dict]:
    """Load the Wk 9 inter-rater agreement JSON."""
    path = PHASE1_RESULTS / "inter_rater_agreement.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def compute_provenance_stats(system: str) -> dict:
    """Per-system: how many extractions claim a source_excerpt, and how many
    actually verify against the source paper.
    """
    sys_dir = EXTRACTIONS_DIR / system
    if not sys_dir.exists():
        return {"n_total": 0, "n_with_excerpt": 0, "n_verified": 0, "pass_rate": 0.0}

    n_total = 0
    n_with_excerpt = 0
    n_verified = 0

    for path in sorted(sys_dir.glob("*.json")):
        n_total += 1
        data = json.loads(path.read_text())
        excerpt = data.get("source_excerpt", "")
        if excerpt:
            n_with_excerpt += 1
        if data.get("pinned_provenance"):
            n_verified += 1

    return {
        "n_total": n_total,
        "n_with_excerpt": n_with_excerpt,
        "n_verified": n_verified,
        "pass_rate": n_verified / n_total if n_total else 0.0,
    }
