"""
Version Registry.

File-backed log of accepted, refined, or rejected updates with
before/after metrics. The default location is
``versions/version_registry.jsonl``; callers can swap in a different
path for tests via ``set_registry_path``.

Each call to ``append_version`` immediately appends a JSON line to disk
so a crash never loses an entry, and also caches the entry in memory so
``read_versions`` and ``export_registry`` are cheap.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REGISTRY_PATH = Path("versions/version_registry.jsonl")

_loaded_path: Path | None = None
_registry: List[Dict[str, Any]] = []


def set_registry_path(path: str | Path) -> None:
    """Override the default registry path (mostly used by tests)."""
    global REGISTRY_PATH, _loaded_path, _registry
    REGISTRY_PATH = Path(path)
    _loaded_path = None
    _registry = []


def _ensure_loaded() -> None:
    global _loaded_path, _registry
    if _loaded_path == REGISTRY_PATH:
        return
    _registry = []
    if REGISTRY_PATH.exists():
        with REGISTRY_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    _registry.append(json.loads(line))
    _loaded_path = REGISTRY_PATH


def append_version(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Append a version entry to the registry and persist immediately.

    Returns the (timestamp-augmented) entry that was written.
    """
    _ensure_loaded()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **entry,
    }
    _registry.append(record)
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_versions() -> List[Dict[str, Any]]:
    """Return all version entries currently in the registry."""
    _ensure_loaded()
    return list(_registry)


def export_registry(path: str | Path) -> None:
    """Write the registry to a JSON-lines file at ``path``."""
    _ensure_loaded()
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for entry in _registry:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_registry(path: str | Path) -> List[Dict[str, Any]]:
    """Load a registry from ``path``, replacing the active in-memory state."""
    set_registry_path(path)
    _ensure_loaded()
    return list(_registry)


__all__ = [
    "REGISTRY_PATH",
    "set_registry_path",
    "append_version",
    "read_versions",
    "export_registry",
    "load_registry",
]
