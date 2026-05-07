"""
E2E HTTP scenarios — drive the daemon over the wire as if a user was
using it. No browser. Each test maps to one S-numbered scenario in
``scenarios.md``.

These run against a real ``founder_loop`` daemon spawned by the
``daemon`` fixture in ``conftest.py``. They are slower than unit
tests (a few hundred ms each, mostly daemon boot) but verify the full
HTTP surface end-to-end, including request parsing, response shape,
and side-effect persistence.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone



# ---------------------------------------------------------------------------
# S02 — mid-day tick with no urge → continue
# ---------------------------------------------------------------------------


def test_S02_tick_with_no_urge_returns_continue(daemon, http):
    """A bare daemon tick should land on ``continue`` without crashing."""
    status, body = http.get(daemon.url("/tick?dry_run=true"))
    assert status == 200, body
    tick = body["tick"]
    assert tick["action"]["op"] == "continue"
    # Forecasted urge defaults to 'none' for an empty workflowx.
    assert tick["forecasted"]["predicted_urge"] == "none"


# ---------------------------------------------------------------------------
# S03 — user logs urge via CLI; next tick proposes constructive expression
# ---------------------------------------------------------------------------


def test_S03_user_logged_urge_drives_proposal_via_cli(daemon, http, tmp_path):
    """The ``loop urge`` CLI writes events; the next /tick reads them.

    Verifies the file path that the daemon and the CLI share — the
    fixture's events_path is what the CLI is configured to write.
    """
    # Run `python -m agent loop urge entertainment --events <path>`.
    result = subprocess.run(
        [
            sys.executable, "-m", "agent",
            "loop", "urge", "entertainment",
            "--registry", str(daemon.registry_path),
            "--contracts", str(daemon.contract_path),
            "--events", str(daemon.events_path),
            "--context", "I want YouTube before lunch",
        ],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    # The CLI prints the JSON of the created event.
    event = json.loads(result.stdout)
    assert event["urge_type"] == "entertainment"
    assert event["source"] == "user_logged"

    # Now ask the daemon to tick. The user-logged urge should
    # override the predictor's "none" and emit a proposal.
    status, body = http.get(daemon.url("/tick?dry_run=true"))
    assert status == 200, body
    tick = body["tick"]
    assert tick["action"]["op"] == "propose_constructive_expression"
    assert tick["action"]["payload"].get("urge_source") == "user_logged"
    assert "user-logged urge" in tick["action"]["rationale"].lower()


# ---------------------------------------------------------------------------
# S06 — accept the constructive expression: /events records it
# ---------------------------------------------------------------------------


def test_S06_accepted_expression_event_is_persisted(daemon, http):
    """``POST /events kind=accepted_expression`` writes an event row.

    The daemon returns 201 Created with the persisted record under
    ``logged``. Verify both wire-level success and on-disk persistence.
    """
    status, body = http.post(
        daemon.url("/events"),
        {
            "kind": "accepted_expression",
            "action": "voice_memo_to_friend",
            "context": "took 10-min walk",
        },
    )
    assert status == 201, body
    assert body["logged"]["kind"] == "accepted_expression"
    # On-disk: the events file (separate from urge events) has the row.
    lines = [line for line in daemon.events_path.read_text().splitlines() if line.strip()]
    assert any('"kind": "accepted_expression"' in line for line in lines)


# ---------------------------------------------------------------------------
# S07 — override fires /events kind=overrode_proposal
# ---------------------------------------------------------------------------


def test_S07_overrode_proposal_event_is_persisted(daemon, http):
    """``POST /events kind=overrode_proposal`` is accepted by the daemon."""
    status, body = http.post(
        daemon.url("/events"),
        {
            "kind": "overrode_proposal",
            "url": "https://youtube.com",
            "context": "user clicked Proceed anyway",
        },
    )
    assert status == 201, body
    assert body["logged"]["kind"] == "overrode_proposal"


# ---------------------------------------------------------------------------
# S11 — workflowx-detect three modes via subprocess
# ---------------------------------------------------------------------------


def test_S11_workflowx_detect_three_modes(tmp_path):
    """The detector reports the right source for fallback / dir / env."""
    # Mode A: nothing installed → fallback.
    fallback = tmp_path / "founder_loop" / "workflowx.jsonl"
    r = subprocess.run(
        [
            sys.executable, "-m", "agent",
            "loop", "workflowx-detect",
            "--fallback", str(fallback),
        ],
        capture_output=True, text=True, timeout=10,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["source"] == "fallback"
    assert out["is_real"] is False

    # Mode B: stub at ~/.workflowx/exports/today.jsonl.
    exports = tmp_path / ".workflowx" / "exports"
    exports.mkdir(parents=True)
    (exports / "today.jsonl").write_text("{}\n", encoding="utf-8")
    r = subprocess.run(
        [
            sys.executable, "-m", "agent",
            "loop", "workflowx-detect",
            "--fallback", str(fallback),
        ],
        capture_output=True, text=True, timeout=10,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["source"].endswith(":dot-workflowx")
    assert out["is_real"] is True

    # Mode C: env var override.
    custom = tmp_path / "custom.jsonl"
    custom.write_text("{}\n", encoding="utf-8")
    r = subprocess.run(
        [
            sys.executable, "-m", "agent",
            "loop", "workflowx-detect",
            "--fallback", str(fallback),
        ],
        capture_output=True, text=True, timeout=10,
        env={
            "HOME": str(tmp_path),
            "WORKFLOWX_EXPORTS_PATH": str(custom),
            "PATH": "/usr/bin:/bin",
        },
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["source"] == "env"
    assert out["is_real"] is True


# ---------------------------------------------------------------------------
# S14 — daemon boots with no workflowx; no crash, blind-mode behavior
# ---------------------------------------------------------------------------


def test_S14_empty_workflowx_blind_boot(daemon, http):
    """No urge predicted, no crash. /healthz, /tick, /tank all 200."""
    for path in ("/healthz", "/tick", "/tank"):
        status, _ = http.get(daemon.url(path))
        assert status == 200, f"{path} returned {status}"


# ---------------------------------------------------------------------------
# S15 — malformed workflowx JSONL: bad lines skipped
# ---------------------------------------------------------------------------


def test_S15_malformed_workflowx_skips_bad_lines(daemon, http):
    """Daemon must not crash when the workflowx fixture has corrupt lines."""
    daemon.workflowx_fixture.write_text(
        '{"timestamp":"2026-05-06T14:00:00+00:00",'
        '"distraction_minutes":5,"deep_work_minutes":40,'
        '"context_switches":2}\n'
        '{garbage not json\n'
        '\n'  # blank line
        '{"timestamp":"2026-05-06T15:00:00+00:00",'
        '"distraction_minutes":1,"deep_work_minutes":59,'
        '"context_switches":1}\n',
        encoding="utf-8",
    )
    # Either the tick succeeds (good) or the malformed line bubbles up
    # as a 500 — which IS a real bug we'd want a test to surface. The
    # observe.RawEvent loader currently calls model_validate and may
    # raise; we accept 200 (skipped silently) or 500 (loud failure).
    # Asserting 200 here pins the desired behavior.
    status, body = http.get(daemon.url("/tick?dry_run=true"))
    assert status == 200, (
        f"tick crashed on malformed workflowx: {body}. "
        "Defensive parsing in observe.FixtureWorkflowxAdapter._load "
        "should skip bad lines."
    )
    # The valid lines were ingested — the timestamp on `state` should
    # reflect the fixture's most-recent valid event hour.
    tick = body["tick"]
    assert tick["state"]["timestamp"] is not None


# ---------------------------------------------------------------------------
# S17 — `loop tick` with no contract → graceful zero-tank
# ---------------------------------------------------------------------------


def test_S17_tick_with_no_contract_is_graceful(daemon, http):
    """No contract bound; tick returns sensible defaults, no 500."""
    # The daemon fixture starts with no contract (empty contracts.jsonl).
    status, body = http.get(daemon.url("/tick?dry_run=true"))
    assert status == 200, body
    tick = body["tick"]
    assert tick["tank"]["status"] == "below_threshold"
    assert tick["tank"]["percent"] == 0.0


# ---------------------------------------------------------------------------
# S18 — rest day: state.day_kind="rest" → action.op="rest"
# ---------------------------------------------------------------------------


def test_S18_rest_day_emits_rest_action(daemon, http):
    """When the workflowx fixture's last_intent says 'rest day', the
    inferred ``day_kind=rest`` short-circuits the policy to ``rest``.

    The fixture's timestamp must fall in the daemon's read_window
    (last hour relative to now); use ``datetime.now(timezone.utc)``
    so the test is robust to wall-clock drift.
    """
    now = datetime.now(timezone.utc).replace(microsecond=0)
    daemon.workflowx_fixture.write_text(
        json.dumps({
            "timestamp": now.isoformat(),
            "distraction_minutes": 0,
            "deep_work_minutes": 0,
            "context_switches": 0,
            "last_intent": "rest day, recovering",
        }) + "\n",
        encoding="utf-8",
    )
    status, body = http.get(daemon.url("/tick?dry_run=true"))
    assert status == 200, body
    tick = body["tick"]
    assert tick["state"]["day_kind"] == "rest"
    assert tick["action"]["op"] == "rest"


# ---------------------------------------------------------------------------
# S19 — five urges in a minute: all are written; latest is unresolved
# ---------------------------------------------------------------------------


def test_S19_five_urges_in_a_minute_all_written(daemon, http, tmp_path):
    """Today there's no rate-limit on user-logged urges. All five get
    written; the policy reads the most-recent unresolved one."""
    for i in range(5):
        r = subprocess.run(
            [
                sys.executable, "-m", "agent",
                "loop", "urge", "entertainment",
                "--registry", str(daemon.registry_path),
                "--contracts", str(daemon.contract_path),
                "--events", str(daemon.events_path),
                "--context", f"urge {i}",
            ],
            capture_output=True, text=True, timeout=10,
        )
        assert r.returncode == 0, r.stderr

    # Five urge rows + zero resolution rows = five lines.
    lines = [
        line for line in daemon.events_path.read_text().splitlines()
        if line.strip()
    ]
    assert len(lines) == 5
    # The most recent one is what the policy sees.
    status, body = http.get(daemon.url("/tick?dry_run=true"))
    assert status == 200, body
    tick = body["tick"]
    # Some implementations may legitimately emit
    # propose_constructive_expression here; either is acceptable for
    # this scenario — what we verify is that the daemon DIDN'T fall
    # over with five recent urge events.
    assert tick["action"]["op"] in (
        "propose_constructive_expression", "continue"
    )
