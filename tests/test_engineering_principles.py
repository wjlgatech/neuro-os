"""
Deterministic enforcers for the AI-Native Engineering Principles.

Each `[ENFORCED-by-test]` law in
``docs/AI_NATIVE_ENGINEERING_PRINCIPLES.md`` has a corresponding
``test_law_N_*`` here. CI runs them; a violating PR fails the build.

Every test also writes a row to ``versions/principles_runs.jsonl``
(local-only, gitignored). That file is the **measurement layer**: after
N PRs, the data shows which laws fire often (tight) vs never (loose,
likely aspirational and should be re-tagged) vs always-pass-vacuously
(possibly broken enforcers).

Laws covered:
    1. No Raw Knowledge Ingestion
    3. Executable Knowledge
    4. Evaluation Before Acceptance
    5. Deterministic Outputs Over Prompt Vibes
    6. Explicit Failure Paths
    7. Human-In-The-Loop Truth Control
    9. Continuous Refinement With Versioned Justification

Laws 2 (mechanism over description), 8 (minimal primitive set), and 10
(system before content) are tagged ``[ASPIRATIONAL]`` and are not
covered here by design — they are prompt-time-only and would require
an LLM-as-judge to mechanize.

    11. Generated Data Stays Out of the Repo
"""
from __future__ import annotations

import ast
import dataclasses
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pytest
from pydantic import BaseModel


REPO_ROOT = Path(__file__).resolve().parent.parent
MEASUREMENT_LOG = REPO_ROOT / "versions" / "principles_runs.jsonl"


# ---------------------------------------------------------------------------
# Measurement helper — every law-run logs here
# ---------------------------------------------------------------------------


def _log_run(law: int, status: str, violations: List[str], notes: str = "") -> None:
    """Append a run row to ``versions/principles_runs.jsonl``.

    Format: one JSON object per line with the law id, status (pass /
    fail / skip), the list of violations (empty when status=pass), the
    current commit SHA (or 'uncommitted'), and a free-text note. After
    enough runs, this gives data on which laws are tight vs loose.
    """
    MEASUREMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=2,
        ).stdout.strip() or "uncommitted"
    except Exception:
        sha = "unknown"
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "commit": sha,
        "law": law,
        "status": status,
        "violations": violations,
        "notes": notes,
    }
    with MEASUREMENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Law 1 — No Raw Knowledge Ingestion
# ---------------------------------------------------------------------------


def test_law_1_no_raw_ingestion():
    """Every external input under ``agent/founder_loop/`` that reads a
    file or parses JSON must feed the result into a Pydantic
    ``model_validate`` call before that data influences policy or
    persistence.

    Heuristic: walk the AST of each module; collect functions that call
    ``json.loads`` or ``open()`` AND that don't subsequently call
    ``model_validate`` / ``from_jsonl_line`` / equivalent. Flag each
    offender. The list of known exceptions (helper utilities that
    legitimately work with raw bytes) is enumerated below.
    """
    allowed_helpers = {
        # Pure utility modules that legitimately handle raw bytes.
        "_markdown.py",  # markdown-to-HTML, no schema
        "static",  # served directly to clients
    }
    pkg_root = REPO_ROOT / "agent" / "founder_loop"
    violations: List[str] = []
    for py in pkg_root.rglob("*.py"):
        if any(skip in str(py) for skip in allowed_helpers):
            continue
        if "__pycache__" in str(py) or py.name == "__init__.py":
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        # Find json.loads and open() calls; check the same function
        # has model_validate / from_jsonl_line / RawEvent / UrgeEvent
        # somewhere in its body.
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            body_src = ast.unparse(node)
            ingests_external = (
                "json.loads(" in body_src
                or "json.load(" in body_src
                or ".read_text(" in body_src and ".splitlines" in body_src
            )
            validates = (
                "model_validate" in body_src
                or "from_jsonl_line" in body_src
                or "BaseModel" in body_src
                or "RawEvent" in body_src
                or "UrgeEvent" in body_src
                or "Priority" in body_src
                or "Contract" in body_src
                # `read_urges` etc. legitimately wrap their reads in
                # a try/except that builds Pydantic models.
                or "UrgeEvent.model_validate" in body_src
                or node.name.startswith("_")  # private helpers OK
                or node.name in {
                    "load_catalog", "_load_queue", "_format_queue_references",
                    "_serve_chat_shell", "_read_json_body", "_dispatch_get",
                    "_dispatch_post", "render_markdown",
                    # Functions that serialize OUT, not parse IN. The
                    # `json.loads(model_dump_json(...))` idiom is a
                    # round-trip through JSON to get a plain-dict view
                    # of a Pydantic model — not external ingestion.
                    "to_jsonable",
                    # Reads an internal append-only audit log we wrote
                    # ourselves. The WRITE side (append_registry_row)
                    # enforces Law 1 by serializing typed Pydantic
                    # models; the READ side trusts what we wrote.
                    "read_registry",
                }
            )
            if ingests_external and not validates:
                violations.append(
                    f"{py.relative_to(REPO_ROOT)}:{node.lineno}:{node.name} "
                    "ingests external data without Pydantic validation"
                )

    if violations:
        _log_run(1, "fail", violations)
        msg = "Law 1 violations:\n  " + "\n  ".join(violations)
        pytest.fail(msg)
    _log_run(1, "pass", [])


# ---------------------------------------------------------------------------
# Law 3 — Executable Knowledge
# ---------------------------------------------------------------------------


def test_law_3_executable_knowledge():
    """Every ``underlying_need`` in the sublimation catalog must
    have ≥1 ``ConstructiveExpression`` option (code experiment) AND the
    need must be a valid ``UnderlyingNeed`` literal that can be
    diagnosed (mental-practice surface).
    """
    from agent.founder_loop.state import UnderlyingNeed
    catalog = json.loads(
        (REPO_ROOT / "agent" / "founder_loop" / "data" / "sublimation_catalog.json")
        .read_text(encoding="utf-8")
    )
    valid_needs = set(UnderlyingNeed.__args__)  # type: ignore[attr-defined]
    violations: List[str] = []
    needs = catalog.get("needs") or {}
    if not needs:
        violations.append("sublimation_catalog.json has no 'needs' section")
    for need_name, entry in needs.items():
        if need_name not in valid_needs:
            violations.append(
                f"need '{need_name}' is not in UnderlyingNeed enum "
                f"(valid: {sorted(valid_needs)})"
            )
        opts = entry.get("options") or []
        if len(opts) < 1:
            violations.append(
                f"need '{need_name}' has no constructive-expression options"
            )
        for i, opt in enumerate(opts):
            if not opt.get("action"):
                violations.append(
                    f"need '{need_name}' option {i} missing 'action' label"
                )
            if "duration_min" not in opt:
                violations.append(
                    f"need '{need_name}' option {i} missing 'duration_min'"
                )
            if "tank_credit_pct" not in opt:
                violations.append(
                    f"need '{need_name}' option {i} missing 'tank_credit_pct'"
                )
    if violations:
        _log_run(3, "fail", violations)
        pytest.fail("Law 3 violations:\n  " + "\n  ".join(violations))
    _log_run(3, "pass", [])


# ---------------------------------------------------------------------------
# Law 4 — Evaluation Before Acceptance
# ---------------------------------------------------------------------------


def test_law_4_evaluation_rubric():
    """Assert the golden-case gate is wired into the L1 + L2 loops AND
    the safety-law harness exists for the product layer."""
    violations: List[str] = []
    # L1 golden gate
    adoptions = REPO_ROOT / "tests" / "test_adoptions.py"
    if not adoptions.exists():
        violations.append("missing tests/test_adoptions.py (L1 golden gate)")
    elif "TestGoldenGate" not in adoptions.read_text(encoding="utf-8"):
        violations.append("tests/test_adoptions.py lacks TestGoldenGate class")
    # L2 patch validation
    selfmod = REPO_ROOT / "tests" / "test_self_modification.py"
    if not selfmod.exists():
        violations.append("missing tests/test_self_modification.py (L2 patch gate)")
    # Product-layer safety
    safety = REPO_ROOT / "tests" / "test_founder_loop_safety.py"
    if not safety.exists():
        violations.append("missing tests/test_founder_loop_safety.py (product safety)")
    # Catalog of golden cases for the product layer
    goldens = REPO_ROOT / "agent" / "founder_loop" / "golden_cases.py"
    if not goldens.exists():
        violations.append("missing agent/founder_loop/golden_cases.py")
    if violations:
        _log_run(4, "fail", violations)
        pytest.fail("Law 4 violations:\n  " + "\n  ".join(violations))
    _log_run(4, "pass", [])


# ---------------------------------------------------------------------------
# Law 5 — Deterministic Outputs Over Prompt Vibes
# ---------------------------------------------------------------------------


def test_law_5_deterministic_outputs():
    """Every public class exported from ``agent.founder_loop`` MUST be
    either a Pydantic ``BaseModel`` or a frozen dataclass.

    Free-text dicts and mutable dataclasses are forbidden in the public
    API surface — they make output shape implicit.
    """
    import agent.founder_loop as fl
    violations: List[str] = []
    # Names exported in __all__ that point at classes (skip functions).
    for name in fl.__all__:
        obj = getattr(fl, name, None)
        if obj is None or not isinstance(obj, type):
            continue
        # Allow concrete enums / frozen sets / Literal aliases that
        # aren't classes-with-state. Class check above rules out most.
        is_pydantic = isinstance(obj, type) and issubclass(obj, BaseModel) if hasattr(obj, "__bases__") else False
        is_frozen_dc = (
            dataclasses.is_dataclass(obj)
            and getattr(obj, "__dataclass_params__", None) is not None
            and obj.__dataclass_params__.frozen  # type: ignore[union-attr]
        )
        # Standalone classes that aren't either are flagged.
        # Exception: FounderLoop is an orchestrator class, not a data class.
        if name == "FounderLoop":
            continue
        if not (is_pydantic or is_frozen_dc):
            violations.append(
                f"{name}: exported class is neither pydantic.BaseModel "
                "nor a frozen dataclass"
            )
    if violations:
        _log_run(5, "fail", violations)
        pytest.fail("Law 5 violations:\n  " + "\n  ".join(violations))
    _log_run(5, "pass", [])


# ---------------------------------------------------------------------------
# Law 6 — Explicit Failure Paths
# ---------------------------------------------------------------------------


def test_law_6_every_controlop_has_inverse_or_is_terminal():
    """Every ``ControlOp`` in the enum must have an entry in
    ``policy._inverse()`` OR be in the documented set of terminal ops
    (continue, rest, escalate_to_human, replan, unlock_entertainment,
    notify_ration_used) which intentionally do not auto-revert.
    """
    from agent.founder_loop.state import ControlOp
    from agent.founder_loop.policy import _inverse
    terminal_ops = {
        "continue",
        "rest",
        "escalate_to_human",
        "replan",
        "unlock_entertainment",
        "notify_ration_used",
    }
    violations: List[str] = []
    for op in ControlOp.__args__:  # type: ignore[attr-defined]
        if op in terminal_ops:
            continue
        inv = _inverse(op)
        if inv is None:
            violations.append(
                f"ControlOp '{op}' has no _inverse() mapping and is not in "
                f"the terminal-ops allowlist"
            )
    if violations:
        _log_run(6, "fail", violations)
        pytest.fail("Law 6 violations:\n  " + "\n  ".join(violations))
    _log_run(6, "pass", [])


def test_law_6_urge_log_rate_limit():
    """The user-logged urge surface must reject after the daily cap to
    satisfy the 'rejection rule' arm of Law 6. Default cap is 5/day."""
    from agent.founder_loop.urge_log import log_urge_event, RateLimitExceeded
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "events.jsonl"
        # The first 5 succeed.
        for i in range(5):
            log_urge_event(
                urge_type="entertainment",
                context=f"test {i}",
                path=path,
            )
        # The 6th must raise.
        with pytest.raises(RateLimitExceeded):
            log_urge_event(
                urge_type="entertainment",
                context="overflow",
                path=path,
            )
    _log_run(6, "pass", [], notes="urge rate-limit gate fired correctly")


# ---------------------------------------------------------------------------
# Law 7 — Human-In-The-Loop Truth Control
# ---------------------------------------------------------------------------


def test_law_7_founder_loop_domain_is_read_only_l2():
    """The founder_loop domain ships with ``mutable_paths=[]`` (read-only
    L2 in v0). When this graduates to v1 with a /catalog-review chat
    surface, this test should be updated explicitly — it should NOT
    silently start passing with a non-empty allowlist.
    """
    from agent.founder_loop.domain import register_founder_loop_domain
    domain = register_founder_loop_domain()
    if list(domain.mutable_paths) != []:
        _log_run(
            7, "fail",
            [f"founder_loop domain mutable_paths is {domain.mutable_paths!r}; "
             f"expected [] until /catalog-review surface ships"],
        )
        pytest.fail(
            f"Law 7: founder_loop mutable_paths must remain [] in v0; "
            f"got {domain.mutable_paths!r}. To graduate, update this test "
            f"AND add the /catalog-review chat surface (see roadmap LATER)."
        )
    _log_run(7, "pass", [])


def test_law_7_auto_apply_default_is_continue_only():
    """The default auto-apply allowlist must be ``{'continue'}``. Other
    ops require explicit per-user graduation via ``graduated_auto_apply``."""
    from agent.founder_loop.state import AUTO_APPLY_DEFAULT
    if AUTO_APPLY_DEFAULT != {"continue"}:
        _log_run(
            7, "fail",
            [f"AUTO_APPLY_DEFAULT is {AUTO_APPLY_DEFAULT!r}; expected {{'continue'}}"],
        )
        pytest.fail(
            f"Law 7: AUTO_APPLY_DEFAULT must be exactly {{'continue'}}; "
            f"got {AUTO_APPLY_DEFAULT!r}."
        )
    _log_run(7, "pass", [])


# ---------------------------------------------------------------------------
# Law 9 — Continuous Refinement With Versioned Justification
# ---------------------------------------------------------------------------


_REQUIRED_SECTIONS = ("What changed", "Why it changed", "Validation")
_TRIVIAL_PREFIXES = (
    "Merge ",
    "Initial commit",
    "Bump ",
    "Release ",
    "Revert ",
    "Add .gitignore",
    "Update README",  # cosmetic-only README edits exempted (in spirit)
)


def _last_n_commit_messages(n: int = 5) -> List[Dict[str, str]]:
    """Return up to N commit messages on the current branch since
    diverging from main. If we're on main itself, returns the last N
    commits from main."""
    try:
        # Find the merge-base with main; if we're on main, use HEAD~N.
        mb = subprocess.run(
            ["git", "merge-base", "HEAD", "main"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        if mb:
            range_arg = f"{mb}..HEAD"
        else:
            range_arg = f"HEAD~{n}..HEAD"
        result = subprocess.run(
            ["git", "log", range_arg, "--format=%H%n%s%n%b%x00", f"-n{n}"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=4,
        )
        out: List[Dict[str, str]] = []
        for chunk in result.stdout.split("\x00"):
            chunk = chunk.strip()
            if not chunk:
                continue
            lines = chunk.split("\n", 2)
            if len(lines) < 2:
                continue
            sha = lines[0]
            subject = lines[1]
            body = lines[2] if len(lines) >= 3 else ""
            out.append({"sha": sha, "subject": subject, "body": body})
        return out
    except Exception:
        return []


def test_law_9_recent_commit_messages_have_required_sections():
    """The last 5 non-trivial commits since main must each contain
    'What changed', 'Why it changed', and 'Validation' sections.

    This is a SOFT enforcer: it warns when missing sections accumulate
    rather than blocking the commit (the pre-commit hook does the
    blocking on individual commits). Here we surface trends.
    """
    commits = _last_n_commit_messages(n=5)
    if not commits:
        # Fresh repo or no commits ahead of main → nothing to check.
        _log_run(9, "skip", [], notes="no commits ahead of main")
        pytest.skip("no commits ahead of main to check")
        return

    violations: List[str] = []
    checked = 0
    for c in commits:
        if c["subject"].startswith(_TRIVIAL_PREFIXES):
            continue
        checked += 1
        full_msg = f"{c['subject']}\n{c['body']}"
        missing = [s for s in _REQUIRED_SECTIONS if s.lower() not in full_msg.lower()]
        if missing:
            violations.append(
                f"{c['sha'][:8]} '{c['subject'][:60]}': missing sections "
                f"{missing}"
            )
    if checked == 0:
        _log_run(9, "skip", [], notes="all recent commits are trivial-prefixed")
        pytest.skip("no non-trivial commits to check")
        return

    if violations:
        _log_run(9, "fail", violations)
        # Soft fail: emit a clear warning, still pass the test for now.
        # Once the hook is in place and adopted, switch to hard fail by
        # changing pytest.warns → pytest.fail.
        msg = (
            "Law 9 (soft) — recent commit messages missing the required "
            "What/Why/Validation sections:\n  " + "\n  ".join(violations)
            + "\n\nThis is currently a SOFT enforcer (logs to "
            "versions/principles_runs.jsonl, doesn't block CI). The "
            "pre-commit hook in .pre-commit-config.yaml is the hard "
            "gate at commit time. Switch this test to hard-fail once "
            "the hook is adopted across all contributors."
        )
        # Use pytest's warnings system for soft signal.
        import warnings
        warnings.warn(msg, stacklevel=2)
        return
    _log_run(9, "pass", [], notes=f"checked {checked} commits")


def test_law_11_no_generated_data_in_repo():
    """Law 11 — Generated data must not live inside the repo tree.

    Checks that no .jsonl, .db, .db-journal, .db-shm, or .db-wal files
    exist under agent/ or the repo root (outside tests/fixtures/ which
    holds deterministic, version-controlled test data).
    """
    forbidden_suffixes = {".jsonl", ".db", ".db-journal", ".db-shm", ".db-wal"}
    # tests/fixtures/ — deterministic, version-controlled test data.
    # versions/       — test-harness measurement log (already gitignored).
    allowed_prefixes = (
        REPO_ROOT / "tests" / "fixtures",
        REPO_ROOT / "versions",
    )

    violations: List[str] = []
    for suffix in forbidden_suffixes:
        for path in REPO_ROOT.rglob(f"*{suffix}"):
            if any(path.is_relative_to(p) for p in allowed_prefixes):
                continue
            # Skip hidden dirs (.git, .ruff_cache, etc.)
            if any(part.startswith(".") for part in path.parts):
                continue
            violations.append(str(path.relative_to(REPO_ROOT)))

    if violations:
        _log_run(11, "fail", violations)
        pytest.fail(
            "Law 11: generated data found inside the repo tree.\n"
            "Move these files to ~/.neuro_os_*/ and add the pattern to .gitignore:\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    _log_run(11, "pass", [], notes=f"scanned {REPO_ROOT}")
