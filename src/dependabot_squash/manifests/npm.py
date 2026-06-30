"""Handler for npm ``package.json`` manifests."""

from __future__ import annotations

import json
from pathlib import Path

from .base import ManifestHandler, split_specifier

_SECTIONS = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")


class NpmHandler(ManifestHandler):
    @classmethod
    def discover(cls, directory: Path) -> list[ManifestHandler]:
        path = directory / "package.json"
        return [cls(path)] if path.is_file() else []

    def _load(self) -> dict:
        return json.loads(self.path.read_text())

    def read_dep(self, pkg: str) -> str | None:
        data = self._load()
        for section in _SECTIONS:
            spec = data.get(section, {}).get(pkg)
            if spec:
                return spec
        return None

    def update_dep(self, pkg: str, version: str) -> bool:
        data = self._load()
        changed = False
        for section in _SECTIONS:
            if pkg in data.get(section, {}):
                prefix, _ = split_specifier(data[section][pkg])
                data[section][pkg] = f"{prefix}{version}"
                changed = True
        if changed:
            self.path.write_text(json.dumps(data, indent=2) + "\n")
        return changed
