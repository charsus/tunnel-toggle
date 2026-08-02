"""Tests for application runtime composition and lifetime."""

from __future__ import annotations

from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot

from tunnel_toggle.models import TunnelState
from tunnel_toggle.network_manager import NetworkManagerBackend
from tunnel_toggle.network_monitor import NetworkManagerMonitor
from tunnel_toggle.runtime import (
    ApplicationRuntime,
    create_application_runtime,
    selected_connection_uuid,
)
from tunnel_toggle.settings import AppSettings, NetworkSettings
from tunnel_toggle.tray import TrayShell

TARGET_UUID = "44444444-4444-4444-4444-444444444444"


class FakeSettingsRepository:
    """Minimal runtime settings repository test double."""

    def __init__(self) -> None:
        self.saved_settings: list[AppSettings] = []

    def save(self, settings: AppSettings) -> None:
        self.saved_settings.append(settings)


def install_lifecycle_spies(
    monkeypatch: MonkeyPatch,
) -> tuple[list[str], list[str]]:
    """Replace process and tray lifecycle methods with test spies."""
    lifecycle_calls: list[str] = []
    state_queries: list[str] = []

    def start_monitor(
        monitor: NetworkManagerMonitor,
    ) -> None:
        del monitor
        lifecycle_calls.append("monitor.start")

    def stop_monitor(
        monitor: NetworkManagerMonitor,
    ) -> None:
        del monitor
        lifecycle_calls.append("monitor.stop")

    def show_tray(
        tray: TrayShell,
    ) -> None:
        del tray
        lifecycle_calls.append("tray.show")

    def hide_tray(
        tray: TrayShell,
    ) -> None:
        del tray
        lifecycle_calls.append("tray.hide")

    def query_state(
        backend: NetworkManagerBackend,
        connection_uuid: str,
    ) -> None:
        del backend
        state_queries.append(connection_uuid)

    monkeypatch.setattr(
        NetworkManagerMonitor,
        "start",
        start_monitor,
    )
    monkeypatch.setattr(
        NetworkManagerMonitor,
        "stop",
        stop_monitor,
    )
    monkeypatch.setattr(
        TrayShell,
        "show",
        show_tray,
    )
    monkeypatch.setattr(
        TrayShell,
        "hide",
        hide_tray,
    )
    monkeypatch.setattr(
        NetworkManagerBackend,
        "query_tunnel_state",
        query_state,
    )

    return lifecycle_calls, state_queries


def create_runtime(
    qtbot: QtBot,
    *,
    connection_uuid: str | None = None,
) -> ApplicationRuntime:
    """Create a runtime with isolated settings storage."""
    settings = AppSettings(
        setup_completed=connection_uuid is not None,
        network=NetworkSettings(
            connection_uuid=connection_uuid,
        ),
    )
    repository = FakeSettingsRepository()
    runtime = ApplicationRuntime(
        settings=settings,
        repository=repository,  # type: ignore[arg-type]
    )
    qtbot.addWidget(runtime.tray.menu)
    qtbot.addWidget(runtime.setup_dialog)
    return runtime


def test_runtime_composes_unconfigured_initial_view(
    qtbot: QtBot,
) -> None:
    """The production graph should begin safely unconfigured."""
    runtime = create_runtime(qtbot)

    assert runtime.controller.state.network.state is (TunnelState.UNCONFIGURED)
    assert runtime.tray.status_action.text() == ("Status: Not configured")
    assert runtime.tray.toggle_action.isEnabled() is False
    assert runtime.is_started is False


def test_start_activates_monitor_before_showing_tray(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
) -> None:
    """Runtime startup should use a stable service order."""
    lifecycle_calls, state_queries = install_lifecycle_spies(monkeypatch)
    runtime = create_runtime(qtbot)

    runtime.start()

    assert lifecycle_calls == [
        "monitor.start",
        "tray.show",
    ]
    assert state_queries == []
    assert runtime.controller.is_started is True
    assert runtime.is_started is True

    runtime.stop()


def test_start_is_idempotent(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
) -> None:
    """Repeated startup should not duplicate monitor or tray work."""
    lifecycle_calls, _ = install_lifecycle_spies(monkeypatch)
    runtime = create_runtime(qtbot)

    runtime.start()
    runtime.start()

    assert lifecycle_calls == [
        "monitor.start",
        "tray.show",
    ]

    runtime.stop()


def test_stop_hides_tray_before_stopping_monitor(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
) -> None:
    """Runtime shutdown should hide presentation first."""
    lifecycle_calls, _ = install_lifecycle_spies(monkeypatch)
    runtime = create_runtime(qtbot)
    runtime.start()
    lifecycle_calls.clear()

    runtime.stop()
    runtime.stop()

    assert lifecycle_calls == [
        "tray.hide",
        "monitor.stop",
    ]
    assert runtime.controller.is_started is False
    assert runtime.is_started is False


def test_configured_runtime_requests_initial_state(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
) -> None:
    """A configured runtime should query its selected UUID."""
    lifecycle_calls, state_queries = install_lifecycle_spies(monkeypatch)
    runtime = create_runtime(
        qtbot,
        connection_uuid=TARGET_UUID,
    )

    runtime.start()

    assert lifecycle_calls == [
        "monitor.start",
        "tray.show",
    ]
    assert state_queries == [TARGET_UUID]
    assert runtime.controller.state.network.state is (TunnelState.UNKNOWN)

    runtime.stop()


def test_runtime_forwards_tray_quit_request(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
) -> None:
    """The application should receive the tray's quit request."""
    install_lifecycle_spies(monkeypatch)
    runtime = create_runtime(qtbot)

    with qtbot.waitSignal(
        runtime.quit_requested,
        timeout=1_000,
    ):
        runtime.tray.quit_requested.emit()


def test_runtime_retains_all_composed_services(
    qtbot: QtBot,
) -> None:
    """The runtime should retain every member of its object graph."""
    runtime = create_runtime(qtbot)

    components: tuple[object, ...] = (
        runtime.backend,
        runtime.monitor,
        runtime.controller,
        runtime.tray,
        runtime.presenter,
    )

    assert all(component is not None for component in components)


def test_incomplete_setup_ignores_stored_uuid() -> None:
    """A partially completed setup must remain unconfigured."""
    settings = AppSettings(
        setup_completed=False,
        network=NetworkSettings(
            connection_uuid=TARGET_UUID,
        ),
    )

    assert selected_connection_uuid(settings) is None


def test_completed_setup_exposes_selected_uuid() -> None:
    """Completed setup should provide the configured connection."""
    settings = AppSettings(
        setup_completed=True,
        network=NetworkSettings(
            connection_uuid=TARGET_UUID,
        ),
    )

    assert selected_connection_uuid(settings) == TARGET_UUID


def test_runtime_factory_uses_completed_setup(
    qtbot: QtBot,
) -> None:
    """The production factory should configure the controller."""
    settings = AppSettings(
        setup_completed=True,
        network=NetworkSettings(
            connection_uuid=TARGET_UUID,
        ),
    )

    repository = FakeSettingsRepository()
    runtime = create_application_runtime(
        settings=settings,
        repository=repository,  # type: ignore[arg-type]
    )
    qtbot.addWidget(runtime.tray.menu)

    assert runtime.controller.connection_uuid == TARGET_UUID
    assert runtime.controller.state.network.state is (TunnelState.UNKNOWN)


def test_runtime_factory_keeps_incomplete_setup_unconfigured(
    qtbot: QtBot,
) -> None:
    """An incomplete setup should produce the safe tray state."""
    settings = AppSettings(
        setup_completed=False,
        network=NetworkSettings(
            connection_uuid=TARGET_UUID,
        ),
    )

    repository = FakeSettingsRepository()
    runtime = create_application_runtime(
        settings=settings,
        repository=repository,  # type: ignore[arg-type]
    )
    qtbot.addWidget(runtime.tray.menu)

    assert runtime.controller.connection_uuid is None
    assert runtime.controller.state.network.state is (TunnelState.UNCONFIGURED)
    assert runtime.tray.status_action.text() == ("Status: Not configured")


def test_unconfigured_runtime_exposes_configure_action(
    qtbot: QtBot,
) -> None:
    """Initial setup should be available from the tray."""
    runtime = create_runtime(qtbot)

    assert runtime.tray.configure_action.isVisible() is True
    assert runtime.tray.configure_action.isEnabled() is True


def test_configure_request_shows_reusable_dialog(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
) -> None:
    """Repeated requests should use one existing dialog."""
    runtime = create_runtime(qtbot)
    shown_dialogs: list[object] = []

    monkeypatch.setattr(
        runtime.setup_dialog,
        "show",
        lambda: shown_dialogs.append(runtime.setup_dialog),
    )
    monkeypatch.setattr(
        runtime.setup_dialog,
        "isVisible",
        lambda: False,
    )
    monkeypatch.setattr(
        runtime.setup_dialog,
        "raise_",
        lambda: None,
    )
    monkeypatch.setattr(
        runtime.setup_dialog,
        "activateWindow",
        lambda: None,
    )

    runtime.presenter.configure_requested.emit()
    runtime.presenter.configure_requested.emit()

    assert shown_dialogs == [
        runtime.setup_dialog,
        runtime.setup_dialog,
    ]
    assert runtime.setup_dialog is runtime.setup_dialog


def test_saved_setup_updates_running_controller(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
) -> None:
    """A saved UUID should immediately trigger canonical state."""
    lifecycle_calls, state_queries = install_lifecycle_spies(monkeypatch)
    runtime = create_runtime(qtbot)
    runtime.start()

    updated_settings = AppSettings(
        setup_completed=True,
        network=NetworkSettings(
            connection_uuid=TARGET_UUID,
        ),
    )

    runtime.setup_dialog.settings_saved.emit(updated_settings)

    assert runtime.settings == updated_settings
    assert runtime.controller.connection_uuid == TARGET_UUID
    assert state_queries == [TARGET_UUID]
    assert runtime.tray.configure_action.isVisible() is False
    assert lifecycle_calls == [
        "monitor.start",
        "tray.show",
    ]

    runtime.stop()
