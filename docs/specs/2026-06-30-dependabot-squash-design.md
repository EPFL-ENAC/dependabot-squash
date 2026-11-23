# Design: dependabot-squash

**Date:** 2026-06-30
**Status:** Approved (brainstorming complete; implementation plan pending)
**Repo:** `epfl-enac/dependabot-squash` — public, MIT

## Problem

Dependabot opens one PR per dependency. On an active repo that means a steady
drip of PRs, each with its own CI run and review. Merging them one at a time is
slow and noisy; the bumps are usually trivial and independent.

co2-calculator solved this locally with `scripts/consolidate-dependabot-updates.sh`,
a bash + embedded-python script that gathers every open Dependabot PR, applies all
the bumps to the working tree in one shot, regenerates lockfiles, and closes the
superseded PRs — leaving a single commit to merge.

That script is hardcoded to co2-calculator's layout (fixed npm/uv manifest paths,
npm + uv only). This project generalizes it into a standalone, installable CLI any
team repo can use, driven by the repo's own `.github/dependabot.yml`.

## Goals

- One command consolidates all open Dependabot PRs into a single local commit.
- Works in any repo without per-repo configuration beyond its existing
  `dependabot.yml`.
- Supports the ecosystems the team uses: **npm, uv, Poetry, pip (requirements.txt)**.
- Installable and maintainable as a shared tool (proper package, tests).

## Non-goals (deferred — YAGNI)

- Reusable GitHub Action / scheduled CI mode.
- Ecosystems beyond the four above (Go, Rust, Docker…). GitHub Actions PRs
  are the one exception: they are applied from the PR diff (see README).
- semver-major upgrade handling (the team's `dependabot.yml` ignores majors).
- pip-tools (`requirements.in` → `requirements.txt`) compilation.

## Distribution & invocation

- Installed with `uv tool install git+https://github.com/epfl-enac/dependabot-squash`.
- Exposes a `dependabot-squash` command and a short alias `dbsquash`.
- Run from inside the target repo's working tree.
- Requirements:
  - Python **3.11+** (for stdlib `tomllib`).
  - An authenticated **`gh`** CLI.
  - The relevant package managers on PATH for lockfile regen (`npm`, `uv`,
    `poetry`) — only those needed by the repo's ecosystems.

## Core flow

Mirrors the proven behavior of the original script:

1. **Discover** — parse `.github/dependabot.yml` → list of `(ecosystem, directory)`
   targets; resolve the manifest file(s) inside each directory.
2. **Refresh** — `git fetch --all --prune`.
3. **Fetch PRs** — `gh pr list --author "app/dependabot" --state open`.
4. **Parse** — for each PR, read the head-commit body's `updated-dependencies:`
   YAML trailer → direct dependencies `(name, version, type)`. Transitive-only
   bumps are skipped.
5. **Update manifests** — apply each bump to the working-tree manifest, preserving
   the existing version specifier style (`^`, `~`, `>=`, `==`, bare…).
6. **Regenerate lockfiles** — per ecosystem (see below). Skippable with
   `--skip-install`.
7. **Check supersession** — for each PR, confirm every direct dependency it ships
   is now at-or-above target in the working tree. Exit states per dep:
   satisfied / below-target / not-declared (removed).
8. **Confirm & close** — list closable vs. held-back PRs; on confirmation,
   comment + `gh pr close` each superseded PR.
9. **Write commit draft** — `.git/DEPENDABOT_SQUASH_MSG` listing the closed PRs,
   ready for `git commit -F`.

### Flags (carried over from the original)

| Flag | Effect |
| --- | --- |
| `--dry-run` | Show what would change; no edits, installs, or PR closures. |
| `--yes` / `-y` | Skip the interactive confirmation prompt. |
| `--skip-install` | Skip lockfile regeneration (run it yourself afterward). |
| `--close-removed` | Also close PRs whose package is no longer in any manifest. |

### Tradeoff (documented in README)

PRs are closed **before** the consolidation commit merges. If the consolidation is
abandoned, the closed PRs must be reopened with `gh pr reopen`.

## Architecture

A Python package with units that each have one purpose and a well-defined
interface, so they can be tested in isolation.

```
src/dependabot_squash/
  __init__.py
  cli.py                 # argparse + orchestration of the core-flow steps
  discovery.py           # dependabot.yml -> targets + resolved manifest paths
  dependabot_pr.py       # gh wrapper: list PRs, parse commit trailer, comment, close
  lockfiles.py           # per-ecosystem lockfile regeneration
  manifests/
    __init__.py          # handler registry + per-directory detection
    base.py              # ManifestHandler protocol
    npm.py               # package.json (JSON)
    pyproject_pep621.py  # [project.dependencies] (uv / PEP 621)
    pyproject_poetry.py  # [tool.poetry.dependencies]
    requirements.py      # requirements.txt
tests/
  ...                    # see Testing
```

### `manifests/base.py` — handler interface

Every manifest handler implements the same small protocol so the orchestrator
treats all ecosystems uniformly:

- `applies_to(directory) -> bool` — does this handler own a manifest in this dir?
- `read_dep(pkg) -> str | None` — current specifier for `pkg`, or `None` if absent.
- `update_dep(pkg, version) -> bool` — bump `pkg` to `version`, preserving the
  existing specifier prefix; return whether anything changed.
- `satisfies(pkg, target) -> Satisfaction` — one of `SATISFIED` / `BELOW` /
  `NOT_DECLARED`, comparing the working-tree specifier against `target`.

Adding a new ecosystem later = adding one handler + registering it. This is the
clean replacement for the original script's hardcoded `NPM_FILES` / `TOML_FILES`
lists.

### `discovery.py`

Parses `.github/dependabot.yml` (YAML) into targets. Maps each Dependabot
`package-ecosystem` to candidate manifest handlers:

- `npm` → `npm.py`
- `uv` → `pyproject_pep621.py`
- `pip` → `pyproject_poetry.py` **or** `requirements.py` **or** `pyproject_pep621.py`,
  resolved by which manifest actually exists in the directory (Dependabot's `pip`
  ecosystem covers pip/Poetry/pipenv).

YAML parsing uses `PyYAML` (a declared dependency).

### `lockfiles.py`

Regenerates lockfiles for the ecosystems that were touched:

| Ecosystem | Command |
| --- | --- |
| npm | `npm install --package-lock-only --ignore-scripts` |
| uv | `uv lock` |
| Poetry | `poetry lock --no-update` |
| requirements.txt | none — the pinned manifest *is* the lock; updated in place |

A missing package manager is reported as a warning, not a hard failure (matching
the original's `uv`-not-in-PATH behavior).

### `dependabot_pr.py`

Wraps `gh`: list open Dependabot PRs (number, title, head ref), read a PR head
commit body, post a "superseded" comment, close a PR. The `updated-dependencies:`
trailer parser lives here and is unit-tested against fixture commit bodies.

## Error handling

- Missing `.github/dependabot.yml` → clear message, exit non-zero.
- `gh` not installed / not authenticated → clear message, exit non-zero.
- No open Dependabot PRs → informational message, exit 0.
- A PR with no parsable `updated-dependencies:` block → held back, not closed.
- Package manager missing during regen → warning; manifests stay edited so the
  user can lock manually.
- Surface failures explicitly; never silently swallow a bump that didn't apply
  (skipped/transitive deps are reported).

## Testing

`pytest`, no network:

- **Manifest handlers** — fixture `package.json`, PEP 621 `pyproject.toml`, Poetry
  `pyproject.toml`, `requirements.txt`; assert `read_dep` / `update_dep`
  (specifier preservation) / `satisfies` across satisfied/below/removed cases.
- **Trailer parser** — sample Dependabot commit bodies (single dep, multiple deps,
  transitive-only, malformed) → expected `(name, version, type)` tuples.
- **Discovery** — sample `dependabot.yml`s → expected targets and handler
  resolution (including the `pip` → Poetry-vs-requirements disambiguation).
- **`gh` interactions** — mocked subprocess; assert correct commands issued, no
  live calls.

## README contents

- What it does and the supersession tradeoff.
- Install (`uv tool install …`) and requirements.
- Usage and the flag table.
- "How it works" walkthrough of the core flow.
- A copy-paste example **`.github/dependabot.yml`** based on co2-calculator's
  config: per-ecosystem entries, `cooldown` block with the supply-chain-defense
  rationale, `open-pull-requests-limit`, labels, and the semver-major `ignore`.

## Repo layout

```
dependabot-squash/
  pyproject.toml          # [project.scripts] dependabot-squash, dbsquash
  README.md
  LICENSE                 # MIT
  .github/dependabot.yml  # dogfoods its own recommended config
  docs/specs/2026-06-30-dependabot-squash-design.md  # this file
  src/dependabot_squash/  # (see Architecture)
  tests/
```
