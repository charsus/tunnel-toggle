"""Tests for the minimal system tray shell."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from tunnel_toggle.application import APPLICATION_NAME
from tunnel_toggle.tray import INITIAL_STATUS, TrayShell


@pytest.fixture
def tray_shell(qtbot: QtBot) -> TrayShell:
    """Create an isolated hidden tray shell."""
    tray = TrayShell()
    qtbot.addWidget(tray.menu)

    yield tray

    tray.hide()


def test_tray_builds_status_separator_and_quit_actions(
    tray_shell: TrayShell,
) -> None:
    """The initial menu should contain only shell actions."""
    actions = tray_shell.menu.actions()

    assert len(actions) == 3
    assert actions[0] is tray_shell.status_action
    assert actions[0].text() == (f"Status: {INITIAL_STATUS}")
    assert actions[0].isEnabled() is False
    assert actions[1].isSeparator() is True
    assert actions[2] is tray_shell.quit_action
    assert actions[2].text() == "Quit"
    assert actions[2].isEnabled() is True


def test_initial_tooltip_identifies_application(
    tray_shell: TrayShell,
) -> None:
    """The initial tooltip should expose startup status."""
    assert tray_shell.tray_icon.toolTip() == (f"{APPLICATION_NAME}: {INITIAL_STATUS}")


def test_set_status_updates_action_and_tooltip(
    tray_shell: TrayShell,
) -> None:
    """One status update should keep menu and tooltip aligned."""
    tray_shell.set_status("Disconnected")

    assert tray_shell.status_action.text() == ("Status: Disconnected")
    assert tray_shell.tray_icon.toolTip() == (f"{APPLICATION_NAME}: Disconnected")


def test_set_status_rejects_empty_text(
    tray_shell: TrayShell,
) -> None:
    """The shell should never display a blank status."""
    with pytest.raises(ValueError, match="must not be empty"):
        tray_shell.set_status("   ")


def test_quit_action_emits_simple_signal(
    qtbot: QtBot,
    tray_shell: TrayShell,
) -> None:
    """The QAction checked value should not leak through the API."""
    with qtbot.waitSignal(
        tray_shell.quit_requested,
        timeout=1_000,
    ):
        tray_shell.quit_action.trigger()
