"""NetworkManager connection discovery and output parsing."""

from __future__ import annotations

from enum import StrEnum
from typing import Final
from uuid import UUID

from PySide6.QtCore import (
    QObject,
    QProcess,
    QProcessEnvironment,
    QStandardPaths,
    QTimer,
    Signal,
)

from tunnel_toggle.models import (
    ConnectionProfile,
    NetworkStatus,
    TunnelState,
)

SUPPORTED_CONNECTION_TYPES: Final[frozenset[str]] = frozenset(
    {
        "vpn",
        "wireguard",
    }
)


class NetworkManagerParseError(ValueError):
    """Raised when machine-readable NetworkManager output is invalid."""


def discovery_arguments() -> tuple[str, ...]:
    """Return arguments for machine-readable connection discovery."""
    return (
        "--terse",
        "--escape",
        "yes",
        "--fields",
        "UUID,TYPE,NAME",
        "connection",
        "show",
    )


def parse_connection_profiles(output: str) -> tuple[ConnectionProfile, ...]:
    """Parse supported VPN and WireGuard profiles from nmcli output."""
    profiles_by_uuid: dict[str, ConnectionProfile] = {}

    for line_number, raw_line in enumerate(output.splitlines(), start=1):
        if not raw_line:
            continue

        try:
            uuid_text, connection_type, name = _split_escaped_fields(
                raw_line,
                expected_fields=3,
            )
            normalized_uuid = str(UUID(uuid_text.strip()))
        except (NetworkManagerParseError, ValueError) as error:
            raise NetworkManagerParseError(
                f"Invalid NetworkManager discovery output on line {line_number}."
            ) from error

        normalized_type = connection_type.strip().lower()

        if normalized_type not in SUPPORTED_CONNECTION_TYPES:
            continue

        try:
            profile = ConnectionProfile(
                uuid=normalized_uuid,
                name=name,
                connection_type=normalized_type,
            )
        except ValueError as error:
            raise NetworkManagerParseError(
                f"Invalid NetworkManager connection profile on line {line_number}."
            ) from error

        profiles_by_uuid.setdefault(profile.uuid, profile)

    return tuple(
        sorted(
            profiles_by_uuid.values(),
            key=lambda profile: (
                profile.name.casefold(),
                profile.uuid,
            ),
        )
    )


def _split_escaped_fields(
    line: str,
    *,
    expected_fields: int,
) -> tuple[str, ...]:
    """Split one escaped nmcli terse-output line into fields."""
    fields: list[str] = []
    current: list[str] = []
    escaped = False

    for character in line:
        if escaped:
            current.append(character)
            escaped = False
            continue

        if character == "\\":
            escaped = True
            continue

        if character == ":":
            fields.append("".join(current))
            current.clear()
            continue

        current.append(character)

    if escaped:
        raise NetworkManagerParseError(
            "A field ended with an incomplete escape sequence."
        )

    fields.append("".join(current))

    if len(fields) != expected_fields:
        raise NetworkManagerParseError(
            f"Expected {expected_fields} fields but received {len(fields)}."
        )

    return tuple(fields)


def state_query_arguments() -> tuple[str, ...]:
    """Return arguments for machine-readable active-state queries."""
    return (
        "--terse",
        "--escape",
        "yes",
        "--fields",
        "UUID,TYPE",
        "connection",
        "show",
        "--active",
    )


def parse_active_connection_uuids(output: str) -> frozenset[str]:
    """Parse active supported connection UUIDs from nmcli output."""
    active_uuids: set[str] = set()

    for line_number, raw_line in enumerate(output.splitlines(), start=1):
        if not raw_line:
            continue

        try:
            uuid_text, connection_type = _split_escaped_fields(
                raw_line,
                expected_fields=2,
            )
            normalized_uuid = str(UUID(uuid_text.strip()))
        except (NetworkManagerParseError, ValueError) as error:
            raise NetworkManagerParseError(
                f"Invalid NetworkManager active-state output on line {line_number}."
            ) from error

        normalized_type = connection_type.strip().lower()

        if normalized_type in SUPPORTED_CONNECTION_TYPES:
            active_uuids.add(normalized_uuid)

    return frozenset(active_uuids)


class _Operation(StrEnum):
    """Asynchronous NetworkManager operations."""

    DISCOVERY = "discovery"
    STATE_QUERY = "state_query"


class NetworkManagerBackend(QObject):
    """Run asynchronous NetworkManager operations through nmcli."""

    profiles_discovered = Signal(object)
    discovery_failed = Signal(str)
    tunnel_state_received = Signal(object)
    state_query_failed = Signal(str)

    def __init__(
        self,
        *,
        nmcli_executable: str | None = None,
        timeout_ms: int = 30_000,
        parent: QObject | None = None,
    ) -> None:
        """Create a backend with an injectable nmcli executable."""
        super().__init__(parent)

        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be greater than zero.")

        self._nmcli_executable = (
            nmcli_executable
            if nmcli_executable is not None
            else QStandardPaths.findExecutable("nmcli")
        )
        self._timeout_ms = timeout_ms
        self._process: QProcess | None = None
        self._operation: _Operation | None = None
        self._target_uuid: str | None = None
        self._timed_out = False

        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._handle_timeout)

    @property
    def is_busy(self) -> bool:
        """Return whether a NetworkManager command is running."""
        return self._process is not None

    def discover_connections(self) -> None:
        """Start asynchronous VPN and WireGuard profile discovery."""
        self._start_operation(
            operation=_Operation.DISCOVERY,
            arguments=discovery_arguments(),
        )

    def query_tunnel_state(self, connection_uuid: str) -> None:
        """Query whether NetworkManager reports a UUID as active."""
        try:
            normalized_uuid = str(UUID(connection_uuid.strip()))
        except ValueError as error:
            raise ValueError("connection_uuid must be a valid UUID.") from error

        self._start_operation(
            operation=_Operation.STATE_QUERY,
            arguments=state_query_arguments(),
            target_uuid=normalized_uuid,
        )

    def _start_operation(
        self,
        *,
        operation: _Operation,
        arguments: tuple[str, ...],
        target_uuid: str | None = None,
    ) -> None:
        """Start one asynchronous nmcli operation."""
        if self.is_busy:
            raise RuntimeError("A NetworkManager operation is already running.")

        if not self._nmcli_executable:
            self._emit_failure(
                operation,
                "The nmcli executable could not be found.",
            )
            return

        process = QProcess(self)
        process.setProgram(self._nmcli_executable)
        process.setArguments(list(arguments))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)

        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("LC_ALL", "C")
        environment.insert("LANG", "C")
        environment.insert("NO_COLOR", "1")
        process.setProcessEnvironment(environment)

        process.finished.connect(self._handle_finished)
        process.errorOccurred.connect(self._handle_process_error)

        self._process = process
        self._operation = operation
        self._target_uuid = target_uuid
        self._timed_out = False

        process.start()
        self._timeout_timer.start(self._timeout_ms)

    def _handle_timeout(self) -> None:
        """Terminate an operation after the configured timeout."""
        process = self._process

        if process is None:
            return

        self._timed_out = True
        process.kill()

    def _handle_process_error(
        self,
        error: QProcess.ProcessError,
    ) -> None:
        """Handle errors that occur before normal completion."""
        if error != QProcess.ProcessError.FailedToStart or self._process is None:
            return

        self._finish_failure("The nmcli process could not be started.")

    def _handle_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        """Handle completion of the active operation."""
        process = self._process
        operation = self._operation

        if process is None or operation is None:
            return

        self._timeout_timer.stop()

        if self._timed_out:
            self._finish_failure(f"{self._operation_label(operation)} timed out.")
            return

        if exit_status == QProcess.ExitStatus.CrashExit:
            self._finish_failure(
                f"The {self._operation_label(operation)} process crashed."
            )
            return

        if exit_code != 0:
            self._finish_failure(
                f"{self._operation_label(operation)} failed with exit code {exit_code}."
            )
            return

        output = bytes(process.readAllStandardOutput().data()).decode(
            "utf-8", errors="replace"
        )

        if operation is _Operation.DISCOVERY:
            self._complete_discovery(output)
            return

        self._complete_state_query(output)

    def _complete_discovery(self, output: str) -> None:
        """Parse and emit a successful discovery result."""
        try:
            profiles = parse_connection_profiles(output)
        except NetworkManagerParseError:
            self._finish_failure("NetworkManager returned invalid discovery data.")
            return

        self._cleanup_process()
        self.profiles_discovered.emit(profiles)

    def _complete_state_query(self, output: str) -> None:
        """Parse and emit the selected tunnel's active state."""
        target_uuid = self._target_uuid

        if target_uuid is None:
            self._finish_failure("NetworkManager state query had no target UUID.")
            return

        try:
            active_uuids = parse_active_connection_uuids(output)
        except NetworkManagerParseError:
            self._finish_failure("NetworkManager returned invalid state data.")
            return

        if target_uuid in active_uuids:
            status = NetworkStatus(
                state=TunnelState.CONNECTED,
                active_connection_uuid=target_uuid,
            )
        else:
            status = NetworkStatus(
                state=TunnelState.DISCONNECTED,
            )

        self._cleanup_process()
        self.tunnel_state_received.emit(status)

    def _finish_failure(self, message: str) -> None:
        """Clean up and emit a normalized operation failure."""
        operation = self._operation
        self._cleanup_process()

        if operation is not None:
            self._emit_failure(operation, message)

    def _emit_failure(
        self,
        operation: _Operation,
        message: str,
    ) -> None:
        """Emit the failure signal belonging to an operation."""
        if operation is _Operation.DISCOVERY:
            self.discovery_failed.emit(message)
            return

        self.state_query_failed.emit(message)

    def _operation_label(self, operation: _Operation) -> str:
        """Return a stable human-readable operation label."""
        if operation is _Operation.DISCOVERY:
            return "NetworkManager discovery"

        return "NetworkManager state query"

    def _cleanup_process(self) -> None:
        """Release the process and reset operation state."""
        self._timeout_timer.stop()

        process = self._process
        self._process = None
        self._operation = None
        self._target_uuid = None
        self._timed_out = False

        if process is not None:
            process.deleteLater()
