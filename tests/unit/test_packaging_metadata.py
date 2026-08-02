"""Tests for freedesktop desktop and AppStream metadata."""

from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
from shlex import split
from xml.etree import ElementTree

PROJECT_ROOT = Path(__file__).parents[2]
PACKAGING_DIRECTORY = PROJECT_ROOT / "packaging"

APPLICATION_ID = "io.github.charsus.TunnelToggle"
DESKTOP_FILENAME = f"{APPLICATION_ID}.desktop"
METAINFO_FILENAME = f"{APPLICATION_ID}.metainfo.xml"

DESKTOP_PATH = PACKAGING_DIRECTORY / DESKTOP_FILENAME
METAINFO_PATH = PACKAGING_DIRECTORY / METAINFO_FILENAME


def load_desktop_entry() -> dict[str, str]:
    """Load the desktop entry while preserving key capitalization."""
    parser = ConfigParser(
        interpolation=None,
        strict=True,
    )
    parser.optionxform = str

    with DESKTOP_PATH.open(encoding="utf-8") as desktop_file:
        parser.read_file(desktop_file)

    return dict(parser["Desktop Entry"])


def load_metainfo_root() -> ElementTree.Element:
    """Parse the local AppStream metainfo document."""
    return ElementTree.parse(METAINFO_PATH).getroot()


def required_text(
    root: ElementTree.Element,
    path: str,
) -> str:
    """Return required nonempty XML element text."""
    element = root.find(path)

    assert element is not None
    assert element.text is not None

    value = element.text.strip()

    assert value
    return value


def test_metadata_files_use_stable_application_id() -> None:
    """Desktop and AppStream filenames should share one identity."""
    assert DESKTOP_PATH.is_file()
    assert METAINFO_PATH.is_file()
    assert DESKTOP_PATH.name == DESKTOP_FILENAME
    assert METAINFO_PATH.name == METAINFO_FILENAME


def test_desktop_entry_has_required_application_fields() -> None:
    """The launcher should contain its complete basic identity."""
    entry = load_desktop_entry()

    assert entry["Type"] == "Application"
    assert entry["Name"] == "Tunnel Toggle"
    assert entry["GenericName"] == "Network Tunnel Controller"
    assert entry["Comment"] == (
        "Control a NetworkManager VPN or WireGuard connection from the system tray"
    )
    assert entry["Terminal"] == "false"
    assert entry["StartupNotify"] == "false"


def test_desktop_entry_launches_console_script_without_shell() -> None:
    """The launcher should execute only the installed entry point."""
    entry = load_desktop_entry()

    assert split(entry["Exec"]) == ["tunnel-toggle"]
    assert split(entry["TryExec"]) == ["tunnel-toggle"]

    forbidden_shell_tokens = {
        "&&",
        "||",
        ";",
        "|",
        ">",
        "<",
    }

    assert forbidden_shell_tokens.isdisjoint(split(entry["Exec"]))


def test_desktop_entry_uses_theme_icon_and_kde_scope() -> None:
    """Desktop presentation should use KDE-compatible metadata."""
    entry = load_desktop_entry()

    assert entry["Icon"] == "network-vpn"
    assert not Path(entry["Icon"]).is_absolute()
    assert entry["OnlyShowIn"] == "KDE;"

    categories = {value for value in entry["Categories"].split(";") if value}
    keywords = {value for value in entry["Keywords"].split(";") if value}

    assert categories == {"Network"}
    assert {
        "VPN",
        "WireGuard",
        "NetworkManager",
        "Tunnel",
    }.issubset(keywords)


def test_metainfo_identity_matches_desktop_entry() -> None:
    """AppStream identity should resolve to the desktop launcher."""
    root = load_metainfo_root()

    assert root.tag == "component"
    assert root.attrib == {"type": "desktop-application"}
    assert required_text(root, "id") == APPLICATION_ID
    assert required_text(root, "name") == "Tunnel Toggle"

    launchable = root.find("launchable")

    assert launchable is not None
    assert launchable.attrib == {"type": "desktop-id"}
    assert launchable.text is not None
    assert launchable.text.strip() == DESKTOP_FILENAME


def test_metainfo_declares_licenses_and_binary() -> None:
    """AppStream metadata should identify licensing and executable."""
    root = load_metainfo_root()

    assert required_text(root, "metadata_license") == "CC0-1.0"
    assert required_text(root, "project_license") == "MIT"
    assert required_text(root, "provides/binary") == "tunnel-toggle"


def test_metainfo_uses_project_urls() -> None:
    """Published metadata should point to project-controlled pages."""
    root = load_metainfo_root()
    urls = {
        element.attrib["type"]: (element.text or "").strip()
        for element in root.findall("url")
    }

    assert urls == {
        "homepage": "https://github.com/charsus/tunnel-toggle",
        "bugtracker": ("https://github.com/charsus/tunnel-toggle/issues"),
    }


def test_metainfo_describes_security_boundaries() -> None:
    """Application metadata must not overstate tunnel protection."""
    root = load_metainfo_root()
    description = root.find("description")

    assert description is not None

    description_text = " ".join(
        text.strip() for text in description.itertext() if text.strip()
    ).lower()

    assert "networkmanager" in description_text
    assert "kill switch" in description_text
    assert "application binding" in description_text
    assert "leak-prevention" in description_text
