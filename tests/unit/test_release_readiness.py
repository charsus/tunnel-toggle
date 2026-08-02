"""Tests for public alpha release metadata and documentation."""

from __future__ import annotations

import tomllib
from pathlib import Path
from xml.etree import ElementTree

from tunnel_toggle import __version__

PROJECT_ROOT = Path(__file__).parents[2]

PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
README_PATH = PROJECT_ROOT / "README.md"
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"
SECURITY_PATH = PROJECT_ROOT / "SECURITY.md"
METAINFO_PATH = (
    PROJECT_ROOT / "packaging" / "io.github.charsus.TunnelToggle.metainfo.xml"
)


def load_pyproject() -> dict[str, object]:
    """Load the project's TOML metadata."""
    with PYPROJECT_PATH.open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)


def test_public_version_matches_package_version() -> None:
    """The build metadata and import package should agree."""
    pyproject = load_pyproject()
    project = pyproject["project"]

    assert isinstance(project, dict)
    assert project["version"] == "0.1.0a1"
    assert __version__ == "0.1.0a1"


def test_project_declares_public_repository_urls() -> None:
    """Package metadata should point to the intended public project."""
    pyproject = load_pyproject()
    project = pyproject["project"]

    assert isinstance(project, dict)

    urls = project["urls"]

    assert urls == {
        "Homepage": "https://github.com/charsus/tunnel-toggle",
        "Source": "https://github.com/charsus/tunnel-toggle",
        "Issues": "https://github.com/charsus/tunnel-toggle/issues",
        "Changelog": (
            "https://github.com/charsus/tunnel-toggle/blob/main/CHANGELOG.md"
        ),
    }


def test_readme_documents_current_installation_workflow() -> None:
    """Public documentation should describe the implemented installer."""
    readme = README_PATH.read_text(encoding="utf-8")

    assert "alpha software" in readme
    assert "python3 -m tunnel_toggle.local_installer install" in readme
    assert "python3 -m tunnel_toggle.local_installer uninstall" in readme
    assert "Installation instructions will be added" not in readme
    assert "private, pre-alpha development" not in readme


def test_changelog_contains_dated_alpha_release() -> None:
    """The first public alpha should have a stable release heading."""
    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

    assert "## [Unreleased]\n" in changelog
    assert "## [0.1.0-alpha] - 2026-08-02" in changelog
    assert (
        "[0.1.0-alpha]: "
        "https://github.com/charsus/tunnel-toggle/"
        "releases/tag/v0.1.0-alpha"
    ) in changelog


def test_security_policy_provides_private_reporting_path() -> None:
    """The policy should discourage public vulnerability disclosure."""
    security = SECURITY_PATH.read_text(encoding="utf-8")

    assert "GitHub private vulnerability reporting" in security
    assert "Do not publish vulnerability details" in security
    assert "contains no sensitive technical details" in security
    assert "local and unpublished" not in security


def test_appstream_declares_public_alpha_release() -> None:
    """AppStream metadata should identify the first public alpha."""
    root = ElementTree.parse(METAINFO_PATH).getroot()
    release = root.find("releases/release")

    assert release is not None
    assert release.attrib == {
        "version": "0.1.0-alpha",
        "date": "2026-08-02",
        "type": "development",
    }

    description = release.find("description")

    assert description is not None

    description_text = " ".join(
        value.strip() for value in description.itertext() if value.strip()
    )

    assert "Initial public alpha" in description_text
    assert "NetworkManager" in description_text


def test_project_uses_pep639_license_metadata() -> None:
    """Package licensing should use SPDX metadata without classifiers."""
    pyproject = load_pyproject()
    project = pyproject["project"]

    assert isinstance(project, dict)
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]

    classifiers = project["classifiers"]

    assert isinstance(classifiers, list)
    assert not any(
        isinstance(classifier, str) and classifier.startswith("License ::")
        for classifier in classifiers
    )
