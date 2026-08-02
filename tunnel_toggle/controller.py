"""Application state coordination for Tunnel Toggle."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from PySide6.QtCore import QObject, Signal

from tunnel_toggle.models import (
    ApplicationState,
    NetworkStatus,
    PresentationState,
    TunnelState,
)
from tunnel_toggle.network_manager import NetworkManagerBackend
from tunnel_toggle.network_monitor import NetworkManagerMonitor


class ApplicationController(QObject):
    """Coordinate NetworkManager services and application state."""

    state_changed = Signal(object)
    operation_rejected = Signal(str)

    def __init__(
        self,
        *,
        backend: NetworkManagerBackend,
        monitor: NetworkManagerMonitor,
        connection_uuid: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Create a controller for one selected connection UUID."""
        super().__init__(parent)

        self._backend = backend
        self._monitor = monitor
        self._connection_uuid = self._normalize_optional_uuid(connection_uuid)
        self._refresh_pending = False
        self._started = False

        if self._connection_uuid is None:
            network = NetworkStatus(
                state=TunnelState.UNCONFIGURED,
            )
            presentation = PresentationState.WARNING
        else:
            network = NetworkStatus(
                state=TunnelState.UNKNOWN,
            )
            presentation = PresentationState.UNKNOWN

        self._state = ApplicationState(
            network=network,
            presentation=presentation,
        )

        self._backend.tunnel_state_received.connect(self._handle_tunnel_state)
        self._backend.state_query_failed.connect(self._handle_backend_failure)
        self._backend.tunnel_connected.connect(self._handle_control_success)
        self._backend.connect_failed.connect(self._handle_backend_failure)
        self._backend.tunnel_disconnected.connect(self._handle_control_success)
        self._backend.disconnect_failed.connect(self._handle_backend_failure)
        self._monitor.network_activity_detected.connect(self.refresh_state)

    @property
    def state(self) -> ApplicationState:
        """Return the current immutable application state."""
        return self._state

    @property
    def connection_uuid(self) -> str | None:
        """Return the selected normalized NetworkManager UUID."""
        return self._connection_uuid

    @property
    def is_started(self) -> bool:
        """Return whether controller services have been started."""
        return self._started

    def start(self) -> None:
        """Start monitoring and request the initial tunnel state."""
        if self._started:
            return

        self._started = True
        self._monitor.start()
        self.refresh_state()

    def stop(self) -> None:
        """Stop long-running controller services."""
        if not self._started:
            return

        self._started = False
        self._refresh_pending = False
        self._monitor.stop()

    def set_connection_uuid(
        self,
        connection_uuid: str | None,
    ) -> None:
        """Change the selected NetworkManager connection UUID."""
        normalized_uuid = self._normalize_optional_uuid(connection_uuid)

        if normalized_uuid == self._connection_uuid:
            return

        self._connection_uuid = normalized_uuid
        self._refresh_pending = False

        if normalized_uuid is None:
            self._set_network_state(
                NetworkStatus(
                    state=TunnelState.UNCONFIGURED,
                )
            )
            return

        self._set_network_state(
            NetworkStatus(
                state=TunnelState.UNKNOWN,
            )
        )

        if self._started:
            self.refresh_state()

    def refresh_state(self) -> None:
        """Request canonical state for the selected connection."""
        connection_uuid = self._connection_uuid

        if connection_uuid is None:
            self._set_network_state(
                NetworkStatus(
                    state=TunnelState.UNCONFIGURED,
                )
            )
            return

        if self._backend.is_busy:
            self._refresh_pending = True
            return

        self._refresh_pending = False

        try:
            self._backend.query_tunnel_state(connection_uuid)
        except (RuntimeError, ValueError) as error:
            self._set_error(str(error))

    def request_connect(self) -> None:
        """Request activation of the selected connection."""
        connection_uuid = self._require_connection()
        if connection_uuid is None:
            return

        if self._backend.is_busy:
            self.operation_rejected.emit(
                "Another NetworkManager operation is already running."
            )
            return

        self._set_network_state(
            NetworkStatus(
                state=TunnelState.CONNECTING,
            )
        )

        try:
            self._backend.connect_tunnel(connection_uuid)
        except (RuntimeError, ValueError) as error:
            self._set_error(str(error))

    def request_disconnect(self) -> None:
        """Request deactivation of the selected connection."""
        connection_uuid = self._require_connection()
        if connection_uuid is None:
            return

        if self._backend.is_busy:
            self.operation_rejected.emit(
                "Another NetworkManager operation is already running."
            )
            return

        self._set_network_state(
            NetworkStatus(
                state=TunnelState.DISCONNECTING,
            )
        )

        try:
            self._backend.disconnect_tunnel(connection_uuid)
        except (RuntimeError, ValueError) as error:
            self._set_error(str(error))

    def _require_connection(self) -> str | None:
        """Return the configured UUID or reject the operation."""
        if self._connection_uuid is not None:
            return self._connection_uuid

        message = "No NetworkManager connection is configured."
        self._set_network_state(
            NetworkStatus(
                state=TunnelState.UNCONFIGURED,
                error_message=message,
            )
        )
        self.operation_rejected.emit(message)
        return None

    def _handle_control_success(
        self,
        connection_uuid: str,
    ) -> None:
        """Verify actual state after a successful control command."""
        if connection_uuid != self._connection_uuid:
            return

        self.refresh_state()

    def _handle_tunnel_state(
        self,
        status: NetworkStatus,
    ) -> None:
        """Accept a canonical NetworkManager state result."""
        connection_uuid = self._connection_uuid

        if connection_uuid is None:
            self._set_network_state(
                NetworkStatus(
                    state=TunnelState.UNCONFIGURED,
                )
            )
            return

        if (
            status.state is TunnelState.CONNECTED
            and status.active_connection_uuid != connection_uuid
        ):
            self._set_error("NetworkManager returned a different active UUID.")
            return

        self._set_network_state(status)
        self._run_pending_refresh()

    def _handle_backend_failure(self, message: str) -> None:
        """Convert a normalized backend failure into error state."""
        self._refresh_pending = False
        self._set_error(message)

    def _run_pending_refresh(self) -> None:
        """Run one deferred refresh after an operation completes."""
        if not self._refresh_pending:
            return

        self._refresh_pending = False
        self.refresh_state()

    def _set_error(self, message: str) -> None:
        """Set a normalized controller error state."""
        self._set_network_state(
            NetworkStatus(
                state=TunnelState.ERROR,
                error_message=message,
            )
        )

    def _set_network_state(
        self,
        network: NetworkStatus,
    ) -> None:
        """Replace network and presentation state atomically."""
        presentation = self._presentation_for(network.state)
        updated = replace(
            self._state,
            network=network,
            presentation=presentation,
        )

        if updated == self._state:
            return

        self._state = updated
        self.state_changed.emit(updated)

    @staticmethod
    def _presentation_for(
        tunnel_state: TunnelState,
    ) -> PresentationState:
        """Map tunnel state to the tray presentation state."""
        if tunnel_state is TunnelState.CONNECTED:
            return PresentationState.CONNECTED

        if tunnel_state is TunnelState.DISCONNECTED:
            return PresentationState.DISCONNECTED

        if tunnel_state in {
            TunnelState.CONNECTING,
            TunnelState.DISCONNECTING,
        }:
            return PresentationState.CONNECTING

        if tunnel_state is TunnelState.ERROR:
            return PresentationState.ERROR

        if tunnel_state is TunnelState.UNCONFIGURED:
            return PresentationState.WARNING

        return PresentationState.UNKNOWN

    @staticmethod
    def _normalize_optional_uuid(
        connection_uuid: str | None,
    ) -> str | None:
        """Normalize an optional selected connection UUID."""
        if connection_uuid is None:
            return None

        stripped_uuid = connection_uuid.strip()

        if not stripped_uuid:
            return None

        try:
            return str(UUID(stripped_uuid))
        except ValueError as error:
            raise ValueError("connection_uuid must be a valid UUID.") from error
