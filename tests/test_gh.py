from dataclasses import dataclass

import dependabot_squash.dependabot_pr as gh


@dataclass
class FakeResult:
    stdout: str = ""


def test_list_open_prs(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return FakeResult(
            stdout='[{"number": 5, "title": "bump react", '
            '"headRefName": "dependabot/npm_and_yarn/react"}]'
        )

    monkeypatch.setattr(gh.subprocess, "run", fake_run)
    prs = gh.list_open_prs()

    assert captured["args"][:2] == ["gh", "pr"]
    assert "--author" in captured["args"]
    assert prs == [gh.PullRequest(5, "bump react", "dependabot/npm_and_yarn/react")]


def test_close_issues_gh_command(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return FakeResult()

    monkeypatch.setattr(gh.subprocess, "run", fake_run)
    gh.close(42)

    assert captured["args"] == ["gh", "pr", "close", "42"]


def test_comment_issues_gh_command(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        return FakeResult()

    monkeypatch.setattr(gh.subprocess, "run", fake_run)
    gh.comment(42, "hello")

    assert captured["args"] == ["gh", "pr", "comment", "42", "--body", "hello"]
