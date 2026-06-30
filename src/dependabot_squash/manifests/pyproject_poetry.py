"""Handler for Poetry ``[tool.poetry.dependencies]`` (and group) tables."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .base import ManifestHandler

# Poetry specifier prefixes to preserve: caret, tilde, comparison operators.
_PREFIX = r"[\^~>=<]*"


class PyProjectPoetryHandler(ManifestHandler):
    @classmethod
    def discover(cls, directory: Path) -> list[ManifestHandler]:
        path = directory / "pyproject.toml"
        if not path.is_file():
            return []
        poetry = tomllib.loads(path.read_text()).get("tool", {}).get("poetry", {})
        if poetry.get("dependencies"):
            return [cls(path)]
        return []

    def read_dep(self, pkg: str) -> str | None:
        poetry = tomllib.loads(self.path.read_text()).get("tool", {}).get("poetry", {})
        tables = [poetry.get("dependencies", {})]
        for group in poetry.get("group", {}).values():
            tables.append(group.get("dependencies", {}))
        for table in tables:
            value = table.get(pkg)
            if isinstance(value, dict):
                value = value.get("version")
            if value:
                return value
        return None

    def update_dep(self, pkg: str, version: str) -> bool:
        text = self.path.read_text()
        pkg_re = re.escape(pkg)
        # Simple form:  requests = "^2.28.0"
        simple = re.compile(rf'(?m)^(\s*{pkg_re}\s*=\s*")({_PREFIX})[^"]*(")')
        new, count = simple.subn(rf"\g<1>\g<2>{version}\g<3>", text)
        if count:
            self.path.write_text(new)
            return True
        # Inline-table form:  fastapi = {version = "^0.100.0", extras = [...]}
        inline = re.compile(
            rf'(?m)^(\s*{pkg_re}\s*=\s*\{{[^}}]*?version\s*=\s*")({_PREFIX})[^"]*(")'
        )
        new, count = inline.subn(rf"\g<1>\g<2>{version}\g<3>", text)
        if count:
            self.path.write_text(new)
        return bool(count)
