"""Tests for Tunnel Toggle package metadata."""

from tunnel_toggle import __version__


def test_development_version() -> None:
    """The package should expose the expected pre-alpha version."""
    assert __version__ == "0.1.0a1"
