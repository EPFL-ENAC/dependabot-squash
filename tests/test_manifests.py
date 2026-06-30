import json

from dependabot_squash.manifests.base import Satisfaction
from dependabot_squash.manifests.npm import NpmHandler
from dependabot_squash.manifests.pyproject_pep621 import PyProjectPep621Handler
from dependabot_squash.manifests.pyproject_poetry import PyProjectPoetryHandler
from dependabot_squash.manifests.requirements import RequirementsHandler


def test_npm_read_update_satisfies(tmp_path):
    path = tmp_path / "package.json"
    path.write_text(
        json.dumps(
            {"dependencies": {"react": "^18.2.0"}, "devDependencies": {"vite": "5.0.0"}}
        )
    )
    handler = NpmHandler(path)

    assert handler.read_dep("react") == "^18.2.0"
    assert handler.satisfies("react", "18.2.0") is Satisfaction.SATISFIED
    assert handler.satisfies("react", "19.0.0") is Satisfaction.BELOW
    assert handler.satisfies("missing", "1.0.0") is Satisfaction.NOT_DECLARED

    assert handler.update_dep("react", "18.3.1") is True
    assert json.loads(path.read_text())["dependencies"]["react"] == "^18.3.1"
    # bare specifier stays bare
    assert handler.update_dep("vite", "5.1.0") is True
    assert json.loads(path.read_text())["devDependencies"]["vite"] == "5.1.0"


def test_npm_discover(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    assert len(NpmHandler.discover(tmp_path)) == 1
    assert NpmHandler.discover(tmp_path / "nope") == []


def test_pep621(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text(
        '[project]\nname = "x"\n'
        'dependencies = ["fastapi>=0.100.0", "httpx[http2]>=0.27.0"]\n'
    )
    handlers = PyProjectPep621Handler.discover(tmp_path)
    assert len(handlers) == 1
    handler = handlers[0]

    assert handler.satisfies("fastapi", "0.100.0") is Satisfaction.SATISFIED
    assert handler.satisfies("fastapi", "0.110.0") is Satisfaction.BELOW
    # prefix-name guard: httpx-utils must not match httpx
    assert handler.read_dep("fastapi-utils") is None

    assert handler.update_dep("fastapi", "0.110.0") is True
    assert ">=0.110.0" in path.read_text()
    assert handler.update_dep("httpx", "0.28.0") is True
    assert "httpx[http2]>=0.28.0" in path.read_text()


def test_poetry(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text(
        "[tool.poetry.dependencies]\n"
        'python = "^3.11"\n'
        'requests = "^2.28.0"\n'
        'fastapi = {version = "^0.100.0", extras = ["all"]}\n'
    )
    handlers = PyProjectPoetryHandler.discover(tmp_path)
    assert len(handlers) == 1
    handler = handlers[0]

    assert handler.read_dep("requests") == "^2.28.0"
    assert handler.read_dep("fastapi") == "^0.100.0"

    assert handler.update_dep("requests", "2.31.0") is True
    assert 'requests = "^2.31.0"' in path.read_text()
    assert handler.update_dep("fastapi", "0.110.0") is True
    assert '"^0.110.0"' in path.read_text()


def test_requirements(tmp_path):
    path = tmp_path / "requirements.txt"
    path.write_text("requests==2.28.0\nhttpx>=0.27.0  # keep comment\n")
    handlers = RequirementsHandler.discover(tmp_path)
    assert len(handlers) == 1
    handler = handlers[0]

    assert handler.read_dep("requests") == "==2.28.0"
    assert handler.satisfies("requests", "2.28.0") is Satisfaction.SATISFIED

    assert handler.update_dep("requests", "2.31.0") is True
    assert "requests==2.31.0" in path.read_text()
    assert handler.update_dep("httpx", "0.28.0") is True
    text = path.read_text()
    assert "httpx>=0.28.0" in text
    assert "# keep comment" in text
