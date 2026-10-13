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


def topic(evidence: dict) -> str:
    """The `topic` dynamic variable the agent opens the call with: the error logs."""
    if not evidence.get("error_count"):
        latest_note = "no errors captured yet" if evidence.get("entry_count") else "no logs yet"
        return f"the error logs for run {evidence.get('run_id', 'unknown')} ({latest_note})"
    latest = evidence.get("latest_error") or {}
    return (
        f"the error logs for run {evidence.get('run_id', 'unknown')}: "
        f"{evidence['error_count']} error lines, newest is "
        f"{latest.get('error_type', 'an error')} — {latest.get('error', 'no message')}"
    )


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
