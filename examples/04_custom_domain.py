"""
Example 04 — Register a custom domain in 30 lines.

Domains decouple *what* (ontology + golden cases + extractor + validators)
from *how* (the OEC loops). This example registers a toy "code vs prose"
domain and runs a stable check against it.

Apply the same pattern to anything you want OEC over: lead scoring, content
moderation, code-style checks, lint rules.

Run::

    python examples/04_custom_domain.py
"""
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.domains import (  # noqa: E402
    Domain,
    get_domain,
    import_smoke_validator,
    register_domain,
)
from agent.self_modification import run_self_modification  # noqa: E402


def code_or_prose_extractor(text: str) -> Dict[str, Any]:
    """Toy classifier: looks for code-shaped tokens; else prose."""
    code_tokens = ("()", "{", "}", "import ", "def ", "=>", "class ")
    mechanism = "code" if any(t in text for t in code_tokens) else "prose"
    return {
        "knowledge": {"mechanism": mechanism, "main_claim": text[:80]},
        "true_validation": {"scores": {"TRUE": 1.0}},
        "decision": "ACCEPT",
    }


def main() -> None:
    domain = Domain(
        name="code_or_prose_v1",
        ontology={"primitives": {"code": {}, "prose": {}}},
        golden_cases=[
            {"text": "import json\ndef foo(): pass", "expected_mechanism": "code"},
            {"text": "The quick brown fox jumps over the lazy dog.", "expected_mechanism": "prose"},
        ],
        extractor=code_or_prose_extractor,
        validators=[import_smoke_validator],
        mutable_paths=[],  # this toy domain is read-only
    )
    register_domain(domain)
    print(f"registered: {get_domain('code_or_prose_v1').name}")

    # Run the meta loop — read-only domain, will report STABLE.
    report = run_self_modification(get_domain("code_or_prose_v1"))
    print(f"loop status: {report['status']}")
    print(f"baseline accuracy: {report['baseline']['accuracy']}")


if __name__ == "__main__":
    main()
