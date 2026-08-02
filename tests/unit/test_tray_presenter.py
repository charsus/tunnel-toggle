"""Tests for application-state presentation in the tray."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal
from pytestqt.qtbot import QtBot

from tunnel_toggle.models import (
    ApplicationState,
    NetworkStatus,
    PresentationState,
    TunnelState,
)
from tunnel_toggle.tray import TrayShell
from tunnel_toggle.tray_presenter import (
    ToggleOperation,
    TrayPresenter,
    TrayViewState,
    tray_view_for,
)


class FakeApplicationController(QObject):
    """Controllable controller test double for tray presentation."""

    state_changed = Signal(object)

    def __init__(
        self,
        tunnel_state: TunnelState,
    ) -> None:
        """Create a fake controller with one initial state."""
        super().__init__()
        self._state = create_application_state(tunnel_state)
        self.connect_requests = 0
        self.disconnect_requests = 0

    @property
    def state(self) -> ApplicationState:
        """Return the current immutable fake state."""
        return self._state

    def request_connect(self) -> None:
        """Record a tray connect request."""
        self.connect_requests += 1

    def request_disconnect(self) -> None:
        """Record a tray disconnect request."""
        self.disconnect_requests += 1

    def set_tunnel_state(
        self,
        tunnel_state: TunnelState,
    ) -> None:
        """Emit a replacement application state."""
        self._state = create_application_state(tunnel_state)
        self.state_changed.emit(self._state)


def create_application_state(
    tunnel_state: TunnelState,
) -> ApplicationState:
    """Create the smallest state needed by the presenter."""
    return ApplicationState(
        network=NetworkStatus(
            state=tunnel_state,
        ),
        presentation=PresentationState.UNKNOWN,
    )


def create_presenter(
    qtbot: QtBot,
    tunnel_state: TunnelState,
) -> tuple[
    TrayPresenter,
    FakeApplicationController,
    TrayShell,
]:
    """Create a presenter with isolated fake dependencies."""
    controller = FakeApplicationController(tunnel_state)
    tray = TrayShell()
    qtbot.addWidget(tray.menu)

    presenter = TrayPresenter(
        controller=controller,  # type: ignore[arg-type]
        tray=tray,
    )

    return presenter, controller, tray


@pytest.mark.parametrize(
    ("tunnel_state", "expected"),
    [
        (
            TunnelState.UNCONFIGURED,
            TrayViewState(
                status="Not configured",
                toggle_text="Connect",
                toggle_enabled=False,
                toggle_operation=None,
            ),
        ),
        (
            TunnelState.UNKNOWN,
            TrayViewState(
                status="Checking…",
                toggle_text="Connect",
                toggle_enabled=False,
                toggle_operation=None,
            ),
        ),
        (
            TunnelState.DISCONNECTED,
            TrayViewState(
                status="Disconnected",
                toggle_text="Connect",
                toggle_enabled=True,
                toggle_operation=ToggleOperation.CONNECT,
            ),
        ),
        (
            TunnelState.CONNECTING,
            TrayViewState(
                status="Connecting…",
                toggle_text="Connect",
                toggle_enabled=False,
                toggle_operation=None,
            ),
        ),
        (
            TunnelState.CONNECTED,
            TrayViewState(
                status="Connected",
                toggle_text="Disconnect",
                toggle_enabled=True,
                toggle_operation=ToggleOperation.DISCONNECT,
            ),
        ),
        (
            TunnelState.DISCONNECTING,
            TrayViewState(
                status="Disconnecting…",
                toggle_text="Disconnect",
                toggle_enabled=False,
                toggle_operation=None,
            ),
        ),
        (
            TunnelState.ERROR,
            TrayViewState(
                status="Error",
                toggle_text="Unavailable",
                toggle_enabled=False,
                toggle_operation=None,
            ),
        ),
    ],
)
def test_tray_view_maps_every_tunnel_state(
    tunnel_state: TunnelState,
    expected: TrayViewState,
) -> None:
    """Every domain state should have an explicit tray mapping."""
    assert tray_view_for(tunnel_state) == expected


def test_presenter_applies_initial_controller_state(
    qtbot: QtBot,
) -> None:
    """Construction should immediately replace startup text."""
    presenter, _, tray = create_presenter(
        qtbot,
        TunnelState.DISCONNECTED,
    )

    assert presenter is not None
    assert tray.status_action.text() == "Status: Disconnected"
    assert tray.toggle_action.text() == "Connect"
    assert tray.toggle_action.isEnabled() is True


def test_presenter_applies_emitted_state_changes(
    qtbot: QtBot,
) -> None:
    """Controller signals should update the complete tray view."""
    presenter, controller, tray = create_presenter(
        qtbot,
        TunnelState.DISCONNECTED,
    )

    controller.set_tunnel_state(TunnelState.CONNECTED)

    assert presenter is not None
    assert tray.status_action.text() == "Status: Connected"
    assert tray.toggle_action.text() == "Disconnect"
    assert tray.toggle_action.isEnabled() is True


def test_disconnected_toggle_requests_connect(
    qtbot: QtBot,
) -> None:
    """The enabled disconnected action should request connection."""
    presenter, controller, tray = create_presenter(
        qtbot,
        TunnelState.DISCONNECTED,
    )

    tray.toggle_action.trigger()

    assert presenter is not None
    assert controller.connect_requests == 1
    assert controller.disconnect_requests == 0


def test_connected_toggle_requests_disconnect(
    qtbot: QtBot,
) -> None:
    """The enabled connected action should request disconnection."""
    presenter, controller, tray = create_presenter(
        qtbot,
        TunnelState.CONNECTED,
    )

    tray.toggle_action.trigger()

    assert presenter is not None
    assert controller.connect_requests == 0
    assert controller.disconnect_requests == 1


@pytest.mark.parametrize(
    "tunnel_state",
    [
        TunnelState.UNCONFIGURED,
        TunnelState.UNKNOWN,
        TunnelState.CONNECTING,
        TunnelState.DISCONNECTING,
        TunnelState.ERROR,
    ],
)
def test_non_actionable_state_ignores_toggle_signal(
    qtbot: QtBot,
    tunnel_state: TunnelState,
) -> None:
    """Disabled states should remain safe if signalled directly."""
    presenter, controller, tray = create_presenter(
        qtbot,
        tunnel_state,
    )

    tray.toggle_requested.emit()

    assert presenter is not None
    assert controller.connect_requests == 0
    assert controller.disconnect_requests == 0
