"""Tests for the presentation-only connection setup dialog."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QDialog
from pytestqt.qtbot import QtBot

from tunnel_toggle.models import ConnectionProfile
from tunnel_toggle.setup_controller import (
    ConnectionSetupState,
    SetupPhase,
)
from tunnel_toggle.setup_dialog import (
    DIALOG_TITLE,
    ConnectionSetupDialog,
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


class FakeConnectionSetupController(QObject):
    """Controllable setup-controller test double."""

    state_changed = Signal(object)
    settings_saved = Signal(object)
    operation_rejected = Signal(str)

    def __init__(
        self,
        state: ConnectionSetupState | None = None,
    ) -> None:
        """Create a fake setup controller."""
        super().__init__()
        self._state = state or ConnectionSetupState()
        self.refresh_requests = 0
        self.selection_requests: list[str] = []
        self.save_requests = 0

    @property
    def state(self) -> ConnectionSetupState:
        """Return the current fake setup state."""
        return self._state

    def refresh_profiles(self) -> None:
        """Record a discovery request."""
        self.refresh_requests += 1

    def select_connection(
        self,
        connection_uuid: str,
    ) -> None:
        """Record an exact UUID selection."""
        self.selection_requests.append(connection_uuid)

    def save_selection(self) -> None:
        """Record a persistence request."""
        self.save_requests += 1

    def emit_state(
        self,
        state: ConnectionSetupState,
    ) -> None:
        """Replace and emit setup state."""
        self._state = state
        self.state_changed.emit(state)


def create_dialog(
    qtbot: QtBot,
    *,
    state: ConnectionSetupState | None = None,
) -> tuple[
    ConnectionSetupDialog,
    FakeConnectionSetupController,
]:
    """Create a hidden dialog with an isolated fake controller."""
    controller = FakeConnectionSetupController(state)
    dialog = ConnectionSetupDialog(
        controller=controller,  # type: ignore[arg-type]
    )
    qtbot.addWidget(dialog)
    return dialog, controller


def test_dialog_builds_initial_idle_view(
    qtbot: QtBot,
) -> None:
    """Construction should render state without starting discovery."""
    dialog, controller = create_dialog(qtbot)

    assert dialog.windowTitle() == DIALOG_TITLE
    assert dialog.profile_combo.count() == 0
    assert dialog.profile_combo.isEnabled() is False
    assert dialog.refresh_button.isEnabled() is True
    assert dialog.save_button.isEnabled() is False
    assert dialog.status_label.text() == (
        "Refresh to search for supported connections."
    )
    assert controller.refresh_requests == 0


def test_opening_dialog_requests_profile_refresh(
    qtbot: QtBot,
) -> None:
    """Showing the dialog should request asynchronous discovery."""
    dialog, controller = create_dialog(qtbot)

    dialog.show()

    assert controller.refresh_requests == 1


def test_loading_state_disables_interaction(
    qtbot: QtBot,
) -> None:
    """Discovery should prevent overlapping dialog operations."""
    dialog, controller = create_dialog(qtbot)

    controller.emit_state(
        ConnectionSetupState(
            phase=SetupPhase.LOADING,
        )
    )

    assert dialog.profile_combo.isEnabled() is False
    assert dialog.refresh_button.isEnabled() is False
    assert dialog.save_button.isEnabled() is False
    assert dialog.status_label.text() == (
        "Searching for VPN and WireGuard connections…"
    )


def test_ready_state_lists_profiles_by_name_and_type(
    qtbot: QtBot,
) -> None:
    """Profiles should display labels while retaining UUID data."""
    dialog, controller = create_dialog(qtbot)

    controller.emit_state(
        ConnectionSetupState(
            phase=SetupPhase.READY,
            profiles=(FIRST_PROFILE, SECOND_PROFILE),
        )
    )

    assert dialog.profile_combo.count() == 2
    assert dialog.profile_combo.itemText(0) == ("Home Tunnel — WireGuard")
    assert dialog.profile_combo.itemData(0) == FIRST_UUID
    assert dialog.profile_combo.itemText(1) == "Work VPN — VPN"
    assert dialog.profile_combo.itemData(1) == SECOND_UUID
    assert dialog.profile_combo.currentIndex() == -1
    assert dialog.profile_combo.isEnabled() is True
    assert dialog.save_button.isEnabled() is False
    assert dialog.status_label.text() == ("Choose a connection to continue.")


def test_ready_state_restores_selection_by_uuid(
    qtbot: QtBot,
) -> None:
    """Controller selection should be restored by identity."""
    dialog, controller = create_dialog(qtbot)

    controller.emit_state(
        ConnectionSetupState(
            phase=SetupPhase.READY,
            profiles=(FIRST_PROFILE, SECOND_PROFILE),
            selected_connection_uuid=SECOND_UUID,
        )
    )

    assert dialog.profile_combo.currentIndex() == 1
    assert dialog.profile_combo.currentData() == SECOND_UUID
    assert dialog.save_button.isEnabled() is True
    assert dialog.status_label.text() == ("The selected connection is ready to save.")


def test_user_selection_routes_exact_uuid(
    qtbot: QtBot,
) -> None:
    """User activation should send item data, not display text."""
    dialog, controller = create_dialog(qtbot)
    controller.emit_state(
        ConnectionSetupState(
            phase=SetupPhase.READY,
            profiles=(FIRST_PROFILE, SECOND_PROFILE),
        )
    )

    dialog.profile_combo.setCurrentIndex(1)
    dialog.profile_combo.activated.emit(1)

    assert controller.selection_requests == [SECOND_UUID]


def test_refresh_button_routes_request(
    qtbot: QtBot,
) -> None:
    """Refresh should remain a controller operation."""
    dialog, controller = create_dialog(
        qtbot,
        state=ConnectionSetupState(
            phase=SetupPhase.READY,
            profiles=(FIRST_PROFILE,),
        ),
    )

    qtbot.mouseClick(
        dialog.refresh_button,
        Qt.MouseButton.LeftButton,
    )

    assert controller.refresh_requests == 1


def test_save_requests_persistence_without_closing(
    qtbot: QtBot,
) -> None:
    """Save should wait for controller persistence confirmation."""
    dialog, controller = create_dialog(
        qtbot,
        state=ConnectionSetupState(
            phase=SetupPhase.READY,
            profiles=(FIRST_PROFILE,),
            selected_connection_uuid=FIRST_UUID,
        ),
    )
    dialog.show()

    qtbot.mouseClick(
        dialog.save_button,
        Qt.MouseButton.LeftButton,
    )

    assert controller.save_requests == 1
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.isVisible() is True


def test_settings_saved_accepts_dialog(
    qtbot: QtBot,
) -> None:
    """Successful persistence should close with Accepted."""
    dialog, controller = create_dialog(qtbot)
    dialog.show()
    saved_settings = object()

    with qtbot.waitSignal(
        dialog.accepted,
        timeout=1_000,
    ):
        controller.settings_saved.emit(saved_settings)

    assert dialog.result() == QDialog.DialogCode.Accepted


def test_dialog_forwards_saved_settings(
    qtbot: QtBot,
) -> None:
    """Runtime integration should receive the saved value."""
    dialog, controller = create_dialog(qtbot)
    saved_settings = object()

    with qtbot.waitSignal(
        dialog.settings_saved,
        timeout=1_000,
    ) as blocker:
        controller.settings_saved.emit(saved_settings)

    assert blocker.args == [saved_settings]


def test_cancel_rejects_dialog(
    qtbot: QtBot,
) -> None:
    """Cancel should close without requesting persistence."""
    dialog, controller = create_dialog(qtbot)
    dialog.show()

    qtbot.mouseClick(
        dialog.cancel_button,
        Qt.MouseButton.LeftButton,
    )

    assert dialog.result() == QDialog.DialogCode.Rejected
    assert controller.save_requests == 0


def test_error_state_displays_normalized_message(
    qtbot: QtBot,
) -> None:
    """Controller errors should be visible and retryable."""
    dialog, controller = create_dialog(qtbot)

    controller.emit_state(
        ConnectionSetupState(
            phase=SetupPhase.ERROR,
            error_message=("NetworkManager discovery failed with exit code 7."),
        )
    )

    assert dialog.profile_combo.isEnabled() is False
    assert dialog.refresh_button.isEnabled() is True
    assert dialog.save_button.isEnabled() is False
    assert dialog.status_label.text() == (
        "NetworkManager discovery failed with exit code 7."
    )


def test_empty_ready_state_explains_missing_profiles(
    qtbot: QtBot,
) -> None:
    """An empty discovery result should not look like a failure."""
    dialog, controller = create_dialog(qtbot)

    controller.emit_state(
        ConnectionSetupState(
            phase=SetupPhase.READY,
            profiles=(),
        )
    )

    assert dialog.profile_combo.isEnabled() is False
    assert dialog.save_button.isEnabled() is False
    assert dialog.status_label.text() == (
        "No supported VPN or WireGuard connections were found."
    )


def test_rejected_operation_is_shown_inline(
    qtbot: QtBot,
) -> None:
    """User-operation rejections should remain inside the dialog."""
    dialog, controller = create_dialog(qtbot)

    controller.operation_rejected.emit(
        "Select a NetworkManager connection before saving."
    )

    assert dialog.status_label.text() == (
        "Select a NetworkManager connection before saving."
    )
