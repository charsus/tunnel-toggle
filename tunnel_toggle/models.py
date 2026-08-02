"""Domain models for Tunnel Toggle."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class TunnelState(StrEnum):
    """Possible states of the selected NetworkManager tunnel."""

    UNCONFIGURED = "unconfigured"
    UNKNOWN = "unknown"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


class ProtectionState(StrEnum):
    """Possible safety states of the protected application."""

    DISABLED = "disabled"
    NOT_RUNNING = "not_running"
    RUNNING_SAFE = "running_safe"
    RUNNING_AT_RISK = "running_at_risk"
    UNKNOWN = "unknown"


class PublicIpState(StrEnum):
    """Possible states of the optional public-IP service."""

    DISABLED = "disabled"
    IDLE = "idle"
    CHECKING = "checking"
    AVAILABLE = "available"
    FAILED = "failed"
    STALE = "stale"


class PresentationState(StrEnum):
    """Visual states available to the system tray interface."""

    UNKNOWN = "unknown"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ConnectionProfile:
    """A NetworkManager connection that Tunnel Toggle can control."""

    uuid: str
    name: str
    connection_type: str
    is_active: bool = False

    def __post_init__(self) -> None:
        """Validate required connection profile values."""
        if not self.uuid.strip():
            raise ValueError("Connection UUID must not be empty.")

        if not self.name.strip():
            raise ValueError("Connection name must not be empty.")

        if not self.connection_type.strip():
            raise ValueError("Connection type must not be empty.")


@dataclass(frozen=True, slots=True)
class NetworkStatus:
    """Current state of the selected NetworkManager connection."""

    state: TunnelState = TunnelState.UNKNOWN
    active_connection_uuid: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ProtectedApplicationStatus:
    """Current state of the protected application."""

    state: ProtectionState = ProtectionState.UNKNOWN
    executable: str | None = None
    process_count: int = 0

    def __post_init__(self) -> None:
        """Validate protected-application process information."""
        if self.process_count < 0:
            raise ValueError("Process count must not be negative.")


@dataclass(frozen=True, slots=True)
class PublicIpResult:
    """Result of an optional public-IP lookup."""

    state: PublicIpState = PublicIpState.DISABLED
    address: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ApplicationState:
    """Aggregate state consumed by the controller and tray interface."""

    network: NetworkStatus = field(default_factory=NetworkStatus)
    protected_application: ProtectedApplicationStatus = field(
        default_factory=ProtectedApplicationStatus
    )
    public_ip: PublicIpResult = field(default_factory=PublicIpResult)
    presentation: PresentationState = PresentationState.UNKNOWN
