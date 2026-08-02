"""Typed settings storage for Tunnel Toggle."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeVar

from PySide6.QtCore import QSettings

SETTINGS_SCHEMA_VERSION = 1
SETTINGS_ORGANIZATION = "TunnelToggle"
SETTINGS_APPLICATION = "Tunnel Toggle"


class SettingsError(RuntimeError):
    """Raised when application settings cannot be loaded or saved safely."""


class StartupTunnelAction(StrEnum):
    """Actions available when Tunnel Toggle starts automatically."""

    NONE = "none"
    CONNECT = "connect"


class IconMode(StrEnum):
    """Supported tray icon selection modes."""

    THEME_WITH_FALLBACK = "theme_with_fallback"


def _require_positive(name: str, value: int) -> None:
    """Require an integer setting to be greater than zero."""
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")


def _require_nonnegative(name: str, value: int) -> None:
    """Require an integer setting to be zero or greater."""
    if value < 0:
        raise ValueError(f"{name} must not be negative.")


@dataclass(frozen=True, slots=True)
class NetworkSettings:
    """Settings for NetworkManager discovery, monitoring, and control."""

    connection_uuid: str | None = None
    last_known_name: str | None = None
    last_known_type: str | None = None
    command_timeout_ms: int = 30_000
    fallback_poll_interval_ms: int = 15_000
    monitor_restart_delay_ms: int = 2_000

    def __post_init__(self) -> None:
        """Validate NetworkManager timing values."""
        _require_positive("command_timeout_ms", self.command_timeout_ms)
        _require_positive(
            "fallback_poll_interval_ms",
            self.fallback_poll_interval_ms,
        )
        _require_positive(
            "monitor_restart_delay_ms",
            self.monitor_restart_delay_ms,
        )


@dataclass(frozen=True, slots=True)
class ProtectedApplicationSettings:
    """Settings for protected-application monitoring."""

    enabled: bool = True
    profile_id: str = "qbittorrent"
    custom_executable: str | None = None
    monitor_interval_ms: int = 3_000

    def __post_init__(self) -> None:
        """Validate protected-application settings."""
        if not self.profile_id.strip():
            raise ValueError("profile_id must not be empty.")

        _require_positive("monitor_interval_ms", self.monitor_interval_ms)


@dataclass(frozen=True, slots=True)
class WarningSettings:
    """Settings controlling tunnel safety warnings."""

    app_without_tunnel: bool = True
    show_notification: bool = True
    show_warning_icon: bool = True
    repeat_interval_minutes: int = 0

    def __post_init__(self) -> None:
        """Validate warning timing values."""
        _require_nonnegative(
            "repeat_interval_minutes",
            self.repeat_interval_minutes,
        )


@dataclass(frozen=True, slots=True)
class PublicIpSettings:
    """Settings for optional public-IP checking."""

    enabled: bool = False
    provider_id: str = "default"
    custom_url: str | None = None
    refresh_on_tunnel_change: bool = True
    cache_ttl_seconds: int = 300
    timeout_ms: int = 5_000

    def __post_init__(self) -> None:
        """Validate public-IP settings."""
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty.")

        _require_positive("cache_ttl_seconds", self.cache_ttl_seconds)
        _require_positive("timeout_ms", self.timeout_ms)


@dataclass(frozen=True, slots=True)
class StartupSettings:
    """Settings controlling desktop autostart behavior."""

    autostart_enabled: bool = True
    tunnel_action: StartupTunnelAction = StartupTunnelAction.NONE


@dataclass(frozen=True, slots=True)
class UiSettings:
    """Settings controlling user-interface behavior."""

    notifications_enabled: bool = True
    show_public_ip_in_menu: bool = True
    icon_mode: IconMode = IconMode.THEME_WITH_FALLBACK


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Complete validated Tunnel Toggle configuration."""

    schema_version: int = SETTINGS_SCHEMA_VERSION
    setup_completed: bool = False
    network: NetworkSettings = field(default_factory=NetworkSettings)
    protected_application: ProtectedApplicationSettings = field(
        default_factory=ProtectedApplicationSettings
    )
    warnings: WarningSettings = field(default_factory=WarningSettings)
    public_ip: PublicIpSettings = field(default_factory=PublicIpSettings)
    startup: StartupSettings = field(default_factory=StartupSettings)
    ui: UiSettings = field(default_factory=UiSettings)

    def __post_init__(self) -> None:
        """Validate application-level settings."""
        _require_positive("schema_version", self.schema_version)


EnumType = TypeVar("EnumType", bound=StrEnum)


class SettingsRepository:
    """Load and save validated application settings through QSettings."""

    def __init__(self, settings: QSettings) -> None:
        """Create a repository using an injected QSettings backend."""
        self._settings = settings

    @classmethod
    def create_default(cls) -> SettingsRepository:
        """Create the normal per-user application settings repository."""
        settings = QSettings(
            QSettings.Format.NativeFormat,
            QSettings.Scope.UserScope,
            SETTINGS_ORGANIZATION,
            SETTINGS_APPLICATION,
        )
        return cls(settings)

    @property
    def file_name(self) -> str:
        """Return the settings backend filename for diagnostics."""
        return self._settings.fileName()

    def load(self) -> AppSettings:
        """Load, convert, and validate all application settings."""
        schema_version = self._read_positive_int(
            "meta/schema_version",
            SETTINGS_SCHEMA_VERSION,
        )

        if schema_version > SETTINGS_SCHEMA_VERSION:
            raise SettingsError(
                "Settings were created by a newer Tunnel Toggle version."
            )

        return AppSettings(
            schema_version=schema_version,
            setup_completed=self._read_bool(
                "meta/setup_completed",
                False,
            ),
            network=NetworkSettings(
                connection_uuid=self._read_optional_string("network/connection_uuid"),
                last_known_name=self._read_optional_string("network/last_known_name"),
                last_known_type=self._read_optional_string("network/last_known_type"),
                command_timeout_ms=self._read_positive_int(
                    "network/command_timeout_ms",
                    30_000,
                ),
                fallback_poll_interval_ms=self._read_positive_int(
                    "network/fallback_poll_interval_ms",
                    15_000,
                ),
                monitor_restart_delay_ms=self._read_positive_int(
                    "network/monitor_restart_delay_ms",
                    2_000,
                ),
            ),
            protected_application=ProtectedApplicationSettings(
                enabled=self._read_bool(
                    "protected_app/enabled",
                    True,
                ),
                profile_id=self._read_nonempty_string(
                    "protected_app/profile_id",
                    "qbittorrent",
                ),
                custom_executable=self._read_optional_string(
                    "protected_app/custom_executable"
                ),
                monitor_interval_ms=self._read_positive_int(
                    "protected_app/monitor_interval_ms",
                    3_000,
                ),
            ),
            warnings=WarningSettings(
                app_without_tunnel=self._read_bool(
                    "warnings/app_without_tunnel",
                    True,
                ),
                show_notification=self._read_bool(
                    "warnings/show_notification",
                    True,
                ),
                show_warning_icon=self._read_bool(
                    "warnings/show_warning_icon",
                    True,
                ),
                repeat_interval_minutes=self._read_nonnegative_int(
                    "warnings/repeat_interval_minutes",
                    0,
                ),
            ),
            public_ip=PublicIpSettings(
                enabled=self._read_bool(
                    "public_ip/enabled",
                    False,
                ),
                provider_id=self._read_nonempty_string(
                    "public_ip/provider_id",
                    "default",
                ),
                custom_url=self._read_optional_string("public_ip/custom_url"),
                refresh_on_tunnel_change=self._read_bool(
                    "public_ip/refresh_on_tunnel_change",
                    True,
                ),
                cache_ttl_seconds=self._read_positive_int(
                    "public_ip/cache_ttl_seconds",
                    300,
                ),
                timeout_ms=self._read_positive_int(
                    "public_ip/timeout_ms",
                    5_000,
                ),
            ),
            startup=StartupSettings(
                autostart_enabled=self._read_bool(
                    "startup/autostart_enabled",
                    True,
                ),
                tunnel_action=self._read_enum(
                    "startup/tunnel_action",
                    StartupTunnelAction.NONE,
                    StartupTunnelAction,
                ),
            ),
            ui=UiSettings(
                notifications_enabled=self._read_bool(
                    "ui/notifications_enabled",
                    True,
                ),
                show_public_ip_in_menu=self._read_bool(
                    "ui/show_public_ip_in_menu",
                    True,
                ),
                icon_mode=self._read_enum(
                    "ui/icon_mode",
                    IconMode.THEME_WITH_FALLBACK,
                    IconMode,
                ),
            ),
        )

    def save(self, settings: AppSettings) -> None:
        """Save a complete validated configuration."""
        values: dict[str, object] = {
            "meta/schema_version": settings.schema_version,
            "meta/setup_completed": settings.setup_completed,
            "network/connection_uuid": settings.network.connection_uuid or "",
            "network/last_known_name": settings.network.last_known_name or "",
            "network/last_known_type": settings.network.last_known_type or "",
            "network/command_timeout_ms": settings.network.command_timeout_ms,
            "network/fallback_poll_interval_ms": (
                settings.network.fallback_poll_interval_ms
            ),
            "network/monitor_restart_delay_ms": (
                settings.network.monitor_restart_delay_ms
            ),
            "protected_app/enabled": settings.protected_application.enabled,
            "protected_app/profile_id": (settings.protected_application.profile_id),
            "protected_app/custom_executable": (
                settings.protected_application.custom_executable or ""
            ),
            "protected_app/monitor_interval_ms": (
                settings.protected_application.monitor_interval_ms
            ),
            "warnings/app_without_tunnel": (settings.warnings.app_without_tunnel),
            "warnings/show_notification": (settings.warnings.show_notification),
            "warnings/show_warning_icon": (settings.warnings.show_warning_icon),
            "warnings/repeat_interval_minutes": (
                settings.warnings.repeat_interval_minutes
            ),
            "public_ip/enabled": settings.public_ip.enabled,
            "public_ip/provider_id": settings.public_ip.provider_id,
            "public_ip/custom_url": settings.public_ip.custom_url or "",
            "public_ip/refresh_on_tunnel_change": (
                settings.public_ip.refresh_on_tunnel_change
            ),
            "public_ip/cache_ttl_seconds": (settings.public_ip.cache_ttl_seconds),
            "public_ip/timeout_ms": settings.public_ip.timeout_ms,
            "startup/autostart_enabled": (settings.startup.autostart_enabled),
            "startup/tunnel_action": settings.startup.tunnel_action.value,
            "ui/notifications_enabled": settings.ui.notifications_enabled,
            "ui/show_public_ip_in_menu": (settings.ui.show_public_ip_in_menu),
            "ui/icon_mode": settings.ui.icon_mode.value,
        }

        for key, value in values.items():
            self._settings.setValue(key, value)

        self._settings.sync()

        if self._settings.status() is not QSettings.Status.NoError:
            raise SettingsError("Tunnel Toggle settings could not be written safely.")

    def _read_bool(self, key: str, default: bool) -> bool:
        """Read a Boolean value with a typed default."""
        value = self._settings.value(key, default, type=bool)
        return bool(value)

    def _read_string(self, key: str, default: str) -> str:
        """Read a string or return its default."""
        value = self._settings.value(key, default, type=str)

        if not isinstance(value, str):
            return default

        return value

    def _read_optional_string(self, key: str) -> str | None:
        """Read a string and convert blank values to None."""
        value = self._read_string(key, "").strip()
        return value or None

    def _read_nonempty_string(self, key: str, default: str) -> str:
        """Read a string, falling back when it is blank."""
        value = self._read_string(key, default).strip()
        return value or default

    def _read_positive_int(self, key: str, default: int) -> int:
        """Read a positive integer, falling back when invalid."""
        value = self._read_int(key, default)

        if value <= 0:
            return default

        return value

    def _read_nonnegative_int(self, key: str, default: int) -> int:
        """Read a nonnegative integer, falling back when invalid."""
        value = self._read_int(key, default)

        if value < 0:
            return default

        return value

    def _read_int(self, key: str, default: int) -> int:
        """Read an integer, falling back when conversion fails."""
        raw_value = self._settings.value(key, default)

        try:
            return int(str(raw_value).strip())
        except (TypeError, ValueError):
            return default

    def _read_enum(
        self,
        key: str,
        default: EnumType,
        enum_type: type[EnumType],
    ) -> EnumType:
        """Read a string enumeration, falling back when unknown."""
        raw_value = self._read_string(key, default.value)

        try:
            return enum_type(raw_value)
        except ValueError:
            return default
