"""Tests for typed Tunnel Toggle settings."""

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from tunnel_toggle.settings import (
    AppSettings,
    IconMode,
    NetworkSettings,
    ProtectedApplicationSettings,
    PublicIpSettings,
    SettingsError,
    SettingsRepository,
    StartupSettings,
    StartupTunnelAction,
    UiSettings,
    WarningSettings,
)


@pytest.fixture
def qsettings(tmp_path: Path) -> QSettings:
    """Create an isolated settings file for one test."""
    settings = QSettings(
        str(tmp_path / "settings.ini"),
        QSettings.Format.IniFormat,
    )
    settings.setFallbacksEnabled(False)
    return settings


@pytest.fixture
def repository(qsettings: QSettings) -> SettingsRepository:
    """Create a repository backed by isolated test settings."""
    return SettingsRepository(qsettings)


def test_new_repository_loads_safe_defaults(
    repository: SettingsRepository,
) -> None:
    """Missing settings should produce the documented defaults."""
    settings = repository.load()

    assert settings.schema_version == 1
    assert settings.setup_completed is False
    assert settings.network.connection_uuid is None
    assert settings.network.command_timeout_ms == 30_000
    assert settings.protected_application.enabled is True
    assert settings.protected_application.profile_id == "qbittorrent"
    assert settings.warnings.app_without_tunnel is True
    assert settings.warnings.repeat_interval_minutes == 0
    assert settings.public_ip.enabled is False
    assert settings.startup.tunnel_action is StartupTunnelAction.NONE
    assert settings.ui.icon_mode is IconMode.THEME_WITH_FALLBACK


def test_repository_uses_injected_test_file(
    repository: SettingsRepository,
    tmp_path: Path,
) -> None:
    """Tests must not write to the real application settings."""
    assert Path(repository.file_name) == tmp_path / "settings.ini"


def test_settings_round_trip(repository: SettingsRepository) -> None:
    """Saved typed settings should load without losing information."""
    expected = AppSettings(
        setup_completed=True,
        network=NetworkSettings(
            connection_uuid="12345678-1234-1234-1234-123456789abc",
            last_known_name="Home WireGuard",
            last_known_type="wireguard",
            command_timeout_ms=10_000,
            fallback_poll_interval_ms=20_000,
            monitor_restart_delay_ms=3_000,
        ),
        protected_application=ProtectedApplicationSettings(
            enabled=False,
            profile_id="qbittorrent",
            custom_executable="/usr/bin/qbittorrent",
            monitor_interval_ms=4_500,
        ),
        warnings=WarningSettings(
            app_without_tunnel=True,
            show_notification=False,
            show_warning_icon=True,
            repeat_interval_minutes=15,
        ),
        public_ip=PublicIpSettings(
            enabled=True,
            provider_id="default",
            custom_url="https://example.invalid/ip",
            refresh_on_tunnel_change=False,
            cache_ttl_seconds=600,
            timeout_ms=7_000,
        ),
        startup=StartupSettings(
            autostart_enabled=False,
            tunnel_action=StartupTunnelAction.CONNECT,
        ),
        ui=UiSettings(
            notifications_enabled=False,
            show_public_ip_in_menu=False,
            icon_mode=IconMode.THEME_WITH_FALLBACK,
        ),
    )

    repository.save(expected)

    assert repository.load() == expected


def test_invalid_numbers_fall_back_to_defaults(
    qsettings: QSettings,
    repository: SettingsRepository,
) -> None:
    """Malformed numeric settings should not crash the application."""
    qsettings.setValue("network/command_timeout_ms", -1)
    qsettings.setValue("protected_app/monitor_interval_ms", "invalid")
    qsettings.setValue("warnings/repeat_interval_minutes", -5)
    qsettings.sync()

    settings = repository.load()

    assert settings.network.command_timeout_ms == 30_000
    assert settings.protected_application.monitor_interval_ms == 3_000
    assert settings.warnings.repeat_interval_minutes == 0


def test_invalid_enums_fall_back_to_defaults(
    qsettings: QSettings,
    repository: SettingsRepository,
) -> None:
    """Unknown enumeration values should use safe defaults."""
    qsettings.setValue("startup/tunnel_action", "launch_everything")
    qsettings.setValue("ui/icon_mode", "unsupported")
    qsettings.sync()

    settings = repository.load()

    assert settings.startup.tunnel_action is StartupTunnelAction.NONE
    assert settings.ui.icon_mode is IconMode.THEME_WITH_FALLBACK


def test_future_schema_is_rejected(
    qsettings: QSettings,
    repository: SettingsRepository,
) -> None:
    """An older application must not overwrite newer settings."""
    qsettings.setValue("meta/schema_version", 2)
    qsettings.sync()

    with pytest.raises(SettingsError, match="newer"):
        repository.load()


def test_network_settings_reject_invalid_direct_values() -> None:
    """Typed models should reject invalid values created by code."""
    with pytest.raises(ValueError, match="command_timeout_ms"):
        NetworkSettings(command_timeout_ms=0)


def test_warning_settings_reject_negative_repeat_interval() -> None:
    """Warning intervals cannot be negative."""
    with pytest.raises(ValueError, match="repeat_interval_minutes"):
        WarningSettings(repeat_interval_minutes=-1)
