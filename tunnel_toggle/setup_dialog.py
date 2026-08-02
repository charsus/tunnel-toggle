"""Presentation-only dialog for selecting a tunnel profile."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tunnel_toggle.models import ConnectionProfile
from tunnel_toggle.setup_controller import (
    ConnectionSetupController,
    ConnectionSetupState,
    SetupPhase,
)

DIALOG_TITLE = "Configure Tunnel Toggle"


class ConnectionSetupDialog(QDialog):
    """Display setup state and route user actions to its controller."""

    settings_saved = Signal(object)

    def __init__(
        self,
        *,
        controller: ConnectionSetupController,
        parent: QWidget | None = None,
    ) -> None:
        """Create a setup dialog without starting discovery."""
        super().__init__(parent)

        self._controller = controller

        self.setWindowTitle(DIALOG_TITLE)
        self.setModal(True)
        self.setMinimumWidth(460)

        introduction = QLabel(
            "Choose the NetworkManager VPN or WireGuard "
            "connection that Tunnel Toggle should control.",
            self,
        )
        introduction.setWordWrap(True)

        connection_label = QLabel("&Connection:", self)

        self._profile_combo = QComboBox(self)
        self._profile_combo.setEnabled(False)
        connection_label.setBuddy(self._profile_combo)

        self._refresh_button = QPushButton("Refresh", self)

        selection_layout = QHBoxLayout()
        selection_layout.addWidget(connection_label)
        selection_layout.addWidget(self._profile_combo, 1)
        selection_layout.addWidget(self._refresh_button)

        self._status_label = QLabel(self)
        self._status_label.setWordWrap(True)
        self._status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )

        save_button = self._button_box.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = self._button_box.button(QDialogButtonBox.StandardButton.Cancel)

        if save_button is None or cancel_button is None:
            raise RuntimeError("The setup dialog could not create its buttons.")

        self._save_button = save_button
        self._cancel_button = cancel_button
        self._save_button.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addWidget(introduction)
        layout.addLayout(selection_layout)
        layout.addWidget(self._status_label)
        layout.addStretch()
        layout.addWidget(self._button_box)

        self._refresh_button.clicked.connect(self._handle_refresh_clicked)
        self._profile_combo.activated.connect(self._handle_profile_activated)
        self._button_box.accepted.connect(self._handle_save_requested)
        self._button_box.rejected.connect(self.reject)

        self._controller.state_changed.connect(self._handle_state_changed)
        self._controller.settings_saved.connect(self._handle_settings_saved)
        self._controller.operation_rejected.connect(self._handle_operation_rejected)

        self._apply_state(self._controller.state)

    @property
    def profile_combo(self) -> QComboBox:
        """Return the profile-selection control."""
        return self._profile_combo

    @property
    def refresh_button(self) -> QPushButton:
        """Return the profile refresh button."""
        return self._refresh_button

    @property
    def status_label(self) -> QLabel:
        """Return the inline setup status label."""
        return self._status_label

    @property
    def button_box(self) -> QDialogButtonBox:
        """Return the dialog's standard button box."""
        return self._button_box

    @property
    def save_button(self) -> QPushButton:
        """Return the standard Save button."""
        return self._save_button

    @property
    def cancel_button(self) -> QPushButton:
        """Return the standard Cancel button."""
        return self._cancel_button

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh profiles whenever the dialog is opened."""
        super().showEvent(event)

        if self._controller.state.phase is not SetupPhase.LOADING:
            self._controller.refresh_profiles()

    @Slot(bool)
    def _handle_refresh_clicked(self, checked: bool) -> None:
        """Route a Refresh button click to the controller."""
        del checked
        self._controller.refresh_profiles()

    @Slot(int)
    def _handle_profile_activated(self, index: int) -> None:
        """Route a user-selected profile UUID to the controller."""
        if index < 0:
            return

        connection_uuid = self._profile_combo.itemData(index)

        if not isinstance(connection_uuid, str):
            self._status_label.setText("The selected connection contains invalid data.")
            self._save_button.setEnabled(False)
            return

        self._controller.select_connection(connection_uuid)

    @Slot()
    def _handle_save_requested(self) -> None:
        """Request persistence without closing prematurely."""
        self._controller.save_selection()

    @Slot(object)
    def _handle_state_changed(self, state: object) -> None:
        """Render an immutable controller state."""
        if not isinstance(state, ConnectionSetupState):
            raise TypeError("Connection setup emitted an invalid state.")

        self._apply_state(state)

    @Slot(object)
    def _handle_settings_saved(self, settings: object) -> None:
        """Close only after persistence succeeds."""
        self.settings_saved.emit(settings)
        self.accept()

    @Slot(str)
    def _handle_operation_rejected(self, message: str) -> None:
        """Display a normalized rejected-operation message."""
        self._status_label.setText(message)

    def _apply_state(
        self,
        state: ConnectionSetupState,
    ) -> None:
        """Render one complete setup-controller state."""
        self._render_profiles(
            state.profiles,
            state.selected_connection_uuid,
        )

        if state.phase is SetupPhase.IDLE:
            self._profile_combo.setEnabled(False)
            self._refresh_button.setEnabled(True)
            self._save_button.setEnabled(False)
            self._status_label.setText("Refresh to search for supported connections.")
            return

        if state.phase is SetupPhase.LOADING:
            self._profile_combo.setEnabled(False)
            self._refresh_button.setEnabled(False)
            self._save_button.setEnabled(False)
            self._status_label.setText("Searching for VPN and WireGuard connections…")
            return

        if state.phase is SetupPhase.ERROR:
            self._profile_combo.setEnabled(False)
            self._refresh_button.setEnabled(True)
            self._save_button.setEnabled(False)
            self._status_label.setText(
                state.error_message or "Connection discovery failed."
            )
            return

        has_profiles = bool(state.profiles)
        has_selection = (
            state.selected_connection_uuid is not None
            and self._profile_combo.currentIndex() >= 0
        )

        self._profile_combo.setEnabled(has_profiles)
        self._refresh_button.setEnabled(True)
        self._save_button.setEnabled(has_selection)

        if not has_profiles:
            self._status_label.setText(
                "No supported VPN or WireGuard connections were found."
            )
        elif has_selection:
            self._status_label.setText("The selected connection is ready to save.")
        else:
            self._status_label.setText("Choose a connection to continue.")

    def _render_profiles(
        self,
        profiles: tuple[ConnectionProfile, ...],
        selected_connection_uuid: str | None,
    ) -> None:
        """Rebuild profile choices while preserving UUID identity."""
        previous_block_state = self._profile_combo.blockSignals(True)

        try:
            self._profile_combo.clear()
            selected_index = -1

            for index, profile in enumerate(profiles):
                self._profile_combo.addItem(
                    self._profile_label(profile),
                    profile.uuid,
                )

                if profile.uuid == selected_connection_uuid:
                    selected_index = index

            self._profile_combo.setCurrentIndex(selected_index)
        finally:
            self._profile_combo.blockSignals(previous_block_state)

    @staticmethod
    def _profile_label(profile: ConnectionProfile) -> str:
        """Return a readable label without using it as identity."""
        if profile.connection_type == "wireguard":
            connection_type = "WireGuard"
        elif profile.connection_type == "vpn":
            connection_type = "VPN"
        else:
            connection_type = profile.connection_type

        return f"{profile.name} — {connection_type}"
