"""N=10 corpus loader.

Each paper is represented by its converted text file in
research_practice/inbox/*.txt (or *.pdf if no .txt exists yet).

Note: research_practice/ was originally a sibling project (research-os/)
folded into neuro-os on 2026-05-14. See research_practice/MIGRATION_NOTES.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# Resolve relative to the neuro-os repo root, not absolute paths,
# so the harness works in any clone location.
_REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = _REPO_ROOT / "research_practice" / "inbox"


@dataclass(frozen=True)
class CorpusEntry:
    paper_id: str          # short slug, matches gold-fixture id field
    paper_title: str       # full title
    text_path: Path        # path to converted .txt
    family: str            # CL / world-model / embodied-AI / eval


# Maps paper number on disk (01-10) to canonical metadata.
# Lock this list — it IS the N=10 corpus per PAPERS_MANIFEST.md.
N10_CORPUS: list[CorpusEntry] = [
    CorpusEntry(
        paper_id="ewc-kirkpatrick-2017",
        paper_title="Overcoming catastrophic forgetting in neural networks",
        text_path=CORPUS_ROOT / "01_kirkpatrick_2017_ewc.txt",
        family="CL",
    ),
    CorpusEntry(
        paper_id="world-models-ha-schmidhuber-2018",
        paper_title="World Models",
        text_path=CORPUS_ROOT / "02_world_models.txt",
        family="world-model",
    ),
    CorpusEntry(
        paper_id="latent-replay-pellegrini-2019",
        paper_title="Latent Replay for Real-Time Continual Learning",
        text_path=CORPUS_ROOT / "03_latent_replay.txt",
        family="CL",
    ),
    CorpusEntry(
        paper_id="gem-lopez-paz-2017",
        paper_title="Gradient Episodic Memory for Continual Learning",
        text_path=CORPUS_ROOT / "04_lopez-paz_2017_gem.txt",
        family="CL",
    ),
    CorpusEntry(
        paper_id="progressive-networks-rusu-2016",
        paper_title="Progressive Neural Networks",
        text_path=CORPUS_ROOT / "05_rusu_2016_progressive_networks.txt",
        family="CL",
    ),
    CorpusEntry(
        paper_id="dreamer-v3-hafner-2023",
        paper_title="Mastering Diverse Domains through World Models (DreamerV3)",
        text_path=CORPUS_ROOT / "06_hafner_2023_dreamer_v3.txt",
        family="world-model",
    ),
    CorpusEntry(
        paper_id="iris-micheli-2023",
        paper_title="Transformers are Sample-Efficient World Models (IRIS)",
        text_path=CORPUS_ROOT / "07_micheli_2023_iris.txt",
        family="world-model",
    ),
    CorpusEntry(
        paper_id="rt2-brohan-2023",
        paper_title="RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control",
        text_path=CORPUS_ROOT / "08_brohan_2023_rt2.txt",
        family="embodied-AI",
    ),
    CorpusEntry(
        paper_id="open-x-embodiment-2023",
        paper_title="Open X-Embodiment: Robotic Learning Datasets and RT-X Models",
        text_path=CORPUS_ROOT / "09_open_x_embodiment_2023.txt",
        family="embodied-AI",
    ),
    CorpusEntry(
        paper_id="helm-liang-2022",
        paper_title="Holistic Evaluation of Language Models (HELM)",
        text_path=CORPUS_ROOT / "10_liang_2022_helm.txt",
        family="eval",
    ),
]


def load_corpus() -> list[CorpusEntry]:
    """Verify all text files exist; return the locked corpus list."""
    missing = [e for e in N10_CORPUS if not e.text_path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing corpus files: " + ", ".join(str(e.text_path) for e in missing)
        )
    return list(N10_CORPUS)
