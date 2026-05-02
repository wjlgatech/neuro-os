"""Sandbox runner for Neuro-OS self-modification.

Creates isolated sandboxes, applies bounded changes, runs validation commands,
and can promote validated files back to production.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class SandboxResult:
    sandbox_path: str
    success: bool
    returncode: int
    stdout: str
    stderr: str
    metrics: Dict[str, Any]


def utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_sandbox(root: str = ".", sandbox_root: str = "sandbox") -> Path:
    root_path = Path(root).resolve()
    sandbox_path = root_path / sandbox_root / f"run_{utc_id()}"
    sandbox_path.mkdir(parents=True, exist_ok=True)

    for name in ["agent", "tests", "evals", "docs"]:
        src = root_path / name
        if src.exists():
            shutil.copytree(src, sandbox_path / name)

    return sandbox_path


def apply_bounded_change(sandbox_path: Path, change: Dict[str, Any]) -> List[str]:
    """Apply an allowlisted change to a sandbox only.

    Returns changed file paths relative to sandbox root.
    """
    change_id = change.get("change_id", "")
    changed: List[str] = []

    if change_id == "prioritize_reward_prediction_error":
        target = sandbox_path / "agent" / "ingestion_pipeline.py"
        text = target.read_text(encoding="utf-8")
        old = "if any(k in text for k in [\"dopamine\", \"reward\", \"td error\", \"reinforcement\", \"q-learning\"]):"
        if old not in text:
            raise ValueError("Expected reward-priority rule not found; refusing unsafe mutation")
        # Safe idempotent marker-only change: documents that the rule is already enforced.
        marker = "# SELF_EVOLUTION: reward prediction error cues are prioritized before generic prediction error cues.\n"
        if marker not in text:
            text = text.replace("def extract_mechanism_offline(source_text: str, source_url: str = \"\") -> ExtractedKnowledge:\n", marker + "def extract_mechanism_offline(source_text: str, source_url: str = \"\") -> ExtractedKnowledge:\n")
            target.write_text(text, encoding="utf-8")
            changed.append("agent/ingestion_pipeline.py")
    elif change_id.startswith("strengthen_"):
        target = sandbox_path / "docs" / "TRUE_RUBRIC.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        prior = target.read_text(encoding="utf-8") if target.exists() else "# TRUE Rubric\n\n"
        addition = f"\n## Auto-proposed refinement: {change_id}\n\nReason: {change.get('reason', 'No reason provided')}\nAction: {change.get('action', 'No action provided')}\nRisk: {change.get('risk', 'No risk recorded')}\n"
        if addition not in prior:
            target.write_text(prior + addition, encoding="utf-8")
            changed.append("docs/TRUE_RUBRIC.md")
    else:
        raise ValueError(f"Change is not allowlisted for sandbox application: {change_id}")

    return changed


def run_validation(sandbox_path: Path, command: Optional[List[str]] = None) -> SandboxResult:
    command = command or ["python", "-m", "unittest", "discover", "-s", "tests"]
    completed = subprocess.run(command, cwd=sandbox_path, capture_output=True, text=True)

    metrics = {
        "command": command,
        "success": completed.returncode == 0,
        "returncode": completed.returncode,
    }

    return SandboxResult(
        sandbox_path=str(sandbox_path),
        success=completed.returncode == 0,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        metrics=metrics,
    )


def promote_files(sandbox_path: Path, changed_files: Iterable[str], root: str = ".") -> List[str]:
    root_path = Path(root).resolve()
    promoted: List[str] = []
    for rel in changed_files:
        src = sandbox_path / rel
        dst = root_path / rel
        if not src.exists():
            raise FileNotFoundError(f"Sandbox file missing: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        promoted.append(rel)
    return promoted


def write_sandbox_report(sandbox_path: Path, report: Dict[str, Any]) -> Path:
    out = sandbox_path / "sandbox_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    path = create_sandbox()
    result = run_validation(path)
    print(json.dumps(asdict(result), indent=2))
