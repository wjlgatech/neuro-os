"""
Example 01 — Single-document extraction with TRUE scoring.

Run::

    python examples/01_extract.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.api import process_text  # noqa: E402


def main() -> None:
    text = (
        "Predictive coding minimizes sensory prediction error across cortical "
        "hierarchy. Friston (2010) frames this as free-energy minimization."
    )
    result = process_text(text)
    print(f"mechanism: {result['mechanism']}")
    print(f"decision:  {result['pipeline_decision']}")
    print(f"TRUE:      {result['true_score']}")
    print(f"action:    {result['action']}")
    if result["proposal"]:
        print("a refinement was proposed; this would feed the self-evolving loop")


if __name__ == "__main__":
    main()
