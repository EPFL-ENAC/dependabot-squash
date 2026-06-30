from dependabot_squash.dependabot_pr import Dep, parse_updated_dependencies

SINGLE = """chore(deps): bump react

Bumps react from 18.2.0 to 18.3.1.

updated-dependencies:
- dependency-name: react
  dependency-version: 18.3.1
  dependency-type: direct:production
...

Signed-off-by: dependabot[bot]
"""

MULTIPLE = """chore(deps): bump the npm group

updated-dependencies:
- dependency-name: react
  dependency-version: 18.3.1
  dependency-type: direct:production
- dependency-name: vite
  dependency-version: 5.1.0
  dependency-type: direct:development
...
"""

TRANSITIVE_ONLY = """chore(deps): bump nested

updated-dependencies:
- dependency-name: left-pad
  dependency-version: 1.3.0
  dependency-type: indirect
...
"""

NO_BLOCK = """chore(deps): something

Just a plain message with no trailer.
"""


def test_single():
    assert parse_updated_dependencies(SINGLE) == [
        Dep("react", "18.3.1", "direct:production")
    ]


def test_multiple():
    assert parse_updated_dependencies(MULTIPLE) == [
        Dep("react", "18.3.1", "direct:production"),
        Dep("vite", "5.1.0", "direct:development"),
    ]


def test_transitive_only_filtered():
    assert parse_updated_dependencies(TRANSITIVE_ONLY) == []


def test_no_block():
    assert parse_updated_dependencies(NO_BLOCK) == []
