"""Tests for NetworkManager connection setup coordination."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from pytestqt.qtbot import QtBot

from tunnel_toggle.models import ConnectionProfile
from tunnel_toggle.settings import (
    AppSettings,
    NetworkSettings,
    ProtectedApplicationSettings,
    PublicIpSettings,
    WarningSettings,
)
from tunnel_toggle.setup_controller import (
    ConnectionSetupController,
    SetupPhase,
)

FIRST_UUID = "22222222-2222-2222-2222-222222222222"
SECOND_UUID = "33333333-3333-3333-3333-333333333333"

FIRST_PROFILE = ConnectionProfile(
    uuid=FIRST_UUID,
    name="Home Tunnel",
    connection_type="wireguard",
    is_active=False,
)
SECOND_PROFILE = ConnectionProfile(
    uuid=SECOND_UUID,
    name="Work VPN",
    connection_type="vpn",
    is_active=True,
)


class FakeNetworkManagerBackend(QObject):
    """Controllable discovery backend test double."""

    profiles_discovered = Signal(object)
    discovery_failed = Signal(str)

    def __init__(self) -> None:
        """Create an idle fake discovery backend."""
        super().__init__()
        self._is_busy = False
        self.discovery_requests = 0

    @property
    def is_busy(self) -> bool:
        """Return whether fake discovery is active."""
        return self._is_busy

    def discover_connections(self) -> None:
        """Record one discovery request."""
        self.discovery_requests += 1
        self._is_busy = True

    def complete(
        self,
        profiles: tuple[ConnectionProfile, ...],
    ) -> None:
        """Complete discovery with supported profiles."""
        self._is_busy = False
        self.profiles_discovered.emit(profiles)

    def fail(self, message: str) -> None:
        """Complete discovery with a normalized failure."""
        self._is_busy = False
        self.discovery_failed.emit(message)


class FakeSettingsRepository:
    """In-memory settings repository test double."""

    def __init__(self) -> None:
        """Create an empty repository spy."""
        self.saved_settings: list[AppSettings] = []
        self.save_error: Exception | None = None

    def save(self, settings: AppSettings) -> None:
        """Record settings or raise a configured error."""
        if self.save_error is not None:
            raise self.save_error

        self.saved_settings.append(settings)


def create_controller(
    *,
    settings: AppSettings | None = None,
) -> tuple[
    ConnectionSetupController,
    FakeNetworkManagerBackend,
    FakeSettingsRepository,
]:
    """Create a setup controller with isolated dependencies."""
    backend = FakeNetworkManagerBackend()
    repository = FakeSettingsRepository()
    controller = ConnectionSetupController(
        backend=backend,  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
        settings=settings or AppSettings(),
    )
    return controller, backend, repository


def test_controller_begins_idle() -> None:
    """Setup should not perform discovery during construction."""
    controller, backend, _ = create_controller()

    assert controller.state.phase is SetupPhase.IDLE
    assert controller.state.profiles == ()
    assert backend.discovery_requests == 0


def test_refresh_requests_discovery_and_sets_loading() -> None:
    """Refresh should expose loading before starting discovery."""
    controller, backend, _ = create_controller()

    controller.refresh_profiles()

    assert controller.state.phase is SetupPhase.LOADING
    assert controller.state.error_message is None
    assert backend.discovery_requests == 1


def test_discovery_exposes_profiles() -> None:
    """Successful discovery should produce a ready profile list."""
    controller, backend, _ = create_controller()
    controller.refresh_profiles()

    backend.complete((FIRST_PROFILE, SECOND_PROFILE))

    assert controller.state.phase is SetupPhase.READY
    assert controller.state.profiles == (
        FIRST_PROFILE,
        SECOND_PROFILE,
    )
    assert controller.state.selected_connection_uuid is None


def test_discovery_retains_stored_uuid_by_identity() -> None:
    """A still-existing stored UUID should remain selected."""
    settings = AppSettings(
        setup_completed=True,
        network=NetworkSettings(
            connection_uuid=SECOND_UUID,
        ),
    )
    controller, backend, _ = create_controller(
        settings=settings,
    )
    controller.refresh_profiles()

    backend.complete((FIRST_PROFILE, SECOND_PROFILE))

    assert controller.state.selected_connection_uuid == SECOND_UUID


def test_discovery_clears_missing_stored_uuid() -> None:
    """A removed NetworkManager profile must not remain selected."""
    settings = AppSettings(
        setup_completed=True,
        network=NetworkSettings(
            connection_uuid=SECOND_UUID,
        ),
    )
    controller, backend, _ = create_controller(
        settings=settings,
    )
    controller.refresh_profiles()

    backend.complete((FIRST_PROFILE,))

    assert controller.state.phase is SetupPhase.READY
    assert controller.state.selected_connection_uuid is None


def test_select_connection_uses_discovered_uuid() -> None:
    """A discovered profile should become the current selection."""
    controller, backend, _ = create_controller()
    controller.refresh_profiles()
    backend.complete((FIRST_PROFILE, SECOND_PROFILE))

    controller.select_connection("33333333-3333-3333-3333-333333333333")

    assert controller.state.selected_connection_uuid == SECOND_UUID


def test_unknown_selection_is_rejected(
    qtbot: QtBot,
) -> None:
    """Selections must come from the latest discovery result."""
    controller, backend, _ = create_controller()
    controller.refresh_profiles()
    backend.complete((FIRST_PROFILE,))

    with qtbot.waitSignal(
        controller.operation_rejected,
        timeout=1_000,
    ) as blocker:
        controller.select_connection(SECOND_UUID)

    assert blocker.args == ["Selected connection was not returned by NetworkManager."]
    assert controller.state.selected_connection_uuid is None


def test_selection_before_discovery_is_rejected(
    qtbot: QtBot,
) -> None:
    """The user cannot select from an unverified profile list."""
    controller, _, _ = create_controller()

    with qtbot.waitSignal(
        controller.operation_rejected,
        timeout=1_000,
    ) as blocker:
        controller.select_connection(FIRST_UUID)

    assert blocker.args == ["Connection profiles are not ready for selection."]


def test_save_requires_selection(
    qtbot: QtBot,
) -> None:
    """Setup cannot complete without an explicit profile."""
    controller, backend, repository = create_controller()
    controller.refresh_profiles()
    backend.complete((FIRST_PROFILE,))

    with qtbot.waitSignal(
        controller.operation_rejected,
        timeout=1_000,
    ) as blocker:
        controller.save_selection()

    assert blocker.args == ["Select a NetworkManager connection before saving."]
    assert repository.saved_settings == []


def test_save_preserves_unrelated_settings(
    qtbot: QtBot,
) -> None:
    """Saving a profile should modify only setup and network data."""
    initial_settings = AppSettings(
        setup_completed=False,
        network=NetworkSettings(
            command_timeout_ms=12_000,
        ),
        protected_application=ProtectedApplicationSettings(
            enabled=False,
            profile_id="qbittorrent",
        ),
        warnings=WarningSettings(
            show_notification=False,
        ),
        public_ip=PublicIpSettings(
            enabled=True,
        ),
    )
    controller, backend, repository = create_controller(
        settings=initial_settings,
    )
    controller.refresh_profiles()
    backend.complete((FIRST_PROFILE, SECOND_PROFILE))
    controller.select_connection(SECOND_UUID)

    with qtbot.waitSignal(
        controller.settings_saved,
        timeout=1_000,
    ) as blocker:
        controller.save_selection()

    saved = blocker.args[0]

    assert repository.saved_settings == [saved]
    assert saved.setup_completed is True
    assert saved.network.connection_uuid == SECOND_UUID
    assert saved.network.last_known_name == "Work VPN"
    assert saved.network.last_known_type == "vpn"
    assert saved.network.command_timeout_ms == 12_000
    assert saved.protected_application == initial_settings.protected_application
    assert saved.warnings == initial_settings.warnings
    assert saved.public_ip == initial_settings.public_ip
    assert controller.settings == saved


def test_discovery_failure_sets_error_state() -> None:
    """Normalized backend failures should remain presentation-safe."""
    controller, backend, _ = create_controller()
    controller.refresh_profiles()

    backend.fail("NetworkManager discovery failed with exit code 7.")

    assert controller.state.phase is SetupPhase.ERROR
    assert controller.state.error_message == (
        "NetworkManager discovery failed with exit code 7."
    )


def test_busy_backend_rejects_refresh(
    qtbot: QtBot,
) -> None:
    """Setup must not overlap another NetworkManager operation."""
    controller, backend, _ = create_controller()
    backend._is_busy = True

    with qtbot.waitSignal(
        controller.operation_rejected,
        timeout=1_000,
    ) as blocker:
        controller.refresh_profiles()

    assert blocker.args == ["Another NetworkManager operation is already running."]
    assert backend.discovery_requests == 0


def test_repository_failure_sets_error_state() -> None:
    """Persistence failure should not report setup as completed."""
    controller, backend, repository = create_controller()
    controller.refresh_profiles()
    backend.complete((FIRST_PROFILE,))
    controller.select_connection(FIRST_UUID)
    repository.save_error = OSError("Settings could not be saved.")

    controller.save_selection()

    assert controller.state.phase is SetupPhase.ERROR
    assert controller.state.error_message == ("Settings could not be saved.")
    assert controller.settings.setup_completed is False
    assert repository.saved_settings == []
