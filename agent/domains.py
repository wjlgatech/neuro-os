"""
Neuro-OS domains, registered on top of flywheel-loop's substrate.

The ``Domain`` dataclass and registry come from ``flywheel_loop.domains``.
This module:

* re-exports ``Domain`` / ``register_domain`` / ``get_domain`` /
  ``list_domains`` so existing callers don't break,
* defines the neuro-os-specific validators (``import_smoke_validator``,
  ``golden_accuracy_validator``, ``pytest_validator``) that know about
  ``agent.ingestion_pipeline`` and ``GOLDEN_CASES``,
* registers ``neuroscience_v1`` (read-only) and ``neuro_os_self_v1``
  (mutable: ``priority_rules.json``).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

# Substrate API.
from flywheel_loop.domains import (
    Domain,
    Extractor,
    Validator,
    get_domain,
    list_domains,
    register_domain,
)

from agent.ingestion_pipeline import _canonical_ontology, run_pipeline
from agent.patches import PRIORITY_RULES_RELATIVE
from agent.sandbox_runner import run_validation as _agent_run_validation
from agent.self_evolution_controller import GOLDEN_CASES


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def import_smoke_validator(sandbox_path: str) -> Dict[str, Any]:
    """Re-export the import smoke test from sandbox_runner."""
    result = _agent_run_validation(sandbox_path)
    inner = result["validators"][0]
    return {
        "name": inner.get("name", "import_smoke_test"),
        "success": result["success"],
        "imported": inner.get("imported", []),
        "failures": inner.get("failures", []),
    }


def golden_accuracy_validator(sandbox_path: str) -> Dict[str, Any]:
    """Run GOLDEN_CASES through the sandbox copy of the pipeline.

    Uses a subprocess so the sandbox's ``priority_rules.json`` is read
    by a fresh import of ``agent.ingestion_pipeline``.
    """
    cases_json = json.dumps(GOLDEN_CASES)
    script = (
        "import json, sys\n"
        f"sys.path.insert(0, {sandbox_path!r})\n"
        f"cases = json.loads({cases_json!r})\n"
        "from agent.ingestion_pipeline import run_pipeline\n"
        "results = []\n"
        "for case in cases:\n"
        "    r = run_pipeline(case['text'])\n"
        "    results.append({\n"
        "        'expected': case['expected_mechanism'],\n"
        "        'actual': r['knowledge'].get('mechanism'),\n"
        "        'decision': r.get('decision'),\n"
        "    })\n"
        "correct = sum(1 for r in results if r['expected'] == r['actual'])\n"
        "accepted = sum(1 for r in results if r['decision'] == 'ACCEPT')\n"
        "print(json.dumps({\n"
        "    'accuracy': correct / len(results) if results else 1.0,\n"
        "    'accept_rate': accepted / len(results) if results else 1.0,\n"
        "    'errors': [r for r in results if r['expected'] != r['actual']],\n"
        "}))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return {
            "name": "golden_accuracy",
            "success": False,
            "accuracy": 0.0,
            "errors": [{"runner_error": proc.stderr.strip() or "no output"}],
        }
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    return {
        "name": "golden_accuracy",
        "success": payload["accuracy"] >= 1.0,
        "accuracy": payload["accuracy"],
        "accept_rate": payload["accept_rate"],
        "errors": payload["errors"],
    }


def pytest_validator(sandbox_path: str) -> Dict[str, Any]:
    """Run the sandboxed pytest suite (heavy; opt-in)."""
    sandbox_root = Path(sandbox_path)
    repo_root = Path(__file__).resolve().parent.parent
    tests_target = sandbox_root / "tests"
    if not tests_target.exists():
        import shutil

        shutil.copytree(repo_root / "tests", tests_target)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
        cwd=sandbox_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "name": "pytest",
        "success": proc.returncode == 0,
        "stdout_tail": proc.stdout.splitlines()[-5:] if proc.stdout else [],
        "returncode": proc.returncode,
    }


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------


def _neuroscience_extractor(text: str) -> Dict[str, Any]:
    return run_pipeline(text, _canonical_ontology())


# ---------------------------------------------------------------------------
# Default domains (registered idempotently)
# ---------------------------------------------------------------------------


def _ensure_registered(domain: Domain) -> None:
    if domain.name not in list_domains():
        register_domain(domain)


_NEUROSCIENCE_V1 = Domain(
    name="neuroscience_v1",
    ontology=_canonical_ontology(),
    golden_cases=list(GOLDEN_CASES),
    extractor=_neuroscience_extractor,
    validators=[import_smoke_validator, golden_accuracy_validator],
    mutable_paths=[],
)


_NEURO_OS_SELF_V1 = Domain(
    name="neuro_os_self_v1",
    ontology=_canonical_ontology(),
    golden_cases=list(GOLDEN_CASES),
    extractor=_neuroscience_extractor,
    validators=[import_smoke_validator, golden_accuracy_validator],
    mutable_paths=[PRIORITY_RULES_RELATIVE],
)


_ensure_registered(_NEUROSCIENCE_V1)
_ensure_registered(_NEURO_OS_SELF_V1)


__all__ = [
    "Domain",
    "Extractor",
    "Validator",
    "register_domain",
    "get_domain",
    "list_domains",
    "import_smoke_validator",
    "golden_accuracy_validator",
    "pytest_validator",
]
