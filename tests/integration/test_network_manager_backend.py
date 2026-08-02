"""Integration tests for asynchronous NetworkManager discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from tunnel_toggle.network_manager import NetworkManagerBackend


@pytest.fixture
def fake_nmcli_path() -> str:
    """Return the executable fake nmcli fixture path."""
    path = Path(__file__).parents[1] / "fixtures" / "fake_nmcli.py"

    if not path.is_file():
        raise RuntimeError("The fake nmcli fixture is missing.")

    return str(path)


def test_async_discovery_returns_supported_profiles(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    fake_nmcli_path: str,
) -> None:
    """The backend should emit parsed profiles without blocking."""
    monkeypatch.setenv(
        "TUNNEL_TOGGLE_FAKE_NMCLI_MODE",
        "success",
    )
    backend = NetworkManagerBackend(
        nmcli_executable=fake_nmcli_path,
        timeout_ms=1_000,
    )

    with qtbot.waitSignal(
        backend.profiles_discovered,
        timeout=1_000,
    ) as blocker:
        backend.discover_connections()

    profiles = blocker.args[0]

    assert [profile.name for profile in profiles] == [
        "Home Tunnel",
        "Work:VPN",
    ]
    assert backend.is_busy is False


def test_async_discovery_normalizes_command_failure(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    fake_nmcli_path: str,
) -> None:
    """Command stderr should not be exposed through the public error."""
    monkeypatch.setenv(
        "TUNNEL_TOGGLE_FAKE_NMCLI_MODE",
        "failure",
    )
    backend = NetworkManagerBackend(
        nmcli_executable=fake_nmcli_path,
        timeout_ms=1_000,
    )

    with qtbot.waitSignal(
        backend.discovery_failed,
        timeout=1_000,
    ) as blocker:
        backend.discover_connections()

    message = blocker.args[0]

    assert message == ("NetworkManager discovery failed with exit code 7.")
    assert "do-not-leak" not in message
    assert backend.is_busy is False


def test_async_discovery_rejects_malformed_output(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    fake_nmcli_path: str,
) -> None:
    """Successful commands with malformed data should fail safely."""
    monkeypatch.setenv(
        "TUNNEL_TOGGLE_FAKE_NMCLI_MODE",
        "malformed",
    )
    backend = NetworkManagerBackend(
        nmcli_executable=fake_nmcli_path,
        timeout_ms=1_000,
    )

    with qtbot.waitSignal(
        backend.discovery_failed,
        timeout=1_000,
    ) as blocker:
        backend.discover_connections()

    assert blocker.args == ["NetworkManager returned invalid discovery data."]
    assert backend.is_busy is False


def test_async_discovery_times_out(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    fake_nmcli_path: str,
) -> None:
    """A hung command should be terminated and reported."""
    monkeypatch.setenv(
        "TUNNEL_TOGGLE_FAKE_NMCLI_MODE",
        "timeout",
    )
    backend = NetworkManagerBackend(
        nmcli_executable=fake_nmcli_path,
        timeout_ms=50,
    )

    with qtbot.waitSignal(
        backend.discovery_failed,
        timeout=1_000,
    ) as blocker:
        backend.discover_connections()

    assert blocker.args == ["NetworkManager discovery timed out."]
    assert backend.is_busy is False


def test_async_discovery_reports_failed_start(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    """A missing injected executable should produce a safe error."""
    backend = NetworkManagerBackend(
        nmcli_executable=str(tmp_path / "missing-nmcli"),
        timeout_ms=1_000,
    )

    with qtbot.waitSignal(
        backend.discovery_failed,
        timeout=1_000,
    ) as blocker:
        backend.discover_connections()

    assert blocker.args == ["The nmcli process could not be started."]
    assert backend.is_busy is False


def test_overlapping_discovery_is_rejected(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    fake_nmcli_path: str,
) -> None:
    """One backend should not run overlapping discovery commands."""
    monkeypatch.setenv(
        "TUNNEL_TOGGLE_FAKE_NMCLI_MODE",
        "timeout",
    )
    backend = NetworkManagerBackend(
        nmcli_executable=fake_nmcli_path,
        timeout_ms=50,
    )

    with qtbot.waitSignal(
        backend.discovery_failed,
        timeout=1_000,
    ):
        backend.discover_connections()

        with pytest.raises(RuntimeError, match="already running"):
            backend.discover_connections()

    assert backend.is_busy is False
