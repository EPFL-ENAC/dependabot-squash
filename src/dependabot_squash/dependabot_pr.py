"""GitHub (``gh``) and git interactions for Dependabot PRs, plus the trailer parser."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass

_NAME_RE = re.compile(r"^- dependency-name:")
_VERSION_RE = re.compile(r"^\s+dependency-version:")
_TYPE_RE = re.compile(r"^\s+dependency-type:")


@dataclass
class Dep:
    name: str
    version: str
    type: str


@dataclass
class PullRequest:
    number: int
    title: str
    head_ref: str


def _gh(args: list[str]) -> str:
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


def list_open_prs() -> list[PullRequest]:
    out = _gh(
        [
            "pr", "list",
            "--author", "app/dependabot",
            "--state", "open",
            "--json", "number,title,headRefName",
        ]
    )
    return [
        PullRequest(p["number"], p["title"], p["headRefName"])
        for p in json.loads(out or "[]")
    ]


def commit_body(ref: str) -> str:
    return subprocess.run(
        ["git", "log", "-1", "--format=%B", ref], capture_output=True, text=True
    ).stdout


def comment(number: int, body: str) -> None:
    _gh(["pr", "comment", str(number), "--body", body])


def close(number: int) -> None:
    _gh(["pr", "close", str(number)])


def _value(line: str) -> str:
    return line.split(":", 1)[1].strip().strip('"')


def parse_updated_dependencies(body: str) -> list[Dep]:
    """Parse the ``updated-dependencies:`` YAML trailer, keeping direct deps only."""
    deps: list[Dep] = []
    in_block = False
    name = version = dtype = ""

    def flush() -> None:
        nonlocal name, version, dtype
        if name and version and dtype.startswith("direct:"):
            deps.append(Dep(name, version, dtype))
        name = version = dtype = ""

    for line in body.splitlines():
        if line.startswith("updated-dependencies:"):
            in_block = True
            continue
        if in_block and line and not line[0].isspace() and not line.startswith("-"):
            in_block = False
        if not in_block:
            continue
        if _NAME_RE.match(line):
            flush()
            name = _value(line)
        elif _VERSION_RE.match(line):
            version = _value(line)
        elif _TYPE_RE.match(line):
            dtype = _value(line)
    flush()
    return deps
