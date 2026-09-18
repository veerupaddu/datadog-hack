"""Step 6b: apply an approved patch, but only inside the dummy app."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import settings
from .planner import FixPlan

ALLOWED_PREFIX = "src/devprod/sample_app/"


class PatchRefused(RuntimeError):
    pass


def apply(plan: FixPlan) -> dict:
    if not plan.patch.file.startswith(ALLOWED_PREFIX):
        raise PatchRefused(f"refusing to edit {plan.patch.file} (outside {ALLOWED_PREFIX})")
    path: Path = settings.repo_root / plan.patch.file
    source = path.read_text(encoding="utf-8")
    if plan.patch.new in source:
        return {"applied": False, "reason": "already patched", "file": plan.patch.file}
    if plan.patch.old not in source:
        raise PatchRefused(f"patch target not found in {plan.patch.file}; the file has drifted")
    path.write_text(source.replace(plan.patch.old, plan.patch.new, 1), encoding="utf-8")
    return {"applied": True, "file": plan.patch.file, "diff": plan.patch.diff()}


def revert(plan: FixPlan) -> dict:
    path: Path = settings.repo_root / plan.patch.file
    source = path.read_text(encoding="utf-8")
    if plan.patch.new not in source:
        return {"reverted": False, "reason": "patch not present"}
    path.write_text(source.replace(plan.patch.new, plan.patch.old, 1), encoding="utf-8")
    return {"reverted": True, "file": plan.patch.file}


def run_tests(selection: str = "tests") -> dict:
    proc = subprocess.run(
        ["python", "-m", "pytest", selection, "-q"],
        cwd=settings.repo_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    tail = (proc.stdout or proc.stderr).strip().splitlines()[-12:]
    return {"passed": proc.returncode == 0, "output": "\n".join(tail)}
