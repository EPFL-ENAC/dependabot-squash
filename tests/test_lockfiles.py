"""A failed lock command must surface as a warning, never vanish."""

from __future__ import annotations

import subprocess
from pathlib import Path

from dependabot_squash import lockfiles
from dependabot_squash.discovery import Target


def _fake_run(returncode: int, stderr: str):
    def run(cmd, cwd, check, capture_output, text):
        return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)

    return run


def test_npm_failure_is_reported(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(lockfiles.shutil, "which", lambda _: "/usr/bin/npm")
    monkeypatch.setattr(
        lockfiles.subprocess,
        "run",
        _fake_run(1, "npm error code ETARGET\nnpm error notarget No matching version found\n"),
    )
    warnings = lockfiles.regenerate_for(Target("npm", "/frontend/storybook", []), tmp_path)
    assert len(warnings) == 1
    assert "/frontend/storybook" in warnings[0]
    assert "ETARGET" in warnings[0]


def test_npm_success_is_silent(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(lockfiles.shutil, "which", lambda _: "/usr/bin/npm")
    monkeypatch.setattr(lockfiles.subprocess, "run", _fake_run(0, ""))
    assert lockfiles.regenerate_for(Target("npm", "/frontend", []), tmp_path) == []
