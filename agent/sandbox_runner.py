"""
Sandbox Runner.

Creates an isolated copy of the ``agent/`` directory under a temp dir,
applies a user-provided change callback, and runs validators against the
sandbox copy. Validators are plain callables that take the sandbox path
and return ``{"name": str, "success": bool, ...}``; ``run_validation``
aggregates them.

The default validator imports the sandboxed ``agent/`` modules to catch
syntax errors and broken imports — a real smoke test, not a hardcoded
``True``.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional

Validator = Callable[[str], Dict[str, Any]]


def create_sandbox() -> str:
    """Create a sandbox dir containing a fresh copy of ``agent/``."""
    sandbox_dir = tempfile.mkdtemp(prefix="neuro_os_sandbox_")
    source_dir = os.path.dirname(__file__)
    target_dir = os.path.join(sandbox_dir, "agent")
    shutil.copytree(source_dir, target_dir)
    return sandbox_dir


def apply_bounded_change(
    sandbox_path: str, change_callback: Callable[[str], None]
) -> None:
    """Run ``change_callback(agent_dir)`` against the sandbox's agent copy."""
    agent_dir = os.path.join(sandbox_path, "agent")
    change_callback(agent_dir)


# Modules that are known to be broken or scaffolds in this repo and are
# not part of the documented self-evolving loop. They are intentionally
# excluded from the sandbox import smoke test so unrelated rot does not
# cause the loop to report failure.
_SMOKE_TEST_SKIP = frozenset(
    {
        "true_runtime.py",          # literal placeholder text
        "multi_agent_orchestrator.py",  # legacy: imports without agent prefix
        "self_modification_controller.py",  # legacy: stale sandbox API
    }
)


def _import_smoke_test(sandbox_path: str) -> Dict[str, Any]:
    """Import every loop-relevant ``agent/*.py`` module in a fresh subprocess.

    Running in a subprocess ensures the sandbox copy is loaded with real
    package machinery (so ``from agent.X import Y`` resolves correctly and
    ``from __future__ import annotations`` is handled by the import system,
    not by ``importlib.util.spec_from_file_location``).
    """
    agent_dir = os.path.join(sandbox_path, "agent")
    files = sorted(
        f
        for f in os.listdir(agent_dir)
        if f.endswith(".py") and not f.startswith("_") and f not in _SMOKE_TEST_SKIP
    )
    script = (
        "import json, sys\n"
        f"sys.path.insert(0, {sandbox_path!r})\n"
        f"files = {files!r}\n"
        "results = {'imported': [], 'failures': []}\n"
        "for fname in files:\n"
        "    mod_name = 'agent.' + fname[:-3]\n"
        "    try:\n"
        "        __import__(mod_name)\n"
        "        results['imported'].append(fname)\n"
        "    except Exception as exc:\n"
        "        results['failures'].append({'file': fname, "
        "'error': f'{type(exc).__name__}: {exc}'})\n"
        "print(json.dumps(results))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return {
            "name": "import_smoke_test",
            "success": False,
            "imported": [],
            "failures": [{"file": "<runner>", "error": proc.stderr.strip() or "no output"}],
        }
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    return {
        "name": "import_smoke_test",
        "success": not payload["failures"],
        "imported": payload["imported"],
        "failures": payload["failures"],
    }


def run_validation(
    sandbox_path: str,
    validators: Optional[List[Validator]] = None,
) -> Dict[str, Any]:
    """Run validators against the sandbox; aggregate to a single result."""
    if validators is None:
        validators = [_import_smoke_test]
    results = [v(sandbox_path) for v in validators]
    return {
        "success": all(r.get("success") for r in results),
        "validators": results,
    }


def promote_files(sandbox_path: str, changed_files: Dict[str, Any]) -> Dict[str, Any]:
    """Copy specified files from the sandbox back into ``agent/``.

    ``changed_files`` is ``{relative_path: True}`` (only truthy values are
    promoted). Returns a summary describing which files were copied.
    """
    repo_agent_dir = os.path.dirname(__file__)
    sandbox_agent_dir = os.path.join(sandbox_path, "agent")
    promoted: List[str] = []
    skipped: List[str] = []
    for rel_path, flag in (changed_files or {}).items():
        if not flag:
            skipped.append(rel_path)
            continue
        src = os.path.join(sandbox_agent_dir, rel_path)
        dst = os.path.join(repo_agent_dir, rel_path)
        if not os.path.isfile(src):
            skipped.append(rel_path)
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        promoted.append(rel_path)
    return {"promoted": promoted, "skipped": skipped}


def cleanup_sandbox(sandbox_path: str) -> None:
    """Remove the sandbox directory."""
    shutil.rmtree(sandbox_path, ignore_errors=True)


__all__ = [
    "create_sandbox",
    "apply_bounded_change",
    "run_validation",
    "promote_files",
    "cleanup_sandbox",
]
