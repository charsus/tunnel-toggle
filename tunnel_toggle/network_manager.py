"""NetworkManager connection discovery and output parsing."""

from __future__ import annotations

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

from tunnel_toggle.models import ConnectionProfile

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


class NetworkManagerBackend(QObject):
    """Run asynchronous NetworkManager discovery through nmcli."""

    profiles_discovered = Signal(object)
    discovery_failed = Signal(str)

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
        self._timed_out = False

        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._handle_timeout)

    @property
    def is_busy(self) -> bool:
        """Return whether a discovery process is currently running."""
        return self._process is not None

    def discover_connections(self) -> None:
        """Start asynchronous VPN and WireGuard profile discovery."""
        if self.is_busy:
            raise RuntimeError("NetworkManager discovery is already running.")

        if not self._nmcli_executable:
            self.discovery_failed.emit("The nmcli executable could not be found.")
            return

        process = QProcess(self)
        process.setProgram(self._nmcli_executable)
        process.setArguments(list(discovery_arguments()))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)

        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("LC_ALL", "C")
        environment.insert("LANG", "C")
        environment.insert("NO_COLOR", "1")
        process.setProcessEnvironment(environment)

        process.finished.connect(self._handle_finished)
        process.errorOccurred.connect(self._handle_process_error)

        self._process = process
        self._timed_out = False

        process.start()
        self._timeout_timer.start(self._timeout_ms)

    def _handle_timeout(self) -> None:
        """Terminate discovery after the configured timeout."""
        process = self._process

        if process is None:
            return

        self._timed_out = True
        process.kill()

    def _handle_process_error(
        self,
        error: QProcess.ProcessError,
    ) -> None:
        """Handle errors that may occur before process completion."""
        if error != QProcess.ProcessError.FailedToStart or self._process is None:
            return

        self._finish_failure("The nmcli process could not be started.")

    def _handle_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        """Handle completion of the active discovery process."""
        process = self._process

        if process is None:
            return

        self._timeout_timer.stop()

        if self._timed_out:
            self._finish_failure("NetworkManager discovery timed out.")
            return

        if exit_status == QProcess.ExitStatus.CrashExit:
            self._finish_failure("The NetworkManager discovery process crashed.")
            return

        if exit_code != 0:
            self._finish_failure(
                f"NetworkManager discovery failed with exit code {exit_code}."
            )
            return

        output = bytes(process.readAllStandardOutput().data()).decode(
            "utf-8", errors="replace"
        )

        try:
            profiles = parse_connection_profiles(output)
        except NetworkManagerParseError:
            self._finish_failure("NetworkManager returned invalid discovery data.")
            return

        self.profiles_discovered.emit(profiles)
        self._cleanup_process()

    def _finish_failure(self, message: str) -> None:
        """Emit one normalized failure and clean up the process."""
        self.discovery_failed.emit(message)
        self._cleanup_process()

    def _cleanup_process(self) -> None:
        """Release the active process and reset operation state."""
        self._timeout_timer.stop()

        process = self._process
        self._process = None
        self._timed_out = False

        if process is not None:
            process.deleteLater()
