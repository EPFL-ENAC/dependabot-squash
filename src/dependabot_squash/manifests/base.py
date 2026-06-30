"""Shared manifest-handler contract and version helpers.

Every handler operates on one manifest file and exposes the same small surface so
the orchestrator can treat all ecosystems uniformly.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path

_PREFIX_RE = re.compile(r"^([=^~><!\s]*)")


class Satisfaction(Enum):
    """Whether a declared dependency meets a target version."""

    SATISFIED = "satisfied"
    BELOW = "below"
    NOT_DECLARED = "not_declared"


def split_specifier(spec: str) -> tuple[str, str]:
    """Split a specifier into (prefix, version), e.g. ``^1.2.3`` -> (``^``, ``1.2.3``)."""
    spec = spec.strip()
    m = _PREFIX_RE.match(spec)
    prefix = m.group(1).strip()
    return prefix, spec[m.end() :]


def version_tuple(value: str) -> tuple[int, ...]:
    """Numeric release tuple from a version/specifier; pre-release/build tail dropped."""
    value = re.sub(r"^[^0-9]*", "", value)
    value = re.sub(r"[^0-9.].*$", "", value)
    return tuple(int(x) for x in value.split(".") if x.isdigit())


class ManifestHandler:
    """Base class. One instance wraps one manifest file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def discover(cls, directory: Path) -> list[ManifestHandler]:
        """Return handler instances for the manifests this class owns in ``directory``."""
        raise NotImplementedError

    def read_dep(self, pkg: str) -> str | None:
        """Current specifier for ``pkg`` (e.g. ``>=2.0``), or ``None`` if absent."""
        raise NotImplementedError

    def update_dep(self, pkg: str, version: str) -> bool:
        """Bump ``pkg`` to ``version``, preserving the specifier prefix. Return if changed."""
        raise NotImplementedError

    def satisfies(self, pkg: str, target: str) -> Satisfaction:
        """Compare the working-tree specifier for ``pkg`` against ``target``."""
        spec = self.read_dep(pkg)
        if spec is None:
            return Satisfaction.NOT_DECLARED
        if version_tuple(spec) >= version_tuple(target):
            return Satisfaction.SATISFIED
        return Satisfaction.BELOW
