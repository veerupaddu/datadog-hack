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


def _current_branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main"


def _compare_url(base: str, branch: str) -> str:
    """GitHub 'open a PR' page for the pushed branch, used when `gh` is unavailable."""
    remote = _git("remote", "get-url", "origin").stdout.strip()
    remote = remote.removesuffix(".git")
    if remote.startswith("git@"):
        remote = "https://" + remote[4:].replace(":", "/", 1)
    return f"{remote}/compare/{base}...{branch}?expand=1"


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

    origin_branch = _current_branch()
    base = settings.pr_base_branch or origin_branch
    _git("checkout", "-b", branch)
    _git("add", plan.patch.file)
    commit = _git("commit", "-m", f"fix: {plan.title}")
    push = _git("push", "-u", "origin", branch)
    # Back to the demo branch: the fix lives on its own branch and the bug is back in the tree.
    _git("checkout", origin_branch)
    if push.returncode != 0:
        return {"mode": "error", "branch": branch, "error": push.stderr.strip(), "body": body}

    try:
        gh = subprocess.run(
            [
                "gh", "pr", "create",
                "--base", base,
                "--head", branch,
                "--title", f"fix: {plan.title}",
                "--body", body,
            ],
            cwd=settings.repo_root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        ok = gh.returncode == 0 and bool(gh.stdout.strip())
        url = gh.stdout.strip().splitlines()[-1] if ok else _compare_url(base, branch)
        error = None if ok else gh.stderr.strip()
    except FileNotFoundError:
        url, error = _compare_url(base, branch), "gh CLI not installed; open the PR from the link"
    return {
        "mode": "live",
        "branch": branch,
        "base": base,
        "url": url,
        "commit": commit.stdout.strip(),
        "error": error,
        "body": body,
    }
