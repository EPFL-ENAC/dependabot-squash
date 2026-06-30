# dependabot-squash

Consolidate every open Dependabot PR into a **single local commit**, then close the
superseded PRs. Instead of merging dependency bumps one PR (and one CI run) at a
time, you get one commit to review and merge.

It reads your repo's own `.github/dependabot.yml` to know which ecosystems and
directories to touch — no extra configuration.

## What it does

1. Parses `.github/dependabot.yml` to find the manifests to operate on.
2. Lists open Dependabot PRs (`gh`).
3. Reads each PR's `updated-dependencies:` trailer to learn the direct bumps.
4. Applies every bump to your working-tree manifests, preserving version specifiers.
5. Regenerates lockfiles.
6. Works out which PRs are now fully satisfied by the working tree.
7. Comments on and closes those PRs.
8. Writes a ready-to-use commit message to `.git/DEPENDABOT_SQUASH_MSG`.

Supported ecosystems: **npm**, **uv**, **Poetry**, and **pip** (`requirements*.txt`).

> **Tradeoff:** PRs are closed *before* your consolidation commit merges. If you
> abandon the consolidation, reopen them with `gh pr reopen <number>`.

## Requirements

- Python **3.11+**
- An authenticated [`gh`](https://cli.github.com/) CLI
- The package managers for your ecosystems on `PATH` (`npm`, `uv`, and/or
  `poetry`) — only needed for lockfile regeneration

## Install

```bash
uv tool install git+https://github.com/epfl-enac/dependabot-squash
```

This puts two equivalent commands on your `PATH`: `dependabot-squash` and the short
alias `dbsquash`.

## Usage

Run it from inside the target repo:

```bash
dependabot-squash            # interactive: review, confirm, close
dependabot-squash --dry-run  # show what would change, touch nothing
```

| Flag | Effect |
| --- | --- |
| `--dry-run` | Show what would change; make no edits, installs, or PR closures. |
| `--yes`, `-y` | Skip the confirmation prompt. |
| `--skip-install` | Skip lockfile regeneration (run it yourself afterward). |
| `--close-removed` | Also close PRs whose package is no longer in any manifest. |

After it finishes:

```bash
git add -A
git commit -F .git/DEPENDABOT_SQUASH_MSG
```

## Configuring Dependabot

`dependabot-squash` is driven entirely by your `.github/dependabot.yml`. Below is a
recommended starting point (one `updates` entry per ecosystem + directory). The
`cooldown` block is supply-chain defense-in-depth: newly published versions are
quarantined before Dependabot opens a PR, so most malicious releases (compromised
maintainer tokens, typosquats, worm republishes) get flagged or yanked within days
before they reach you. The tradeoff is that legitimate releases lag a few days.

```yaml
version: 2
updates:
  - package-ecosystem: "uv" # or "pip" for Poetry / requirements.txt
    directory: "/backend"
    schedule:
      interval: "daily"
    target-branch: "dev" # keep bump PRs off your release branch
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
    open-pull-requests-limit: 10 # absorb the burst after a cooldown window
    labels:
      - "dependencies"
    ignore:
      - dependency-name: "*"
        update-types: ["version-update:semver-major"]

  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "daily"
    target-branch: "dev"
    cooldown:
      default-days: 7
      semver-major-days: 30
      semver-minor-days: 7
      semver-patch-days: 3
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
    ignore:
      - dependency-name: "*"
        update-types: ["version-update:semver-major"]
```

Add one entry per manifest directory (e.g. `/`, `/frontend`, `/docs`). The
`directory` values are exactly what `dependabot-squash` walks.

## How specifiers are handled

Bumps preserve your existing specifier style — `^1.2.3` stays caret, `>=1.2.3`
stays a lower bound, `==1.2.3` stays pinned, a bare `1.2.3` stays bare. Only the
version number is rewritten.

## Out of scope

A reusable GitHub Action, ecosystems beyond the four above, semver-major upgrades,
and pip-tools (`requirements.in` → `requirements.txt`) compilation are not handled.

## Development

```bash
uv run --extra dev pytest      # run the test suite (no network; gh is mocked)
uv run --extra dev ruff check  # lint
```

## License

[MIT](LICENSE)
