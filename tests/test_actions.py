import subprocess
from pathlib import Path

from dependabot_squash import actions
from dependabot_squash.dependabot_pr import PullRequest

OLD = "      - uses: astral-sh/setup-uv@38f3f10 # v4\n"
NEW = "      - uses: astral-sh/setup-uv@1db35dd # v10.4.0\n"
REF = "dependabot/github_actions/dev/astral-sh/setup-uv-10.4.0"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _repo_with_pr(tmp_path: Path) -> tuple[Path, Path, PullRequest]:
    """A repo whose `origin/<REF>` holds one Dependabot-style workflow bump."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "ci@example.invalid")
    _git(tmp_path, "config", "user.name", "ci")
    wf = tmp_path / ".github" / "workflows" / "ci.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("jobs:\n  t:\n    steps:\n" + OLD)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "switch", "-q", "-c", "bump")
    wf.write_text(wf.read_text().replace(OLD, NEW))
    _git(tmp_path, "commit", "-qam", "bump")
    _git(tmp_path, "update-ref", f"refs/remotes/origin/{REF}", "HEAD")
    _git(tmp_path, "switch", "-q", "main")
    return tmp_path, wf, PullRequest(3353, "bump setup-uv", REF)


def test_is_actions_pr():
    assert actions.is_actions_pr(PullRequest(1, "t", REF))
    assert not actions.is_actions_pr(PullRequest(2, "t", "dependabot/uv/backend/dev/ruff-0.17.6"))


def test_apply_pr_diff(tmp_path, monkeypatch):
    repo, wf, pr = _repo_with_pr(tmp_path)
    monkeypatch.chdir(repo)
    diff = actions.pr_diff(pr)

    assert not actions.is_applied(diff, repo)
    assert actions.apply(diff, repo)
    assert NEW in wf.read_text()
    assert actions.is_applied(diff, repo)


def test_conflicting_diff_changes_nothing(tmp_path, monkeypatch):
    repo, wf, pr = _repo_with_pr(tmp_path)
    monkeypatch.chdir(repo)
    diff = actions.pr_diff(pr)
    edited = wf.read_text().replace(OLD, "      - uses: astral-sh/setup-uv@abc # v5\n")
    wf.write_text(edited)

    assert not actions.apply(diff, repo)
    assert wf.read_text() == edited
    assert not actions.is_applied(diff, repo)
