"""Step 4a: gather the evidence the voice agent reasons about."""

from __future__ import annotations

from ..simulator import log_store


def collect(run_id: str) -> dict:
    entries = log_store.read(run_id)
    error_entries = [e for e in entries if e.get("level") == "ERROR"]
    latest = error_entries[-1] if error_entries else None
    return {
        "run_id": run_id,
        "entry_count": len(entries),
        "error_count": len(error_entries),
        "entries": entries[-40:],
        "latest_error": latest,
        "traceback": (latest or {}).get("traceback"),
    }


def spoken_summary(evidence: dict) -> str:
    """One sentence the agent can say while the logs stream in."""
    if not evidence["error_count"]:
        return f"I pulled {evidence['entry_count']} log lines and none of them are errors."
    latest = evidence["latest_error"] or {}
    return (
        f"I pulled {evidence['entry_count']} log lines; {evidence['error_count']} are errors. "
        f"The newest one is a {latest.get('error_type', 'failure')} while "
        f"{latest.get('message', 'handling the request')}."
    )
