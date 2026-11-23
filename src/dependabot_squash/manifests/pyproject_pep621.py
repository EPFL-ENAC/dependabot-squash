"""Handler for PEP 621 dependencies and PEP 735 ``[dependency-groups]`` (uv, pyproject)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .base import ManifestHandler

# Operators we rewrite; mirrors the single-bound bumps Dependabot emits.
_OPS = r"==|>=|~=|>|<=|<"


def _collect(data: dict) -> list[str]:
    # update_dep rewrites the whole file, so read_dep must see every table it can
    # touch; otherwise uv dev deps read as "removed" after being bumped.
    project = data.get("project", {})
    reqs = list(project.get("dependencies", []))
    groups = [*project.get("optional-dependencies", {}).values(),
              *data.get("dependency-groups", {}).values()]
    for group in groups:
        # PEP 735 groups may hold {include-group = "..."} tables, not requirements.
        reqs.extend(r for r in group if isinstance(r, str))
    return reqs


class PyProjectPep621Handler(ManifestHandler):
    @classmethod
    def discover(cls, directory: Path) -> list[ManifestHandler]:
        path = directory / "pyproject.toml"
        if not path.is_file():
            return []
        if _collect(tomllib.loads(path.read_text())):
            return [cls(path)]
        return []

    def _requirements(self) -> list[str]:
        return _collect(tomllib.loads(self.path.read_text()))

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
