"""Release metadata consistency guards.

These tests enforce the release invariant documented in RELEASING.md: the two
version markers (`pyproject.toml` and the generated bundle's `_template_version`)
and the most recent finalized `CHANGELOG.md` version must always agree. They run
in CI on every pull request, so a forgotten or partial version bump fails before
merge rather than surfacing during the release itself.
"""

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
TEMPLATE_VERSION_FILE = (
    REPO_ROOT / "template" / "{{.project_name}}" / "bundle_init_config.json.tmpl"
)
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _pyproject_version() -> str:
    """Return the `version` field from `pyproject.toml`."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["version"]


def _template_version() -> str:
    """Return the `_template_version` stamped into generated bundles."""
    text = TEMPLATE_VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'"_template_version":\s*"([^"]+)"', text)
    assert match is not None, "_template_version marker not found"
    return match.group(1)


def _latest_changelog_version() -> str:
    """Return the most recent finalized version heading in the changelog.

    Skips the `[Unreleased]` heading and returns the first `## [X.Y.Z] - DATE`
    entry below it.
    """
    text = CHANGELOG.read_text(encoding="utf-8")
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)
    assert match is not None, "no finalized version heading found in CHANGELOG.md"
    return match.group(1)


def test_version_markers_are_semver():
    """Both version markers are well-formed semantic versions."""
    assert _SEMVER.match(_pyproject_version())
    assert _SEMVER.match(_template_version())


def test_version_markers_agree():
    """The two version markers never drift apart."""
    assert _pyproject_version() == _template_version(), (
        "Version drift: pyproject.toml "
        f"({_pyproject_version()}) != _template_version "
        f"({_template_version()}). Bump both (see RELEASING.md)."
    )


def test_version_matches_latest_changelog():
    """The version markers match the latest finalized changelog entry.

    This catches the case where the changelog was finalized to a new version but
    the markers were not bumped (or the reverse), and the case where neither was
    touched for a release.
    """
    assert _pyproject_version() == _latest_changelog_version(), (
        f"Version markers ({_pyproject_version()}) do not match the latest "
        f"CHANGELOG.md entry ({_latest_changelog_version()}). Finalize the "
        "changelog and bump both markers together (see RELEASING.md)."
    )


def test_unreleased_section_present():
    """The changelog keeps an `[Unreleased]` section for in-flight work."""
    text = CHANGELOG.read_text(encoding="utf-8")
    assert re.search(r"^## \[Unreleased\]", text, re.MULTILINE), (
        "CHANGELOG.md must keep a `## [Unreleased]` section at the top "
        "(re-add it when finalizing a release; see RELEASING.md)."
    )
