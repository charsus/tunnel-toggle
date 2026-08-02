"""Coordination for discovering and saving tunnel profiles."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID

from PySide6.QtCore import QObject, Signal

from tunnel_toggle.models import ConnectionProfile
from tunnel_toggle.network_manager import NetworkManagerBackend
from tunnel_toggle.settings import (
    AppSettings,
    SettingsError,
    SettingsRepository,
)


class SetupPhase(StrEnum):
    """Lifecycle phases for connection setup."""

    IDLE = "idle"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ConnectionSetupState:
    """Complete immutable state for the future setup dialog."""

    phase: SetupPhase = SetupPhase.IDLE
    profiles: tuple[ConnectionProfile, ...] = ()
    selected_connection_uuid: str | None = None
    error_message: str | None = None


class ConnectionSetupController(QObject):
    """Discover NetworkManager profiles and save one selection."""

    state_changed = Signal(object)
    settings_saved = Signal(object)
    operation_rejected = Signal(str)

    def __init__(
        self,
        *,
        backend: NetworkManagerBackend,
        repository: SettingsRepository,
        settings: AppSettings,
        parent: QObject | None = None,
    ) -> None:
        """Create a setup controller using validated settings."""
        super().__init__(parent)

        self._backend = backend
        self._repository = repository
        self._settings = settings
        self._state = ConnectionSetupState(
            selected_connection_uuid=(settings.network.connection_uuid),
        )

        self._backend.profiles_discovered.connect(self._handle_profiles_discovered)
        self._backend.discovery_failed.connect(self._handle_discovery_failed)

    @property
    def state(self) -> ConnectionSetupState:
        """Return the current immutable setup state."""
        return self._state

    @property
    def settings(self) -> AppSettings:
        """Return the latest successfully persisted settings."""
        return self._settings

    def refresh_profiles(self) -> None:
        """Request supported profiles from NetworkManager."""
        if self._backend.is_busy:
            self._reject("Another NetworkManager operation is already running.")
            return

        self._set_state(
            replace(
                self._state,
                phase=SetupPhase.LOADING,
                profiles=(),
                error_message=None,
            )
        )

        try:
            self._backend.discover_connections()
        except RuntimeError as error:
            self._set_error(str(error))

    def select_connection(
        self,
        connection_uuid: str,
    ) -> None:
        """Select a profile returned by the latest discovery."""
        if self._state.phase is not SetupPhase.READY:
            self._reject("Connection profiles are not ready for selection.")
            return

        try:
            normalized_uuid = str(UUID(connection_uuid.strip()))
        except ValueError:
            self._reject("Selected connection UUID is invalid.")
            return

        profile = self._profile_for_uuid(normalized_uuid)

        if profile is None:
            self._reject("Selected connection was not returned by NetworkManager.")
            return

        self._set_state(
            replace(
                self._state,
                selected_connection_uuid=profile.uuid,
                error_message=None,
            )
        )

    def save_selection(self) -> None:
        """Persist the selected profile and complete setup."""
        if self._state.phase is not SetupPhase.READY:
            self._reject("Connection profiles are not ready to save.")
            return

        selected_uuid = self._state.selected_connection_uuid

        if selected_uuid is None:
            self._reject("Select a NetworkManager connection before saving.")
            return

        profile = self._profile_for_uuid(selected_uuid)

        if profile is None:
            self._reject("The selected connection is no longer available.")
            return

        updated_network = replace(
            self._settings.network,
            connection_uuid=profile.uuid,
            last_known_name=profile.name,
            last_known_type=profile.connection_type,
        )
        updated_settings = replace(
            self._settings,
            setup_completed=True,
            network=updated_network,
        )

        try:
            self._repository.save(updated_settings)
        except (SettingsError, OSError, ValueError) as error:
            self._set_error(str(error))
            return

        self._settings = updated_settings
        self.settings_saved.emit(updated_settings)

    def _handle_profiles_discovered(
        self,
        profiles: object,
    ) -> None:
        """Accept and validate a discovery result."""
        if not isinstance(profiles, (list, tuple)) or not all(
            isinstance(profile, ConnectionProfile) for profile in profiles
        ):
            self._set_error("NetworkManager returned an invalid profile list.")
            return

        profile_values = tuple(profiles)
        selected_uuid = self._state.selected_connection_uuid

        if selected_uuid is not None and not any(
            profile.uuid == selected_uuid for profile in profile_values
        ):
            selected_uuid = None

        self._set_state(
            ConnectionSetupState(
                phase=SetupPhase.READY,
                profiles=profile_values,
                selected_connection_uuid=selected_uuid,
            )
        )

    def _handle_discovery_failed(self, message: str) -> None:
        """Convert a normalized discovery failure into error state."""
        self._set_error(message)

    def _profile_for_uuid(
        self,
        connection_uuid: str,
    ) -> ConnectionProfile | None:
        """Return a discovered profile by its exact UUID."""
        return next(
            (
                profile
                for profile in self._state.profiles
                if profile.uuid == connection_uuid
            ),
            None,
        )

    def _set_error(self, message: str) -> None:
        """Set an error state while retaining useful context."""
        self._set_state(
            replace(
                self._state,
                phase=SetupPhase.ERROR,
                error_message=message,
            )
        )

    def _reject(self, message: str) -> None:
        """Report a rejected user operation."""
        self.operation_rejected.emit(message)

    def _set_state(
        self,
        state: ConnectionSetupState,
    ) -> None:
        """Replace setup state and emit only meaningful changes."""
        if state == self._state:
            return

        self._state = state
        self.state_changed.emit(state)
