"""
Tests for ``agent.research.ingest_router``.

Strategy: monkeypatch ``gbrain_available`` so we can drive every
branch (gbrain present / absent) without depending on the test host's
PATH. Also pin the typed-error contract: each error class is
catchable as the same base.
"""
from __future__ import annotations

import pytest

from agent.research import ingest_router as router_mod
from agent.research.ingest_router import (
    GbrainNotInstalledError,
    IngestRouterError,
    NoExtractorAvailableError,
    PlanANotImplementedError,
    detect_extraction_method,
)


# ---------------------------------------------------------------------------
# prefer="gbrain"
# ---------------------------------------------------------------------------


def test_prefer_gbrain_returns_gbrain_when_present(monkeypatch):
    monkeypatch.setattr(router_mod, "gbrain_available", lambda: True)
    assert detect_extraction_method(prefer="gbrain") == "gbrain-mcp"


def test_prefer_gbrain_raises_when_absent(monkeypatch):
    monkeypatch.setattr(router_mod, "gbrain_available", lambda: False)
    with pytest.raises(GbrainNotInstalledError):
        detect_extraction_method(prefer="gbrain")


def test_gbrain_not_installed_error_inherits_router_base():
    """Callers should be able to `except IngestRouterError` and catch all 3."""
    assert issubclass(GbrainNotInstalledError, IngestRouterError)


# ---------------------------------------------------------------------------
# prefer="local" (Plan A; not implemented in Lane 1)
# ---------------------------------------------------------------------------


def test_prefer_local_raises_plan_a_not_implemented():
    with pytest.raises(PlanANotImplementedError):
        detect_extraction_method(prefer="local")


def test_plan_a_not_implemented_inherits_router_base():
    assert issubclass(PlanANotImplementedError, IngestRouterError)


# ---------------------------------------------------------------------------
# prefer="auto" (default)
# ---------------------------------------------------------------------------


def test_auto_returns_gbrain_when_present(monkeypatch):
    monkeypatch.setattr(router_mod, "gbrain_available", lambda: True)
    assert detect_extraction_method(prefer="auto") == "gbrain-mcp"


def test_auto_raises_when_neither_extractor_available(monkeypatch):
    monkeypatch.setattr(router_mod, "gbrain_available", lambda: False)
    with pytest.raises(NoExtractorAvailableError):
        detect_extraction_method(prefer="auto")


def test_no_extractor_available_inherits_router_base():
    assert issubclass(NoExtractorAvailableError, IngestRouterError)


def test_default_prefer_is_auto(monkeypatch):
    """Calling without arguments should match prefer='auto'."""
    monkeypatch.setattr(router_mod, "gbrain_available", lambda: True)
    assert detect_extraction_method() == "gbrain-mcp"


# ---------------------------------------------------------------------------
# Error messages mention the right next step (UX-level contract).
# ---------------------------------------------------------------------------


def test_error_messages_point_to_install_command(monkeypatch):
    monkeypatch.setattr(router_mod, "gbrain_available", lambda: False)
    with pytest.raises(GbrainNotInstalledError) as exc:
        detect_extraction_method(prefer="gbrain")
    assert "bun install" in str(exc.value)


def test_auto_error_mentions_both_paths(monkeypatch):
    monkeypatch.setattr(router_mod, "gbrain_available", lambda: False)
    with pytest.raises(NoExtractorAvailableError) as exc:
        detect_extraction_method(prefer="auto")
    msg = str(exc.value)
    # User should know both paths and how to remedy.
    assert "gbrain" in msg
    assert "Plan A" in msg
