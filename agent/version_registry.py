# Version registry module

import json
from datetime import datetime
from pathlib import Path

REGISTRY_PATH = Path("versions/version_registry.jsonl")


def append_version(entry):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.utcnow().isoformat(), **entry}
    with open(REGISTRY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def read_versions():
    if not REGISTRY_PATH.exists():
        return []
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
