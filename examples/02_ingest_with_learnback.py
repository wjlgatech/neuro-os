"""
Example 02 — Ingest a citation-rich contradiction; watch the ontology learn.

The system detects that the new claim contradicts the canonical attention
definition, scores the proposal (citations make it strong evidence), runs
the golden-case gate, merges the refinement, and persists the updated
ontology to disk.

Run::

    python examples/02_ingest_with_learnback.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.api import ingest_documents  # noqa: E402


def main() -> None:
    out_dir = Path(tempfile.mkdtemp(prefix="neuro_os_learn_back_"))
    ontology_path = out_dir / "ontology.json"

    # Citation-rich contradiction. Year, author, DOI, URL, arXiv id all present.
    contradiction = (
        "Vaswani et al. (2017) https://doi.org/10.1234/qkv shows attention does not "
        "gate signals; routing is via softmax similarity. arXiv:1706.03762."
    )

    print("ingesting one citation-rich contradiction...")
    report = ingest_documents([contradiction], ontology_path=ontology_path)
    print(f"  evolution action: {report['evolutions'][0]['action']}")
    print(f"  evaluation:       {report['evaluations'][0]['decision']}")
    print(f"  merges_applied:   {report['merges_applied']}")
    print(f"  merges_reverted:  {report['merges_reverted']}")
    print()

    on_disk = json.loads(ontology_path.read_text())
    print(f"new attention definition: {on_disk['primitives']['attention']['definition']!r}")
    print(f"sources recorded:         {on_disk['primitives']['attention']['sources']}")
    print()
    print(f"ontology persisted to: {ontology_path}")


if __name__ == "__main__":
    main()
