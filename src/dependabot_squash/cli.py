"""Command-line entry point: orchestrates the consolidation flow."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import dependabot_pr as gh
from . import lockfiles
from .dependabot_pr import Dep, PullRequest
from .discovery import Target, load_targets
from .manifests import ManifestHandler, Satisfaction

_CLOSE_COMMENT = (
    "Superseded by local consolidation of dependabot updates; the bump in this PR "
    "is already present in the working tree. Closing."
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="dependabot-squash",
        description="Consolidate open Dependabot PRs into a single local commit.",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would change; make no edits, installs, or PR closures.")
    p.add_argument("--yes", "-y", action="store_true",
                   help="Skip the confirmation prompt.")
    p.add_argument("--skip-install", action="store_true",
                   help="Skip lockfile regeneration.")
    p.add_argument("--close-removed", action="store_true",
                   help="Also close PRs whose package is no longer in any manifest.")
    return p.parse_args(argv)


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if result.returncode != 0:
        sys.exit("Not inside a git repository.")
    return Path(result.stdout.strip())


def _gather_pr_deps(prs: list[PullRequest]) -> dict[int, list[Dep]]:
    return {
        pr.number: gh.parse_updated_dependencies(gh.commit_body(f"origin/{pr.head_ref}"))
        for pr in prs
    }


def _apply_updates(
    pr_deps: dict[int, list[Dep]],
    handlers: list[tuple[Target, ManifestHandler]],
    dry_run: bool,
) -> tuple[int, int, list[Target]]:
    updated = skipped = 0
    touched: list[Target] = []
    seen: set[tuple[str, str]] = set()
    for deps in pr_deps.values():
        for dep in deps:
            if (dep.name, dep.version) in seen:
                continue
            seen.add((dep.name, dep.version))
            if dry_run:
                print(f"  [dry-run] would update: {dep.name} -> {dep.version}")
                continue
            hit = False
            for target, handler in handlers:
                if handler.update_dep(dep.name, dep.version):
                    print(f"    ✓ {handler.path}: {dep.name} -> {dep.version}")
                    hit = True
                    if target not in touched:
                        touched.append(target)
            if hit:
                updated += 1
            else:
                print(f"    ↷ {dep.name} {dep.version}: not in any manifest (likely transitive)")
                skipped += 1
    return updated, skipped, touched


def _best_state(dep: Dep, handlers: list[tuple[Target, ManifestHandler]]) -> Satisfaction:
    found = False
    for _, handler in handlers:
        state = handler.satisfies(dep.name, dep.version)
        if state is Satisfaction.SATISFIED:
            return Satisfaction.SATISFIED
        if state is Satisfaction.BELOW:
            found = True
    return Satisfaction.BELOW if found else Satisfaction.NOT_DECLARED


def _classify(
    prs: list[PullRequest],
    pr_deps: dict[int, list[Dep]],
    handlers: list[tuple[Target, ManifestHandler]],
    close_removed: bool,
) -> tuple[list[tuple[int, str]], list[str]]:
    closable: list[tuple[int, str]] = []
    hold: list[str] = []
    for pr in prs:
        deps = pr_deps.get(pr.number, [])
        if not deps:
            hold.append(f"#{pr.number} — no parsable dependency block")
            continue
        missing: list[str] = []
        for dep in deps:
            state = _best_state(dep, handlers)
            if state is Satisfaction.SATISFIED:
                continue
            if state is Satisfaction.NOT_DECLARED:
                if not close_removed:
                    missing.append(f"{dep.name} (removed)")
            else:
                missing.append(f"{dep.name}@{dep.version}")
        if missing:
            hold.append(f"#{pr.number} — still needs: {', '.join(missing)}")
        else:
            closable.append((pr.number, pr.title))
    return closable, hold


def _report(closable: list[tuple[int, str]], hold: list[str]) -> None:
    print(f"\nWill close: {len(closable)}")
    for num, title in closable:
        print(f"  #{num} — {title}")
    print(f"\nLeft open: {len(hold)}")
    for line in hold:
        print(f"  {line}")


def _confirm(count: int) -> bool:
    answer = input(f"\nClose {count} PR(s) and write commit message? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def _close_and_write_msg(closable: list[tuple[int, str]], repo_root: Path) -> None:
    for num, _ in closable:
        gh.comment(num, _CLOSE_COMMENT)
        gh.close(num)
        print(f"  ✓ closed #{num}")
    git_dir = subprocess.run(
        ["git", "rev-parse", "--git-dir"], capture_output=True, text=True
    ).stdout.strip()
    msg_file = Path(git_dir) / "DEPENDABOT_SQUASH_MSG"
    lines = [
        "chore(deps): consolidate dependency updates",
        "",
        f"Superseded {len(closable)} dependabot PR(s):",
        "",
        *[f"- #{num} {title}" for num, title in closable],
    ]
    msg_file.write_text("\n".join(lines) + "\n")
    print(f"\nCommit message draft: {msg_file}")
    print(f"\nNext steps:\n  git add -A\n  git commit -F {msg_file}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if not shutil.which("gh"):
        sys.exit("gh CLI is required.")
    repo_root = _repo_root()
    try:
        targets = load_targets(repo_root)
    except FileNotFoundError as exc:
        sys.exit(str(exc))

    print("Refreshing remote refs...")
    subprocess.run(["git", "fetch", "--all", "--prune"], capture_output=True)

    prs = gh.list_open_prs()
    if not prs:
        print("No open dependabot PRs. Nothing to consolidate.")
        return 0

    pr_deps = _gather_pr_deps(prs)
    handlers = [(t, h) for t in targets for h in t.handlers]

    print("\n=== Consolidating dependabot updates ===")
    updated, skipped, touched = _apply_updates(pr_deps, handlers, args.dry_run)
    print(f"\nManifest changes: {updated} updated, {skipped} skipped")

    if args.dry_run:
        print("\n=== DRY RUN — exiting before installs and PR closures ===")
        return 0

    if not args.skip_install and updated:
        print("\n=== Regenerating lockfiles ===")
        for target in touched:
            for warning in lockfiles.regenerate_for(target, repo_root):
                print(f"  ⚠ {warning}")

    closable, hold = _classify(prs, pr_deps, handlers, args.close_removed)
    _report(closable, hold)

    if not closable:
        print("\nNo PRs to close. Manifest edits remain in your working tree.")
        return 0
    if not args.yes and not _confirm(len(closable)):
        print("Aborted. No PRs were closed.")
        return 0

    _close_and_write_msg(closable, repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
