"""Manifest handler registry and Dependabot-ecosystem resolution."""

from __future__ import annotations

from pathlib import Path

from .base import ManifestHandler, Satisfaction
from .npm import NpmHandler
from .pyproject_pep621 import PyProjectPep621Handler
from .pyproject_poetry import PyProjectPoetryHandler
from .requirements import RequirementsHandler

# Dependabot package-ecosystem -> ordered candidate handler classes.
# Dependabot's "pip" covers pip / Poetry / pipenv; resolve by which file exists.
_ECOSYSTEM_HANDLERS: dict[str, list[type[ManifestHandler]]] = {
    "npm": [NpmHandler],
    "uv": [PyProjectPep621Handler],
    "pip": [PyProjectPoetryHandler, RequirementsHandler, PyProjectPep621Handler],
}


def handlers_for(ecosystem: str, directory: Path) -> list[ManifestHandler]:
    """Handler instances for the manifests actually present in ``directory``."""
    found: list[ManifestHandler] = []
    for handler_cls in _ECOSYSTEM_HANDLERS.get(ecosystem, []):
        found.extend(handler_cls.discover(directory))
    return found


__all__ = ["ManifestHandler", "Satisfaction", "handlers_for"]
