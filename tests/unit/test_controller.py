"""Tests for the Tunnel Toggle application controller."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from pytestqt.qtbot import QtBot

from tunnel_toggle.controller import ApplicationController
from tunnel_toggle.models import (
    NetworkStatus,
    PresentationState,
    TunnelState,
)

TARGET_UUID = "44444444-4444-4444-4444-444444444444"


class FakeNetworkManagerBackend(QObject):
    """Controllable NetworkManager backend test double."""

    tunnel_state_received = Signal(object)
    state_query_failed = Signal(str)
    tunnel_connected = Signal(str)
    connect_failed = Signal(str)
    tunnel_disconnected = Signal(str)
    disconnect_failed = Signal(str)

    def __init__(self) -> None:
        """Create an idle fake backend."""
        super().__init__()
        self._is_busy = False
        self.state_queries: list[str] = []
        self.connect_requests: list[str] = []
        self.disconnect_requests: list[str] = []

    @property
    def is_busy(self) -> bool:
        """Return whether a simulated operation is running."""
        return self._is_busy

    def query_tunnel_state(self, connection_uuid: str) -> None:
        """Record a state query."""
        self.state_queries.append(connection_uuid)
        self._is_busy = True

    def connect_tunnel(self, connection_uuid: str) -> None:
        """Record a connect request."""
        self.connect_requests.append(connection_uuid)
        self._is_busy = True

    def disconnect_tunnel(self, connection_uuid: str) -> None:
        """Record a disconnect request."""
        self.disconnect_requests.append(connection_uuid)
        self._is_busy = True

    def complete_state(self, status: NetworkStatus) -> None:
        """Complete a simulated state query."""
        self._is_busy = False
        self.tunnel_state_received.emit(status)

    def complete_connect(self, connection_uuid: str) -> None:
        """Complete a simulated connect command."""
        self._is_busy = False
        self.tunnel_connected.emit(connection_uuid)

    def complete_disconnect(self, connection_uuid: str) -> None:
        """Complete a simulated disconnect command."""
        self._is_busy = False
        self.tunnel_disconnected.emit(connection_uuid)

    def fail_state_query(self, message: str) -> None:
        """Fail a simulated state query."""
        self._is_busy = False
        self.state_query_failed.emit(message)

    def fail_connect(self, message: str) -> None:
        """Fail a simulated connect command."""
        self._is_busy = False
        self.connect_failed.emit(message)

    def fail_disconnect(self, message: str) -> None:
        """Fail a simulated disconnect command."""
        self._is_busy = False
        self.disconnect_failed.emit(message)


class FakeNetworkManagerMonitor(QObject):
    """Controllable NetworkManager monitor test double."""

    network_activity_detected = Signal()

    def __init__(self) -> None:
        """Create a stopped fake monitor."""
        super().__init__()
        self.start_count = 0
        self.stop_count = 0

    def start(self) -> None:
        """Record monitor startup."""
        self.start_count += 1

    def stop(self) -> None:
        """Record monitor shutdown."""
        self.stop_count += 1


def create_controller(
    *,
    connection_uuid: str | None = TARGET_UUID,
) -> tuple[
    ApplicationController,
    FakeNetworkManagerBackend,
    FakeNetworkManagerMonitor,
]:
    """Create a controller with isolated fake services."""
    backend = FakeNetworkManagerBackend()
    monitor = FakeNetworkManagerMonitor()
    controller = ApplicationController(
        backend=backend,  # type: ignore[arg-type]
        monitor=monitor,  # type: ignore[arg-type]
        connection_uuid=connection_uuid,
    )
    return controller, backend, monitor


def test_unconfigured_controller_uses_warning_state() -> None:
    """Missing configuration should be represented explicitly."""
    controller, _, _ = create_controller(connection_uuid=None)

    assert controller.state.network.state is TunnelState.UNCONFIGURED
    assert controller.state.presentation is PresentationState.WARNING


def test_start_begins_monitor_and_initial_state_query() -> None:
    """Starting should monitor and query the selected UUID."""
    controller, backend, monitor = create_controller()

    controller.start()

    assert controller.is_started is True
    assert monitor.start_count == 1
    assert backend.state_queries == [TARGET_UUID]


def test_start_is_idempotent() -> None:
    """Starting twice should not duplicate services or queries."""
    controller, backend, monitor = create_controller()

    controller.start()
    controller.start()

    assert monitor.start_count == 1
    assert backend.state_queries == [TARGET_UUID]


def test_monitor_activity_requests_canonical_refresh() -> None:
    """Monitor text should cause a canonical UUID state query."""
    controller, backend, monitor = create_controller()
    controller.start()
    backend.complete_state(
        NetworkStatus(
            state=TunnelState.DISCONNECTED,
        )
    )

    monitor.network_activity_detected.emit()

    assert backend.state_queries == [
        TARGET_UUID,
        TARGET_UUID,
    ]


def test_connect_waits_for_canonical_state() -> None:
    """Connect completion should trigger verification, not CONNECTED."""
    controller, backend, _ = create_controller()

    controller.request_connect()

    assert controller.state.network.state is TunnelState.CONNECTING
    assert controller.state.presentation is PresentationState.CONNECTING
    assert backend.connect_requests == [TARGET_UUID]

    backend.complete_connect(TARGET_UUID)

    assert controller.state.network.state is TunnelState.CONNECTING
    assert backend.state_queries == [TARGET_UUID]

    backend.complete_state(
        NetworkStatus(
            state=TunnelState.CONNECTED,
            active_connection_uuid=TARGET_UUID,
        )
    )

    assert controller.state.network.state is TunnelState.CONNECTED
    assert controller.state.presentation is PresentationState.CONNECTED


def test_disconnect_waits_for_canonical_state() -> None:
    """Disconnect completion should trigger verification."""
    controller, backend, _ = create_controller()

    controller.request_disconnect()

    assert controller.state.network.state is TunnelState.DISCONNECTING
    assert backend.disconnect_requests == [TARGET_UUID]

    backend.complete_disconnect(TARGET_UUID)

    assert controller.state.network.state is TunnelState.DISCONNECTING
    assert backend.state_queries == [TARGET_UUID]

    backend.complete_state(
        NetworkStatus(
            state=TunnelState.DISCONNECTED,
        )
    )

    assert controller.state.network.state is TunnelState.DISCONNECTED
    assert controller.state.presentation is PresentationState.DISCONNECTED


def test_backend_failure_sets_error_state() -> None:
    """Normalized backend errors should become controller error state."""
    controller, backend, _ = create_controller()

    controller.request_connect()
    backend.fail_connect("NetworkManager connect request failed.")

    assert controller.state.network.state is TunnelState.ERROR
    assert controller.state.network.error_message == (
        "NetworkManager connect request failed."
    )
    assert controller.state.presentation is PresentationState.ERROR


def test_unconfigured_control_request_is_rejected(
    qtbot: QtBot,
) -> None:
    """Control requests require a selected connection UUID."""
    controller, backend, _ = create_controller(connection_uuid=None)

    with qtbot.waitSignal(
        controller.operation_rejected,
        timeout=1_000,
    ) as blocker:
        controller.request_connect()

    assert blocker.args == ["No NetworkManager connection is configured."]
    assert backend.connect_requests == []
    assert controller.state.network.state is TunnelState.UNCONFIGURED


def test_busy_backend_rejects_second_operation(
    qtbot: QtBot,
) -> None:
    """Overlapping NetworkManager commands should be rejected."""
    controller, backend, _ = create_controller()
    controller.request_connect()

    with qtbot.waitSignal(
        controller.operation_rejected,
        timeout=1_000,
    ) as blocker:
        controller.request_disconnect()

    assert blocker.args == ["Another NetworkManager operation is already running."]
    assert backend.disconnect_requests == []


def test_monitor_activity_during_query_is_deferred() -> None:
    """Activity during a query should produce one later refresh."""
    controller, backend, monitor = create_controller()
    controller.start()

    monitor.network_activity_detected.emit()

    assert backend.state_queries == [TARGET_UUID]

    backend.complete_state(
        NetworkStatus(
            state=TunnelState.DISCONNECTED,
        )
    )

    assert backend.state_queries == [
        TARGET_UUID,
        TARGET_UUID,
    ]


def test_changing_connection_refreshes_when_started() -> None:
    """Changing the selected UUID should query the new profile."""
    controller, backend, _ = create_controller()
    controller.start()
    backend.complete_state(
        NetworkStatus(
            state=TunnelState.DISCONNECTED,
        )
    )
    new_uuid = "55555555-5555-5555-5555-555555555555"

    controller.set_connection_uuid(new_uuid)

    assert controller.connection_uuid == new_uuid
    assert controller.state.network.state is TunnelState.UNKNOWN
    assert backend.state_queries[-1] == new_uuid


def test_stop_is_idempotent() -> None:
    """Stopping twice should stop services only once."""
    controller, _, monitor = create_controller()
    controller.start()

    controller.stop()
    controller.stop()

    assert controller.is_started is False
    assert monitor.stop_count == 1
