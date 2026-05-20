"""
Tests for the /invest/dashboard daemon routes (Fix 8 from design audit).

The daemon serves:
- GET /invest/dashboard       → HTML page
- GET /invest/dashboard/data  → JSON of InvestmentDashboardSummary

Routes are read-only — the investment vertical is advisory-only and the
dashboard mirrors the CLI `invest dashboard` output. Tests spin up the
real daemon and seed cost-of-living / trades / theses on disk so the
summary has something to roll up.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


@pytest.fixture
def daemon(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

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

    yield base, fake_home
    server.shutdown()


def _seed_cost_of_living(fake_home, *, monthly_target=14000):
    from agent.investment.cost_of_living import CostOfLivingProfile, save_profile

    invest_home = fake_home / ".neuro_os_investment"
    invest_home.mkdir(parents=True, exist_ok=True)
    save_profile(
        CostOfLivingProfile(
            monthly_target=monthly_target,
            region="Bay Area",
            breakdown=None,
            source="direct",
            written_at=datetime.now(timezone.utc),
        ),
        home=invest_home,
    )


def _get(base, path):
    req = Request(f"{base}{path}")
    req.add_header("Origin", f"http://127.0.0.1:{base.rsplit(':',1)[-1]}")
    return urlopen(req, timeout=5)


# ---------------------------------------------------------------------------
# GET /invest/dashboard
# ---------------------------------------------------------------------------


def test_invest_dashboard_page_served(daemon):
    base, _ = daemon
    resp = _get(base, "/invest/dashboard")
    assert resp.status == 200
    body = resp.read().decode("utf-8")
    assert "Investment dashboard" in body
    assert "/invest/dashboard/data" in body
    # The advisory-only pill should be in the HTML
    assert "advisory only" in body.lower()


# ---------------------------------------------------------------------------
# GET /invest/dashboard/data
# ---------------------------------------------------------------------------


def test_data_endpoint_empty_state(daemon):
    """No cost-of-living, no trades, no theses → summary still renders
    with the no_cost_of_living_target flag firing."""
    base, _ = daemon
    resp = _get(base, "/invest/dashboard/data")
    data = json.loads(resp.read())
    s = data["summary"]
    assert s["vertical"] == "investment"
    assert s["window_days"] == 30  # default
    assert s["cost_of_living_target"] is None
    assert "no_cost_of_living_target" in s["system_health_flags"]


def test_data_endpoint_with_cost_of_living(daemon):
    base, home = daemon
    _seed_cost_of_living(home, monthly_target=12500)
    data = json.loads(_get(base, "/invest/dashboard/data").read())
    s = data["summary"]
    assert s["cost_of_living_target"] == 12500.0
    assert "no_cost_of_living_target" not in s["system_health_flags"]


def test_data_endpoint_window_query_respected(daemon):
    base, _ = daemon
    data = json.loads(_get(base, "/invest/dashboard/data?window=90").read())
    assert data["summary"]["window_days"] == 90


def test_data_endpoint_rejects_window_out_of_range(daemon):
    base, _ = daemon
    with pytest.raises(HTTPError) as exc:
        _get(base, "/invest/dashboard/data?window=0")
    assert exc.value.code == 400

    with pytest.raises(HTTPError) as exc:
        _get(base, "/invest/dashboard/data?window=500")
    assert exc.value.code == 400


def test_data_endpoint_rejects_non_integer_window(daemon):
    base, _ = daemon
    with pytest.raises(HTTPError) as exc:
        _get(base, "/invest/dashboard/data?window=hello")
    assert exc.value.code == 400


# ---------------------------------------------------------------------------
# Security — new routes inherit CORS hardening
# ---------------------------------------------------------------------------


def test_invest_dashboard_rejects_attacker_origin(daemon):
    base, _ = daemon
    for path in ("/invest/dashboard", "/invest/dashboard/data"):
        req = Request(f"{base}{path}")
        req.add_header("Origin", "http://attacker.com")
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 403, f"{path} should reject attacker origin"
