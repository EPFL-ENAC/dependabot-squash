"""Per-ecosystem lockfile regeneration."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .discovery import Target


def _run(cmd: list[str], cwd: Path) -> str | None:
    """Run a lock command; return its first error lines on failure, None on success."""
    proc = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    if proc.returncode == 0:
        return None
    lines = [line for line in (proc.stderr or proc.stdout).splitlines() if line.strip()]
    return " | ".join(lines[:3]) or f"exit code {proc.returncode}"


def regenerate_for(target: Target, repo_root: Path) -> list[str]:
    """Regenerate the lockfile for one touched target. Returns warning messages."""
    abs_dir = repo_root / target.directory.lstrip("/")
    # A failed regen used to be swallowed here; the stale lockfile then broke
    # `npm ci` in Docker days later (co2-calculator 71bb531e5, 539fa0096).
    failure: str | None = None

    if target.ecosystem == "npm":
        if not shutil.which("npm"):
            return [f"npm not on PATH — lockfile for {target.directory} not regenerated"]
        failure = _run(["npm", "install", "--package-lock-only", "--ignore-scripts"], abs_dir)
    elif target.ecosystem == "uv":
        if not shutil.which("uv"):
            return [f"uv not on PATH — lockfile for {target.directory} not regenerated"]
        failure = _run(["uv", "lock"], abs_dir)
    elif target.ecosystem == "pip" and (abs_dir / "poetry.lock").is_file():
        if not shutil.which("poetry"):
            return [f"poetry not on PATH — lockfile for {target.directory} not regenerated"]
        failure = _run(["poetry", "lock", "--no-update"], abs_dir)
    # requirements.txt (and pip without poetry.lock) is its own lock — nothing to do.
    if failure:
        return [f"lockfile for {target.directory} NOT regenerated: {failure}"]
    return []
