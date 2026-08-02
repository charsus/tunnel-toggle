"""Minimal system tray shell for Tunnel Toggle."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QStyle,
    QSystemTrayIcon,
)

from tunnel_toggle.application import APPLICATION_NAME

INITIAL_STATUS = "Starting…"
THEME_ICON_NAME = "network-vpn"


class TrayShell(QObject):
    """Own the persistent tray icon and its minimal context menu."""

    quit_requested = Signal()

    def __init__(
        self,
        *,
        parent: QObject | None = None,
    ) -> None:
        """Create an initially hidden system tray shell."""
        super().__init__(parent)

        self._menu = QMenu(APPLICATION_NAME)

        self._status_action = QAction(self._menu)
        self._status_action.setEnabled(False)

        self._quit_action = QAction("Quit", self._menu)
        self._quit_action.triggered.connect(self._handle_quit_triggered)

        self._menu.addAction(self._status_action)
        self._menu.addSeparator()
        self._menu.addAction(self._quit_action)

        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(self._create_icon())
        self._tray_icon.setContextMenu(self._menu)

        self.set_status(INITIAL_STATUS)

    @property
    def menu(self) -> QMenu:
        """Return the tray context menu."""
        return self._menu

    @property
    def status_action(self) -> QAction:
        """Return the read-only status action."""
        return self._status_action

    @property
    def quit_action(self) -> QAction:
        """Return the action used to request application shutdown."""
        return self._quit_action

    @property
    def tray_icon(self) -> QSystemTrayIcon:
        """Return the underlying Qt tray icon."""
        return self._tray_icon

    @property
    def is_visible(self) -> bool:
        """Return whether Qt considers the tray icon visible."""
        return self._tray_icon.isVisible()

    def set_status(self, status: str) -> None:
        """Update the menu status and tray tooltip."""
        normalized_status = status.strip()

        if not normalized_status:
            raise ValueError("status must not be empty.")

        self._status_action.setText(f"Status: {normalized_status}")
        self._tray_icon.setToolTip(f"{APPLICATION_NAME}: {normalized_status}")

    def show(self) -> None:
        """Make the tray entry visible."""
        self._tray_icon.show()

    def hide(self) -> None:
        """Hide the tray entry."""
        self._tray_icon.hide()

    @Slot(bool)
    def _handle_quit_triggered(self, checked: bool) -> None:
        """Translate QAction's checked argument into a simple signal."""
        del checked
        self.quit_requested.emit()

    @staticmethod
    def _create_icon() -> QIcon:
        """Use the desktop VPN icon with a standard fallback."""
        icon = QIcon.fromTheme(THEME_ICON_NAME)

        if not icon.isNull():
            return icon

        return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
