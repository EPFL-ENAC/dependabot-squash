import pytest

from dependabot_squash.discovery import load_targets

CONFIG = """version: 2
updates:
  - package-ecosystem: pip
    directory: /svc
    schedule: {interval: daily}
  - package-ecosystem: npm
    directory: /
    schedule: {interval: daily}
  - package-ecosystem: uv
    directory: /api
    schedule: {interval: daily}
"""


def _write_repo(tmp_path):
    github = tmp_path / ".github"
    github.mkdir()
    (github / "dependabot.yml").write_text(CONFIG)

    svc = tmp_path / "svc"
    svc.mkdir()
    (svc / "pyproject.toml").write_text('[tool.poetry.dependencies]\nrequests = "^2.0"\n')

    (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')

    api = tmp_path / "api"
    api.mkdir()
    (api / "pyproject.toml").write_text('[project]\nname = "api"\ndependencies = ["httpx>=0.27"]\n')


def test_pip_resolves_to_poetry(tmp_path):
    _write_repo(tmp_path)
    targets = load_targets(tmp_path)

    pip_target = next(t for t in targets if t.ecosystem == "pip")
    assert [h.__class__.__name__ for h in pip_target.handlers] == ["PyProjectPoetryHandler"]


def test_npm_and_uv_resolve(tmp_path):
    _write_repo(tmp_path)
    targets = load_targets(tmp_path)

    npm = next(t for t in targets if t.ecosystem == "npm")
    uv = next(t for t in targets if t.ecosystem == "uv")
    assert [h.__class__.__name__ for h in npm.handlers] == ["NpmHandler"]
    assert [h.__class__.__name__ for h in uv.handlers] == ["PyProjectPep621Handler"]


def test_missing_config_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_targets(tmp_path)
