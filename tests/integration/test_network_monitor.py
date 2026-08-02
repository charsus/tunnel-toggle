"""Integration tests for NetworkManager event monitoring."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from tunnel_toggle.network_monitor import NetworkManagerMonitor


@pytest.fixture
def fake_nmcli_path() -> str:
    """Return the executable fake nmcli fixture path."""
    path = Path(__file__).parents[1] / "fixtures" / "fake_nmcli.py"

    if not path.is_file():
        raise RuntimeError("The fake nmcli fixture is missing.")

    return str(path)


def test_monitor_emits_activity_without_parsing_text(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    fake_nmcli_path: str,
) -> None:
    """Any monitor output should produce one activity signal."""
    monkeypatch.setenv(
        "TUNNEL_TOGGLE_FAKE_NMCLI_MODE",
        "monitor_activity",
    )
    monitor = NetworkManagerMonitor(
        nmcli_executable=fake_nmcli_path,
        debounce_ms=20,
        restart_delay_ms=100,
    )

    with qtbot.waitSignal(
        monitor.network_activity_detected,
        timeout=1_000,
    ):
        monitor.start()

    assert monitor.is_running is True

    monitor.stop()

    assert monitor.is_running is False


def test_monitor_debounces_output_bursts(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    fake_nmcli_path: str,
) -> None:
    """Several rapid output lines should produce one activity event."""
    monkeypatch.setenv(
        "TUNNEL_TOGGLE_FAKE_NMCLI_MODE",
        "monitor_burst",
    )
    monitor = NetworkManagerMonitor(
        nmcli_executable=fake_nmcli_path,
        debounce_ms=40,
        restart_delay_ms=100,
    )
    activities: list[str] = []

    monitor.network_activity_detected.connect(lambda: activities.append("activity"))
    monitor.start()

    qtbot.waitUntil(
        lambda: len(activities) == 1,
        timeout=1_000,
    )
    qtbot.wait(100)

    assert activities == ["activity"]

    monitor.stop()


def test_monitor_restarts_after_unexpected_exit(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    fake_nmcli_path: str,
    tmp_path: Path,
) -> None:
    """An unexpected exit should be followed by a delayed restart."""
    counter_path = tmp_path / "monitor-count.txt"

    monkeypatch.setenv(
        "TUNNEL_TOGGLE_FAKE_NMCLI_MODE",
        "monitor_restart",
    )
    monkeypatch.setenv(
        "TUNNEL_TOGGLE_FAKE_NMCLI_COUNTER_FILE",
        str(counter_path),
    )

    monitor = NetworkManagerMonitor(
        nmcli_executable=fake_nmcli_path,
        debounce_ms=20,
        restart_delay_ms=20,
    )
    failures: list[str] = []

    monitor.monitor_failed.connect(failures.append)

    with qtbot.waitSignal(
        monitor.network_activity_detected,
        timeout=1_500,
    ):
        monitor.start()

    assert int(counter_path.read_text(encoding="utf-8")) >= 2
    assert failures == [
        ("NetworkManager monitor stopped unexpectedly with exit code 13.")
    ]

    monitor.stop()


def test_missing_monitor_executable_fails_safely(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    """A missing executable should fail without scheduling restarts."""
    monitor = NetworkManagerMonitor(
        nmcli_executable=str(tmp_path / "missing-nmcli"),
        debounce_ms=20,
        restart_delay_ms=20,
    )

    with qtbot.waitSignal(
        monitor.monitor_failed,
        timeout=1_000,
    ) as blocker:
        monitor.start()

    assert blocker.args == ["The nmcli monitor process could not be started."]
    assert monitor.is_running is False
    assert monitor.restart_scheduled is False


def test_stop_cancels_scheduled_restart(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
    fake_nmcli_path: str,
    tmp_path: Path,
) -> None:
    """Stopping should prevent a failed monitor from restarting."""
    counter_path = tmp_path / "monitor-count.txt"

    monkeypatch.setenv(
        "TUNNEL_TOGGLE_FAKE_NMCLI_MODE",
        "monitor_restart",
    )
    monkeypatch.setenv(
        "TUNNEL_TOGGLE_FAKE_NMCLI_COUNTER_FILE",
        str(counter_path),
    )

    monitor = NetworkManagerMonitor(
        nmcli_executable=fake_nmcli_path,
        debounce_ms=20,
        restart_delay_ms=250,
    )

    with qtbot.waitSignal(
        monitor.monitor_failed,
        timeout=1_000,
    ):
        monitor.start()

    assert monitor.restart_scheduled is True

    monitor.stop()
    qtbot.wait(350)

    assert counter_path.read_text(encoding="utf-8") == "1"
    assert monitor.is_running is False
    assert monitor.restart_scheduled is False
