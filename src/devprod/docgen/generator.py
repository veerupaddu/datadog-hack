"""Steps 7 and 8: write the incident document and summarise it for the agent to read."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..config import settings


def _timeline(events: list[dict]) -> str:
    return "\n".join(f"- `{e['ts']}` **{e['step']}** — {e['message']}" for e in events)


def write_doc(state) -> Path:
    rc = state.root_cause
    plan = state.fix_plan
    path = settings.docs_dir / f"{state.run_id}.md"
    pr_url = (state.pr or {}).get("url", "n/a")
    lines = [
        f"# Incident {state.run_id} — {rc.headline if rc else 'unresolved'}",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat()} by the DevProd simulator._",
        "",
        "## What happened",
        "",
        f"Fault induced: **{state.fault_id}**. The orders service returned "
        f"`{state.failing_status}` for order `{(state.failing_payload or {}).get('order_id')}`.",
        "",
        "## Root cause",
        "",
        f"**{rc.error_type}** in `{rc.function}()` at `{rc.file}:{rc.line}`" if rc else "unknown",
        "",
        (rc.explain() if rc else ""),
        "",
        "### Evidence",
        "",
        *[f"- {line}" for line in (rc.evidence if rc else [])],
        "",
        "## Fix",
        "",
        f"**{plan.title}** — {plan.summary}" if plan else "no fix applied",
        "",
        "```diff",
        (plan.patch.diff() if plan else ""),
        "```",
        "",
        f"Risk: {plan.risk}" if plan else "",
        f"Verification: replayed request returned `{state.verify_status}`",
        f"Pull request: {pr_url}",
        "",
        "## Timeline",
        "",
        _timeline(state.events),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def summarize(state) -> str:
    rc = state.root_cause
    plan = state.fix_plan
    pr_url = (state.pr or {}).get("url", "no PR")
    if not rc:
        return f"Run {state.run_id} ended without a diagnosis."
    return (
        f"We broke the orders service on purpose with the {state.fault_id} scenario and it "
        f"returned {state.failing_status}. The cause was a {rc.error_type} in {rc.function}() "
        f"at line {rc.line}: {rc.headline}. "
        f"You approved the fix — {plan.summary if plan else 'no change'} — and the replayed "
        f"request now returns {state.verify_status}. "
        f"The change is up for review at {pr_url}, and the full write-up with the evidence "
        f"is in documentation/incidents/{state.run_id}.md."
    )
