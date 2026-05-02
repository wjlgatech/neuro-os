"""Experiment logger for TRUE validation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

DEFAULT_LOG = "memory/experiments.jsonl"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def log_experiment(record: Dict, path: str = DEFAULT_LOG):
    event = {"timestamp": utc_now(), **record}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


if __name__ == "__main__":
    log_experiment({"hypothesis": "test", "result": "inconclusive"})
