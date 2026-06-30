"""Per-ecosystem lockfile regeneration."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .discovery import Target


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=False, capture_output=True)


def regenerate_for(target: Target, repo_root: Path) -> list[str]:
    """Regenerate the lockfile for one touched target. Returns warning messages."""
    abs_dir = repo_root / target.directory.lstrip("/")

    if target.ecosystem == "npm":
        if not shutil.which("npm"):
            return [f"npm not on PATH — lockfile for {target.directory} not regenerated"]
        _run(["npm", "install", "--package-lock-only", "--ignore-scripts"], abs_dir)
    elif target.ecosystem == "uv":
        if not shutil.which("uv"):
            return [f"uv not on PATH — lockfile for {target.directory} not regenerated"]
        _run(["uv", "lock"], abs_dir)
    elif target.ecosystem == "pip" and (abs_dir / "poetry.lock").is_file():
        if not shutil.which("poetry"):
            return [f"poetry not on PATH — lockfile for {target.directory} not regenerated"]
        _run(["poetry", "lock", "--no-update"], abs_dir)
    # requirements.txt (and pip without poetry.lock) is its own lock — nothing to do.
    return []
