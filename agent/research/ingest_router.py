"""
Runtime router: pick the L0–L1 ingestion extractor per invocation.

Three paths:

* ``--from-gbrain`` (Plan B): hard-require gbrain. Raise
  ``GbrainNotInstalledError`` if absent.
* ``--from-llm`` (Plan A, future PR): hard-require the native LLM
  extractor. Currently raises ``PlanANotImplementedError`` because Lane
  1 ships only Plan B. (The error is typed so the CLI can print a
  helpful message — the auto-fallback path doesn't go through this
  branch.)
* default (auto): prefer gbrain when present, raise
  ``NoExtractorAvailableError`` otherwise (Plan A is the future
  fallback).

Detection: subprocess ``gbrain --version`` with a 1-second timeout.
Cached per-invocation; never makes a network call.
"""
from __future__ import annotations

import shutil
import subprocess
from typing import Literal


ExtractionMethod = Literal["gbrain-mcp", "llm-anthropic"]
PreferenceMode = Literal["auto", "gbrain", "local"]


class IngestRouterError(RuntimeError):
    """Base class for router errors so callers can catch with one type."""


class GbrainNotInstalledError(IngestRouterError):
    """Raised when ``--from-gbrain`` is explicit but gbrain isn't on PATH
    or its ``--version`` probe fails."""


class PlanANotImplementedError(IngestRouterError):
    """Raised when the user picks Plan A explicitly but it isn't shipped
    in this build. Lane 1 only ships Plan B; Plan A is in a follow-up."""


class NoExtractorAvailableError(IngestRouterError):
    """Raised when auto-detection finds no usable extractor (gbrain
    absent AND Plan A not yet implemented)."""


_GBRAIN_PROBE_TIMEOUT_SECONDS = 1.0


def gbrain_available() -> bool:
    """Return True iff ``gbrain --version`` exits cleanly within 1s.

    Cheap detection: ``shutil.which`` first (saves a subprocess when
    gbrain isn't on PATH at all), then a real subprocess to confirm it
    actually runs (a stale symlink shouldn't pass).
    """
    if shutil.which("gbrain") is None:
        return False
    try:
        proc = subprocess.run(
            ["gbrain", "--version"],
            capture_output=True,
            timeout=_GBRAIN_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return proc.returncode == 0


def detect_extraction_method(
    prefer: PreferenceMode = "auto",
) -> ExtractionMethod:
    """Decide which extractor to use.

    ``prefer="gbrain"``: hard-require gbrain, raise if absent.
    ``prefer="local"``:  hard-require Plan A; not shipped in Lane 1.
    ``prefer="auto"``:   gbrain if present, else raise (Plan A is the
                          future fallback but isn't implemented yet).
    """
    if prefer == "gbrain":
        if not gbrain_available():
            raise GbrainNotInstalledError(
                "gbrain not detected. Install via "
                "`bun install -g github:garrytan/gbrain` or omit --from-gbrain "
                "(once Plan A ships, the auto-fallback will use the local "
                "extractor instead)."
            )
        return "gbrain-mcp"

    if prefer == "local":
        raise PlanANotImplementedError(
            "Plan A (native LLM extractor) is not yet shipped. Lane 1 ships "
            "only Plan B (the gbrain adapter). Use --from-gbrain or omit the "
            "flag to use auto-detect."
        )

    # prefer == "auto"
    if gbrain_available():
        return "gbrain-mcp"
    raise NoExtractorAvailableError(
        "No extractor available: gbrain is not installed and Plan A (native "
        "LLM extractor) is not yet shipped. Install gbrain via "
        "`bun install -g github:garrytan/gbrain` to proceed."
    )


__all__ = [
    "ExtractionMethod",
    "PreferenceMode",
    "IngestRouterError",
    "GbrainNotInstalledError",
    "PlanANotImplementedError",
    "NoExtractorAvailableError",
    "gbrain_available",
    "detect_extraction_method",
]
