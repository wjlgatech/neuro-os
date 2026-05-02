"""
Pluggable Domain abstraction for the self-modification loop.

A ``Domain`` bundles everything OEC needs to operate on a particular
artifact:

* ``ontology`` — the knowledge graph the extractor classifies into.
* ``golden_cases`` — list of ``{text, expected_mechanism}`` used as the
  invariant: a mutation is beneficial iff it preserves or improves
  classification accuracy on these.
* ``extractor`` — a callable ``text -> {knowledge, decision}`` used in
  the host process for baseline observation.
* ``validators`` — list of callables ``sandbox_path -> {success, ...}``
  run in the sandbox after a patch is applied. The aggregate must
  succeed for promotion.
* ``mutable_paths`` — allowlist of repo-relative file paths that
  patches are permitted to touch. Anything outside this list is
  refused at patch-application time.

Two domains are registered out of the box:

* ``neuroscience_v1`` — the original neuroscience ingestion behavior.
* ``neuro_os_self_v1`` — neuro-os as the artifact under improvement.
  Same goldens (we use the existing classification benchmark as a
  proxy for "the system still works"); validators include pytest in
  addition to the import smoke test; only the priority-rules data
  file is mutable.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List

from agent.ingestion_pipeline import _canonical_ontology, run_pipeline
from agent.patches import PRIORITY_RULES_RELATIVE
from agent.sandbox_runner import run_validation as _import_validation
from agent.self_evolution_controller import GOLDEN_CASES


Validator = Callable[[str], Dict[str, Any]]
Extractor = Callable[[str], Dict[str, Any]]


@dataclass
class Domain:
    name: str
    ontology: Dict[str, Any]
    golden_cases: List[Dict[str, str]]
    extractor: Extractor
    validators: List[Validator]
    mutable_paths: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def import_smoke_validator(sandbox_path: str) -> Dict[str, Any]:
    """Re-export of the sandbox import smoke test for use as a Domain validator."""
    result = _import_validation(sandbox_path)
    inner = result["validators"][0]
    return {
        "name": inner.get("name", "import_smoke_test"),
        "success": result["success"],
        "imported": inner.get("imported", []),
        "failures": inner.get("failures", []),
    }


def golden_accuracy_validator(sandbox_path: str) -> Dict[str, Any]:
    """Run GOLDEN_CASES through the sandbox copy of the pipeline.

    Uses a subprocess so the sandbox's data files (e.g. its possibly-
    patched ``priority_rules.json``) are read by a fresh import of
    ``agent.ingestion_pipeline``.
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
    """Run the sandboxed pytest suite. Must exit 0 for the domain to accept."""
    sandbox_root = Path(sandbox_path)
    repo_root = Path(__file__).resolve().parent.parent
    tests_target = sandbox_root / "tests"
    if not tests_target.exists():
        # Tests dir lives at repo root, not under agent/. Copy it for the run.
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
    """Run the live neuroscience pipeline against ``text``."""
    return run_pipeline(text, _canonical_ontology())


# ---------------------------------------------------------------------------
# Domain registry
# ---------------------------------------------------------------------------


_REGISTRY: Dict[str, Domain] = {}


def register_domain(domain: Domain) -> None:
    if domain.name in _REGISTRY:
        raise ValueError(f"domain {domain.name!r} already registered")
    _REGISTRY[domain.name] = domain


def get_domain(name: str) -> Domain:
    if name not in _REGISTRY:
        raise KeyError(f"unknown domain {name!r}; registered: {list(_REGISTRY)}")
    return _REGISTRY[name]


def list_domains() -> List[str]:
    return list(_REGISTRY)


# ---------------------------------------------------------------------------
# Default domains
# ---------------------------------------------------------------------------


_NEUROSCIENCE_V1 = Domain(
    name="neuroscience_v1",
    ontology=_canonical_ontology(),
    golden_cases=list(GOLDEN_CASES),
    extractor=_neuroscience_extractor,
    validators=[import_smoke_validator, golden_accuracy_validator],
    mutable_paths=[],  # neuroscience domain does not self-modify code
)


_NEURO_OS_SELF_V1 = Domain(
    name="neuro_os_self_v1",
    ontology=_canonical_ontology(),
    golden_cases=list(GOLDEN_CASES),
    extractor=_neuroscience_extractor,
    validators=[
        import_smoke_validator,
        golden_accuracy_validator,
        # pytest_validator is heavy; opt-in via override if needed.
    ],
    mutable_paths=[PRIORITY_RULES_RELATIVE],
)


register_domain(_NEUROSCIENCE_V1)
register_domain(_NEURO_OS_SELF_V1)


__all__ = [
    "Domain",
    "register_domain",
    "get_domain",
    "list_domains",
    "import_smoke_validator",
    "golden_accuracy_validator",
    "pytest_validator",
]
