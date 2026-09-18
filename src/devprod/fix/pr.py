"""Step 6c: branch, commit, push and open the pull request."""

from __future__ import annotations

import subprocess
import time

from ..config import settings
from .planner import FixPlan


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=settings.repo_root, capture_output=True, text=True, timeout=120
    )


def _body(plan: FixPlan, root_cause_headline: str, run_id: str) -> str:
    return (
        f"## Summary\n\n{plan.title}. {plan.summary}\n\n"
        f"Root cause: {root_cause_headline}\n\n"
        f"## Change\n\n```diff\n{plan.patch.diff()}```\n\n"
        f"## Verification\n\n- replayed the failing request from simulator run `{run_id}`\n"
        f"- suggested tests: {', '.join(plan.tests)}\n\n"
        f"## Risk\n\n{plan.risk}\n"
    )


def open_pr(plan: FixPlan, root_cause_headline: str, run_id: str) -> dict:
    """Open a real PR when enabled; otherwise return a dry-run result for the demo."""
    target = plan.patch.file.rsplit("/", 1)[-1].replace(".py", "")
    branch = f"devprod/fix-{target}-{int(time.time())}"
    body = _body(plan, root_cause_headline, run_id)
    if not settings.enable_pr:
        return {
            "mode": "dry-run",
            "branch": branch,
            "url": f"https://example.invalid/pull/{abs(hash(branch)) % 900 + 100}",
            "body": body,
            "note": "set DEVPROD_ENABLE_PR=1 with a configured git remote to open a real PR",
        }

    _git("checkout", "-b", branch)
    _git("add", plan.patch.file)
    commit = _git("commit", "-m", f"fix: {plan.title}")
    push = _git("push", "-u", "origin", branch)
    if push.returncode != 0:
        return {"mode": "error", "branch": branch, "error": push.stderr.strip(), "body": body}

    gh = subprocess.run(
        [
            "gh", "pr", "create",
            "--base", settings.pr_base_branch,
            "--head", branch,
            "--title", f"fix: {plan.title}",
            "--body", body,
        ],
        cwd=settings.repo_root,
        capture_output=True,
        text=True,
        timeout=180,
    )
    url = gh.stdout.strip().splitlines()[-1] if gh.returncode == 0 and gh.stdout.strip() else ""
    return {
        "mode": "live",
        "branch": branch,
        "url": url,
        "commit": commit.stdout.strip(),
        "error": None if gh.returncode == 0 else gh.stderr.strip(),
        "body": body,
    }
