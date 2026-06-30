"""Resolve consolidation targets from a repo's ``.github/dependabot.yml``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .manifests import ManifestHandler, handlers_for


@dataclass
class Target:
    """One Dependabot update entry mapped to concrete manifest handlers."""

    ecosystem: str
    directory: str
    handlers: list[ManifestHandler]


def _config_path(repo_root: Path) -> Path:
    for name in ("dependabot.yml", "dependabot.yaml"):
        candidate = repo_root / ".github" / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"No .github/dependabot.yml found under {repo_root}")


def _directories(update: dict) -> list[str]:
    if update.get("directories"):
        return list(update["directories"])
    return [update.get("directory", "/")]


def load_targets(repo_root: Path) -> list[Target]:
    """Parse dependabot config into targets with resolved manifest handlers."""
    data = yaml.safe_load(_config_path(repo_root).read_text()) or {}
    targets: list[Target] = []
    seen: set[tuple[str, str]] = set()
    for update in data.get("updates", []):
        ecosystem = update.get("package-ecosystem")
        for directory in _directories(update):
            key = (ecosystem, directory)
            if key in seen:
                continue
            seen.add(key)
            abs_dir = repo_root / directory.lstrip("/")
            targets.append(Target(ecosystem, directory, handlers_for(ecosystem, abs_dir)))
    return targets
