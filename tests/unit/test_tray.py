"""Tests for the minimal system tray shell."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from tunnel_toggle.application import APPLICATION_NAME
from tunnel_toggle.tray import (
    INITIAL_STATUS,
    INITIAL_TOGGLE_TEXT,
    TrayShell,
)


@pytest.fixture
def tray_shell(qtbot: QtBot) -> TrayShell:
    """Create an isolated hidden tray shell."""
    tray = TrayShell()
    qtbot.addWidget(tray.menu)

    yield tray

    tray.hide()


def test_tray_builds_status_toggle_separator_and_quit_actions(
    tray_shell: TrayShell,
) -> None:
    """The menu should expose presentation-only shell actions."""
    actions = tray_shell.menu.actions()

    assert len(actions) == 4
    assert actions[0] is tray_shell.status_action
    assert actions[0].text() == (f"Status: {INITIAL_STATUS}")
    assert actions[0].isEnabled() is False

    assert actions[1] is tray_shell.toggle_action
    assert actions[1].text() == INITIAL_TOGGLE_TEXT
    assert actions[1].isEnabled() is False

    assert actions[2].isSeparator() is True

    assert actions[3] is tray_shell.quit_action
    assert actions[3].text() == "Quit"
    assert actions[3].isEnabled() is True


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


def test_set_toggle_updates_text_and_enabled_state(
    tray_shell: TrayShell,
) -> None:
    """The presenter should control the complete toggle display."""
    tray_shell.set_toggle(
        text="Disconnect",
        enabled=True,
    )

    assert tray_shell.toggle_action.text() == "Disconnect"
    assert tray_shell.toggle_action.isEnabled() is True


def test_set_toggle_rejects_empty_text(
    tray_shell: TrayShell,
) -> None:
    """The connection action should always have a useful label."""
    with pytest.raises(
        ValueError,
        match="toggle text must not be empty",
    ):
        tray_shell.set_toggle(
            text=" ",
            enabled=True,
        )


def test_toggle_action_emits_simple_signal(
    qtbot: QtBot,
    tray_shell: TrayShell,
) -> None:
    """The QAction checked value should not leak through the API."""
    tray_shell.set_toggle(
        text="Connect",
        enabled=True,
    )

    with qtbot.waitSignal(
        tray_shell.toggle_requested,
        timeout=1_000,
    ):
        tray_shell.toggle_action.trigger()


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
