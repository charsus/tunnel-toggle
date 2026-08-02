"""Composition and lifetime management for application services."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from tunnel_toggle.controller import ApplicationController
from tunnel_toggle.network_manager import NetworkManagerBackend
from tunnel_toggle.network_monitor import NetworkManagerMonitor
from tunnel_toggle.settings import AppSettings, SettingsRepository
from tunnel_toggle.setup_controller import ConnectionSetupController
from tunnel_toggle.setup_dialog import ConnectionSetupDialog
from tunnel_toggle.tray import TrayShell
from tunnel_toggle.tray_presenter import TrayPresenter


class ApplicationRuntime(QObject):
    """Own and coordinate the complete running application graph."""

    quit_requested = Signal()

    def __init__(
        self,
        *,
        settings: AppSettings,
        repository: SettingsRepository,
        parent: QObject | None = None,
    ) -> None:
        """Construct all runtime services without starting them."""
        super().__init__(parent)

        self._settings = settings
        self._repository = repository

        self._backend = NetworkManagerBackend(
            timeout_ms=settings.network.command_timeout_ms,
            parent=self,
        )
        self._monitor = NetworkManagerMonitor(
            restart_delay_ms=(settings.network.monitor_restart_delay_ms),
            parent=self,
        )
        self._controller = ApplicationController(
            backend=self._backend,
            monitor=self._monitor,
            connection_uuid=selected_connection_uuid(settings),
            parent=self,
        )

        self._tray = TrayShell(parent=self)
        self._presenter = TrayPresenter(
            controller=self._controller,
            tray=self._tray,
            parent=self,
        )

        self._setup_backend = NetworkManagerBackend(
            timeout_ms=settings.network.command_timeout_ms,
            parent=self,
        )
        self._setup_controller = ConnectionSetupController(
            backend=self._setup_backend,
            repository=repository,
            settings=settings,
            parent=self,
        )
        self._setup_dialog = ConnectionSetupDialog(
            controller=self._setup_controller,
        )

        self._started = False

        self._tray.quit_requested.connect(self._handle_quit_requested)
        self._presenter.configure_requested.connect(self._show_setup_dialog)
        self._setup_dialog.settings_saved.connect(self._handle_settings_saved)

    @property
    def settings(self) -> AppSettings:
        """Return the latest successfully saved settings."""
        return self._settings

    @property
    def repository(self) -> SettingsRepository:
        """Return the runtime settings repository."""
        return self._repository

    @property
    def backend(self) -> NetworkManagerBackend:
        """Return the primary NetworkManager backend."""
        return self._backend

    @property
    def monitor(self) -> NetworkManagerMonitor:
        """Return the composed NetworkManager monitor."""
        return self._monitor

    @property
    def controller(self) -> ApplicationController:
        """Return the composed application controller."""
        return self._controller

    @property
    def tray(self) -> TrayShell:
        """Return the composed tray shell."""
        return self._tray

    @property
    def presenter(self) -> TrayPresenter:
        """Return the composed tray presenter."""
        return self._presenter

    @property
    def setup_backend(self) -> NetworkManagerBackend:
        """Return the dedicated setup discovery backend."""
        return self._setup_backend

    @property
    def setup_controller(self) -> ConnectionSetupController:
        """Return the connection setup controller."""
        return self._setup_controller

    @property
    def setup_dialog(self) -> ConnectionSetupDialog:
        """Return the reusable setup dialog."""
        return self._setup_dialog

    @property
    def is_started(self) -> bool:
        """Return whether the runtime is currently active."""
        return self._started

    def start(self) -> None:
        """Start services and then expose the tray icon."""
        if self._started:
            return

        try:
            self._controller.start()
            self._tray.show()
        except Exception:
            self._tray.hide()
            self._controller.stop()
            raise

        self._started = True

    def stop(self) -> None:
        """Hide presentation and stop services safely."""
        self._setup_dialog.hide()

        if not self._started:
            return

        self._started = False

        try:
            self._tray.hide()
        finally:
            self._controller.stop()

    @Slot()
    def _handle_quit_requested(self) -> None:
        """Forward the tray's quit request to the application."""
        self.quit_requested.emit()

    @Slot()
    def _show_setup_dialog(self) -> None:
        """Show or raise the one reusable setup dialog."""
        if not self._setup_dialog.isVisible():
            self._setup_dialog.show()

        self._setup_dialog.raise_()
        self._setup_dialog.activateWindow()

    @Slot(object)
    def _handle_settings_saved(self, settings: object) -> None:
        """Apply a newly persisted setup to the running controller."""
        if not isinstance(settings, AppSettings):
            raise TypeError("Connection setup emitted invalid settings.")

        self._settings = settings
        self._controller.set_connection_uuid(selected_connection_uuid(settings))


def selected_connection_uuid(
    settings: AppSettings,
) -> str | None:
    """Return the usable selected UUID from validated settings."""
    if not settings.setup_completed:
        return None

    return settings.network.connection_uuid


def create_application_runtime(
    *,
    settings: AppSettings,
    repository: SettingsRepository,
    parent: QObject | None = None,
) -> ApplicationRuntime:
    """Create the production runtime from validated settings."""
    return ApplicationRuntime(
        settings=settings,
        repository=repository,
        parent=parent,
    )
