"""Presentation mapping between application state and tray UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QObject, Slot

from tunnel_toggle.controller import ApplicationController
from tunnel_toggle.models import ApplicationState, TunnelState
from tunnel_toggle.tray import TrayShell


class ToggleOperation(StrEnum):
    """Operation represented by the tray's main action."""

    CONNECT = "connect"
    DISCONNECT = "disconnect"


@dataclass(frozen=True, slots=True)
class TrayViewState:
    """Complete presentation state for the minimal tray menu."""

    status: str
    toggle_text: str
    toggle_enabled: bool
    toggle_operation: ToggleOperation | None


def tray_view_for(
    tunnel_state: TunnelState,
) -> TrayViewState:
    """Map a domain tunnel state to tray presentation."""
    if tunnel_state is TunnelState.UNCONFIGURED:
        return TrayViewState(
            status="Not configured",
            toggle_text="Connect",
            toggle_enabled=False,
            toggle_operation=None,
        )

    if tunnel_state is TunnelState.UNKNOWN:
        return TrayViewState(
            status="Checking…",
            toggle_text="Connect",
            toggle_enabled=False,
            toggle_operation=None,
        )

    if tunnel_state is TunnelState.DISCONNECTED:
        return TrayViewState(
            status="Disconnected",
            toggle_text="Connect",
            toggle_enabled=True,
            toggle_operation=ToggleOperation.CONNECT,
        )

    if tunnel_state is TunnelState.CONNECTING:
        return TrayViewState(
            status="Connecting…",
            toggle_text="Connect",
            toggle_enabled=False,
            toggle_operation=None,
        )

    if tunnel_state is TunnelState.CONNECTED:
        return TrayViewState(
            status="Connected",
            toggle_text="Disconnect",
            toggle_enabled=True,
            toggle_operation=ToggleOperation.DISCONNECT,
        )

    if tunnel_state is TunnelState.DISCONNECTING:
        return TrayViewState(
            status="Disconnecting…",
            toggle_text="Disconnect",
            toggle_enabled=False,
            toggle_operation=None,
        )

    return TrayViewState(
        status="Error",
        toggle_text="Unavailable",
        toggle_enabled=False,
        toggle_operation=None,
    )


class TrayPresenter(QObject):
    """Apply controller state to the tray and route user actions."""

    def __init__(
        self,
        *,
        controller: ApplicationController,
        tray: TrayShell,
        parent: QObject | None = None,
    ) -> None:
        """Connect one application controller to one tray shell."""
        super().__init__(parent)

        self._controller = controller
        self._tray = tray
        self._toggle_operation: ToggleOperation | None = None

        self._controller.state_changed.connect(self._handle_state_changed)
        self._tray.toggle_requested.connect(self._handle_toggle_requested)

        self._apply_state(self._controller.state)

    @Slot(object)
    def _handle_state_changed(
        self,
        state: ApplicationState,
    ) -> None:
        """Apply a newly emitted immutable application state."""
        self._apply_state(state)

    @Slot()
    def _handle_toggle_requested(self) -> None:
        """Route the current tray operation to the controller."""
        if self._toggle_operation is ToggleOperation.CONNECT:
            self._controller.request_connect()
            return

        if self._toggle_operation is ToggleOperation.DISCONNECT:
            self._controller.request_disconnect()

    def _apply_state(self, state: ApplicationState) -> None:
        """Render one complete controller state."""
        view_state = tray_view_for(state.network.state)
        self._toggle_operation = view_state.toggle_operation

        self._tray.set_status(view_state.status)
        self._tray.set_toggle(
            text=view_state.toggle_text,
            enabled=view_state.toggle_enabled,
        )
