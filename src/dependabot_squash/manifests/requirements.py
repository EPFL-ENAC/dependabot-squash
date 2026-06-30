"""Handler for ``requirements*.txt`` pinned manifests.

The file is its own lockfile, so there is no separate regen step.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import ManifestHandler

_OPS = r"==|>=|~=|>|<=|<"


class RequirementsHandler(ManifestHandler):
    @classmethod
    def discover(cls, directory: Path) -> list[ManifestHandler]:
        return [cls(p) for p in sorted(directory.glob("requirements*.txt"))]

    def read_dep(self, pkg: str) -> str | None:
        pat = re.compile(rf"^\s*{re.escape(pkg)}(?:\[[^\]]+\])?\s*({_OPS})\s*([^\s#;]+)", re.I)
        for line in self.path.read_text().splitlines():
            m = pat.match(line)
            if m:
                return m.group(1) + m.group(2)
        return None

    def update_dep(self, pkg: str, version: str) -> bool:
        text = self.path.read_text()
        pat = re.compile(
            rf"(?im)^(\s*{re.escape(pkg)}(?:\[[^\]]+\])?\s*)({_OPS})(\s*)([^\s#;]+)"
        )
        new, count = pat.subn(rf"\g<1>\g<2>\g<3>{version}", text)
        if count:
            self.path.write_text(new)
        return bool(count)
