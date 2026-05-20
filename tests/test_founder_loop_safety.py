"""
The six safety laws — pinned to tests.

If any of these fail, the loop's *trustworthiness* is broken even if the
behavior tests pass. Run as part of CI on every change.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent.founder_loop import FounderLoop
from agent.founder_loop.contract import check_contract
from agent.founder_loop.memory import append_registry_row, read_registry
from agent.founder_loop.predict import reset_predict_fn
from agent.founder_loop.state import (
    AUTO_APPLY_DEFAULT,
    AUTO_APPLY_GRADUATABLE,
    Contract,
    ContractCheck,
    ControlAction,
    ControlOp,
    ForecastedState,
    FounderState,
    Priority as PriorityT,
    TankState,
)


@pytest.fixture(autouse=True)
def _clean_predictor():
    yield
    reset_predict_fn()


@pytest.fixture
def loop_with_24_rows(tmp_path):
    """A loop pre-populated with 24h of synthetic registry rows."""
    fixture = tmp_path / "fixture.jsonl"
    fixture.write_text("", encoding="utf-8")
    base = datetime(2026, 5, 5, 0, tzinfo=timezone.utc)
    for h in range(24):
        ts = base + timedelta(hours=h)
        append_registry_row(
            tmp_path / "registry.jsonl",
            state=FounderState(
                timestamp=ts,
                distraction_minutes_last_hour=10.0 + (h % 6),
                deep_work_minutes_last_hour=20.0 + (h % 4),
                context_switches_last_hour=h % 5,
            ),
            forecasted=ForecastedState(
                predicted_distraction_min=12.0,
                predicted_deep_work_min=22.0,
                predicted_urge="none",
                predicted_underlying_need="none",
                confidence="medium",
                reasoning="synthetic",
            ),
            tank=TankState(
                percent=50.0, credits_today=50, debits_today=0,
                threshold=90, ration_remaining_min=60,
                status="below_threshold",
            ),
            action=ControlAction(
                op="continue", rationale="x",
                contract_check=ContractCheck(honored=True),
            ),
        )
    loop = FounderLoop(
        registry_path=tmp_path / "registry.jsonl",
        contract_path=tmp_path / "contracts.jsonl",
        workflowx_export_path=fixture,
    )
    return loop, tmp_path


# ---------------------------------------------------------------------------
# Law 1 — Observability
# ---------------------------------------------------------------------------


def test_law1_observability_24h_from_registry_alone(loop_with_24_rows):
    loop, tmp_path = loop_with_24_rows
    rows = read_registry(loop.registry_path)
    assert len(rows) >= 24, "24h of ticks must produce ≥24 registry rows"
    # Every row carries enough fields to render the day's state alone.
    for r in rows:
        assert "state" in r and "timestamp" in r["state"]
        assert "action" in r and "op" in r["action"]


# ---------------------------------------------------------------------------
# Law 2 — Evaluability
# ---------------------------------------------------------------------------


def test_law2_evaluability_predicted_and_actual_in_every_row(loop_with_24_rows):
    loop, _ = loop_with_24_rows
    rows = read_registry(loop.registry_path)
    for r in rows:
        assert "forecasted" in r and "predicted_distraction_min" in r["forecasted"]
        assert "state" in r and "distraction_minutes_last_hour" in r["state"]
        # Error is computable
        err = abs(
            float(r["forecasted"]["predicted_distraction_min"])
            - float(r["state"]["distraction_minutes_last_hour"])
        )
        assert err >= 0.0


# ---------------------------------------------------------------------------
# Law 3 — Controllability
# ---------------------------------------------------------------------------


def test_law3_controllability_only_allowed_ops_emitted():
    """Every ControlAction op must be in the closed vocabulary."""
    allowed = set(ControlOp.__args__)  # type: ignore[attr-defined]
    # Every default-applied op must be in the allowed set.
    for op in AUTO_APPLY_DEFAULT:
        assert op in allowed
    for op in AUTO_APPLY_GRADUATABLE:
        assert op in allowed
    # Constructing an unknown op should fail at the type system.
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        ControlAction(op="meditate", rationale="x",
                      contract_check=ContractCheck(honored=True))


# ---------------------------------------------------------------------------
# Law 4 — Stability
# ---------------------------------------------------------------------------


def test_law4_stability_promoted_patches_have_inverse_op():
    """Auto-apply-graduatable ops carry an inverse_op for reversibility."""
    from agent.founder_loop.policy import _inverse
    for op in AUTO_APPLY_GRADUATABLE:
        inv = _inverse(op)
        assert inv is not None, f"graduatable op {op} has no inverse"


# ---------------------------------------------------------------------------
# Law 5 — Bounded action
# ---------------------------------------------------------------------------


def test_law5_bounded_action_sublimation_catalog_path_allowlist():
    """The catalog file lives at the path the v0 loop expects.

    v0 ships ``mutable_paths=[]`` — the L2 self-modification loop does
    not write here. v1 will flip ``mutable_paths`` to include this path
    and only this path.
    """
    expected = Path(__file__).resolve().parent.parent / "agent/founder_loop/data/sublimation_catalog.json"
    assert expected.exists(), f"catalog must live at {expected}"
    queues_dir = expected.parent / "queues"
    assert queues_dir.is_dir(), f"queues dir must exist at {queues_dir}"
    # All queues are JSON
    for f in queues_dir.iterdir():
        if f.suffix == ".json":
            json.loads(f.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Law 6 — Contract integrity (the new philosophy invariant)
# ---------------------------------------------------------------------------


def test_law6_contract_integrity_unlock_below_threshold_violates():
    """Trying to unlock entertainment with tank below threshold must
    produce a ``threshold_violation`` (not a silent allow, not a hard
    deny). The action still runs but the violation is logged.
    """
    p = PriorityT(title="x", evidence_type="commit_pushed",
                  evidence_target="1_commit", weight=1)
    c = Contract(date="2026-05-05", priorities=[p],
                 entertainment_ration_min=60,
                 signed_at=datetime.now(timezone.utc))
    tank = TankState(percent=10, credits_today=10, debits_today=0,
                     threshold=90, ration_remaining_min=60,
                     status="below_threshold")
    check = check_contract("unlock_entertainment", {"duration_min": 30},
                           contract=c, tank=tank)
    assert check.honored is False
    assert check.violation_type == "threshold_violation"


def test_law6_block_url_must_be_pre_authorized():
    """block_url ops for non-pre-authorized targets are violations.

    Honors the philosophy: yesterday-self pre-authorizes specific blocks;
    today-self can override but the override is logged.
    """
    p = PriorityT(title="x", evidence_type="commit_pushed",
                  evidence_target="1_commit", weight=1)
    c = Contract(date="2026-05-05", priorities=[p],
                 entertainment_ration_min=60,
                 pre_authorized_blocks=["youtube.com"],
                 signed_at=datetime.now(timezone.utc))
    tank = TankState(percent=95, credits_today=95, debits_today=0,
                     threshold=90, ration_remaining_min=60,
                     status="threshold_within_ration")
    # Authorized → honored
    check_ok = check_contract("block_url", {"target": "https://youtube.com/watch"},
                              contract=c, tank=tank)
    assert check_ok.honored is True
    # Not authorized → violation
    check_no = check_contract("block_url", {"target": "https://reddit.com"},
                              contract=c, tank=tank)
    assert check_no.honored is False
    assert check_no.violation_type == "block_target_not_authorized"


def test_law6_every_action_carries_contract_check_field():
    """Schema invariant: ``ControlAction.contract_check`` is required."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        ControlAction(op="continue", rationale="x")


# ---------------------------------------------------------------------------
# Law 7 — Cross-origin protection (daemon HTTP boundary)
#
# Loopback binding (127.0.0.1) alone does NOT defend against a browser
# script on attacker.com calling fetch('http://127.0.0.1:8765/...'). The
# browser still delivers the request; only a strict same-origin / Origin
# allowlist plus the Sec-Fetch-Site signal stops the read AND the CSRF
# mutation. These tests pin that defense — break them and the daemon's
# "loopback is the boundary" claim becomes false.
# ---------------------------------------------------------------------------


@pytest.fixture
def running_daemon(tmp_path):
    """Spin up a real FounderLoop daemon on a random port for HTTP tests."""
    import time

    from urllib.request import Request, urlopen

    from agent.founder_loop.server import serve

    registry = tmp_path / "registry.jsonl"
    registry.write_text("", encoding="utf-8")
    contract = tmp_path / "contracts.jsonl"
    workflowx = tmp_path / "workflowx.jsonl"
    workflowx.write_text("", encoding="utf-8")

    server = serve(
        host="127.0.0.1", port=0,
        registry_path=registry, contract_path=contract,
        workflowx_fixture=workflowx,
        block=False,
    )
    port = server.server_address[1]
    base = f"http://127.0.0.1:{port}"

    for _ in range(50):
        try:
            urlopen(Request(f"{base}/healthz"), timeout=0.5)
            break
        except Exception:
            time.sleep(0.05)

    yield base, port
    server.shutdown()


def test_law7_attacker_origin_rejected(running_daemon):
    """Origin: http://attacker.com → 403, no body, no CORS leak."""
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    base, _ = running_daemon
    req = Request(f"{base}/healthz")
    req.add_header("Origin", "http://attacker.com")
    with pytest.raises(HTTPError) as exc:
        urlopen(req, timeout=2)
    assert exc.value.code == 403, (
        "cross-origin attacker request must return 403, not 200"
    )


def test_law7_sec_fetch_site_cross_site_rejected(running_daemon):
    """Sec-Fetch-Site: cross-site (modern browsers' canonical signal)
    must be rejected even if Origin happens to be missing."""
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    base, _ = running_daemon
    req = Request(f"{base}/healthz")
    req.add_header("Sec-Fetch-Site", "cross-site")
    with pytest.raises(HTTPError) as exc:
        urlopen(req, timeout=2)
    assert exc.value.code == 403


def test_law7_attacker_post_rejected(running_daemon):
    """Cross-origin POST (the CSRF mutation case) must be rejected
    BEFORE the dispatcher runs — state must not change."""
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    base, _ = running_daemon
    req = Request(
        f"{base}/events", data=b"{}", method="POST",
        headers={"Content-Type": "application/json"},
    )
    req.add_header("Origin", "http://attacker.com")
    with pytest.raises(HTTPError) as exc:
        urlopen(req, timeout=2)
    assert exc.value.code == 403


def test_law7_same_origin_echoes_origin_not_wildcard(running_daemon):
    """Same-origin request succeeds AND Access-Control-Allow-Origin
    echoes the request's Origin (never ``*``)."""
    from urllib.request import Request, urlopen

    base, port = running_daemon
    req = Request(f"{base}/healthz")
    req.add_header("Origin", f"http://127.0.0.1:{port}")
    resp = urlopen(req, timeout=2)
    assert resp.status == 200
    cors = resp.headers.get("Access-Control-Allow-Origin")
    assert cors == f"http://127.0.0.1:{port}", (
        f"expected echo of Origin, got {cors!r} — wildcard CORS regression"
    )
    assert cors != "*", "wildcard CORS regression"


def test_law7_extension_origin_allowed(running_daemon):
    """Browser-extension origins (chrome-extension://, moz-extension://)
    are allowlisted by scheme since the extension ID is generated at
    install time and unknown at server-start."""
    from urllib.request import Request, urlopen

    base, _ = running_daemon
    req = Request(f"{base}/healthz")
    req.add_header("Origin", "chrome-extension://abcdefghijklmnop")
    resp = urlopen(req, timeout=2)
    assert resp.status == 200
    assert resp.headers.get(
        "Access-Control-Allow-Origin"
    ) == "chrome-extension://abcdefghijklmnop"


def test_law7_no_origin_allowed_for_non_browser_clients(running_daemon):
    """curl / tray app / direct HTTP clients send no Origin header.
    These must be served (the tray relies on it) but CORS headers must
    NOT be emitted (no browser context that needs opting-in)."""
    from urllib.request import Request, urlopen

    base, _ = running_daemon
    resp = urlopen(Request(f"{base}/healthz"), timeout=2)
    assert resp.status == 200
    assert resp.headers.get("Access-Control-Allow-Origin") is None, (
        "CORS header must not be sent when request has no Origin"
    )
