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
# prefer="local" (Plan A — now shipped per PR-1)
# ---------------------------------------------------------------------------


def test_prefer_local_returns_llm_anthropic():
    """Plan A is shipped; prefer='local' returns 'llm-anthropic' regardless
    of gbrain presence. (PR-1 — Paul's week of May 11.)"""
    assert detect_extraction_method(prefer="local") == "llm-anthropic"


def test_plan_a_not_implemented_inherits_router_base():
    """The error class is kept as part of the public surface for any
    external callers that imported it; it just isn't raised anymore."""
    assert issubclass(PlanANotImplementedError, IngestRouterError)


# ---------------------------------------------------------------------------
# prefer="auto" (default)
# ---------------------------------------------------------------------------


def test_auto_returns_gbrain_when_present(monkeypatch):
    monkeypatch.setattr(router_mod, "gbrain_available", lambda: True)
    assert detect_extraction_method(prefer="auto") == "gbrain-mcp"


def test_auto_falls_back_to_llm_anthropic_when_gbrain_absent(monkeypatch):
    """PR-1: auto-detect now ALWAYS produces a usable extractor —
    Plan A is the universal fallback when gbrain is absent."""
    monkeypatch.setattr(router_mod, "gbrain_available", lambda: False)
    assert detect_extraction_method(prefer="auto") == "llm-anthropic"


def test_no_extractor_available_inherits_router_base():
    """Class kept for back-compat (no longer raised; superseded by Plan A)."""
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


def test_gbrain_error_message_points_at_local_fallback(monkeypatch):
    """When gbrain is hard-required but absent, the error message
    points users at `--prefer local` as the alternative."""
    monkeypatch.setattr(router_mod, "gbrain_available", lambda: False)
    with pytest.raises(GbrainNotInstalledError) as exc:
        detect_extraction_method(prefer="gbrain")
    msg = str(exc.value)
    assert "--prefer local" in msg
    assert "bun install" in msg
