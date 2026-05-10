"""
Runtime router: pick the L0–L1 ingestion extractor per invocation.

Three paths:

* ``--from-gbrain`` (Plan B): hard-require gbrain. Raise
  ``GbrainNotInstalledError`` if absent.
* ``--prefer local`` (Plan A): force the native LLM extractor. Always
  available — works without gbrain.
* default (auto): prefer gbrain when present (gbrain handles richer
  formats); fall back to Plan A (local LLM extractor) otherwise.

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
    """Reserved — kept as a class for backwards compatibility with any
    external code that imported it. Plan A is now shipped; this error
    is no longer raised by ``detect_extraction_method``."""


class NoExtractorAvailableError(IngestRouterError):
    """Reserved — superseded by Plan A's universal availability. Kept
    as a class so existing imports don't break, but this error is no
    longer raised: ``prefer="auto"`` always returns either gbrain-mcp
    or llm-anthropic."""


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
    ``prefer="local"``:  force Plan A (native LLM extractor). Always works.
    ``prefer="auto"``:   gbrain if present, else Plan A.
    """
    if prefer == "gbrain":
        if not gbrain_available():
            raise GbrainNotInstalledError(
                "gbrain not detected. Install via "
                "`bun install -g github:garrytan/gbrain` or use "
                "`--prefer local` to use the native LLM extractor instead."
            )
        return "gbrain-mcp"

    if prefer == "local":
        return "llm-anthropic"

    # prefer == "auto"
    if gbrain_available():
        return "gbrain-mcp"
    return "llm-anthropic"


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
