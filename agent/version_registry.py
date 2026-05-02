"""
Neuro-OS version registry — shim over the flywheel-loop registry.

Both the L1 knowledge loop (``agent.self_evolving_loop``) and the L2
code loop (``agent.self_modification`` → ``flywheel_loop.self_modification``)
need to write to the same on-disk log so a single
``set_registry_path`` call routes both. This module re-exports the
substrate's registry primitives and adds two convenience helpers
(``export_registry``, ``load_registry``) that neuro-os tests use.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from flywheel_loop.registry import (
    REGISTRY_PATH,
    _ensure_loaded,
    _registry,  # type: ignore[attr-defined]
    append_version,
    read_versions,
    set_registry_path,
)


def export_registry(path: str | Path) -> None:
    """Write the in-memory registry to a JSON-lines file at ``path``."""
    _ensure_loaded()
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for entry in _registry:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


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
