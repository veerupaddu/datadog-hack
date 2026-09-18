"""Per-run capture of the dummy service's structured logs."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import settings


def log_path(run_id: str) -> Path:
    return settings.logs_dir / f"{run_id}.jsonl"


def read(run_id: str, limit: int = 200) -> list[dict]:
    path = log_path(run_id)
    if not path.exists():
        return []
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"level": "RAW", "message": line})
    return entries


def errors(run_id: str) -> list[dict]:
    return [e for e in read(run_id) if e.get("level") == "ERROR"]


def clear(run_id: str) -> None:
    path = log_path(run_id)
    if path.exists():
        path.unlink()
