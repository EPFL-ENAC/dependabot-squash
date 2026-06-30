"""Handler for PEP 621 ``[project.dependencies]`` (uv / standard pyproject)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .base import ManifestHandler

# Operators we rewrite; mirrors the single-bound bumps Dependabot emits.
_OPS = r"==|>=|~=|>|<=|<"


class PyProjectPep621Handler(ManifestHandler):
    @classmethod
    def discover(cls, directory: Path) -> list[ManifestHandler]:
        path = directory / "pyproject.toml"
        if not path.is_file():
            return []
        project = tomllib.loads(path.read_text()).get("project", {})
        if project.get("dependencies") or project.get("optional-dependencies"):
            return [cls(path)]
        return []

    def _requirements(self) -> list[str]:
        project = tomllib.loads(self.path.read_text()).get("project", {})
        reqs = list(project.get("dependencies", []))
        for group in project.get("optional-dependencies", {}).values():
            reqs.extend(group)
        return reqs

    def read_dep(self, pkg: str) -> str | None:
        # Lookahead guards against prefix matches (e.g. "fastapi" vs "fastapi-utils").
        pat = re.compile(rf"^\s*{re.escape(pkg)}(?:\[[^\]]+\])?\s*(?=[<>=!~;]|$)(.*)$", re.I)
        for req in self._requirements():
            m = pat.match(req)
            if m:
                return m.group(1).strip() or None
        return None

    def update_dep(self, pkg: str, version: str) -> bool:
        text = self.path.read_text()
        pat = re.compile(rf'"({re.escape(pkg)}(?:\[[^\]]+\])?)\s*({_OPS})\s*[^"]+"')
        new, count = pat.subn(rf'"\g<1>\g<2>{version}"', text)
        if count:
            self.path.write_text(new)
        return bool(count)
