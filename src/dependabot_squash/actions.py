"""GitHub Actions bumps, applied from the PR's own diff.

Dependabot pins actions by commit SHA. The trailer gives only a version, so the
new pin cannot be rebuilt from it: the PR diff already holds it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .dependabot_pr import PullRequest


def is_actions_pr(pr: PullRequest) -> bool:
    # Matches any branch-name separator Dependabot is configured with.
    return "github_actions" in pr.head_ref


def pr_diff(pr: PullRequest) -> str:
    """Changes the PR adds, from its merge base (the tip may be a base merge)."""
    ref = f"origin/{pr.head_ref}"
    return subprocess.run(
        ["git", "diff", f"HEAD...{ref}"], check=True, capture_output=True, text=True
    ).stdout


def _git_apply(diff: str, repo_root: Path, *flags: str) -> bool:
    proc = subprocess.run(
        ["git", "apply", *flags], input=diff, cwd=repo_root, capture_output=True, text=True
    )
    return proc.returncode == 0


def apply(diff: str, repo_root: Path) -> bool:
    """Apply the diff; on a conflict git changes nothing and this returns False."""
    return _git_apply(diff, repo_root)


def is_applied(diff: str, repo_root: Path) -> bool:
    """True when the working tree already holds the diff (it reverses cleanly)."""
    return _git_apply(diff, repo_root, "--reverse", "--check")
