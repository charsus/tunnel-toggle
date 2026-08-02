"""Qt application metadata and single-instance lifecycle support."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QLockFile,
    QStandardPaths,
)

from tunnel_toggle import __version__

APPLICATION_NAME = "Tunnel Toggle"
APPLICATION_SLUG = "tunnel-toggle"
ORGANIZATION_NAME = "charsus"
ORGANIZATION_DOMAIN = "github.com"
LOCK_FILENAME = f"{APPLICATION_SLUG}.lock"


class LockFailureReason(StrEnum):
    """Normalized reasons why the application lock was not acquired."""

    ALREADY_RUNNING = "already_running"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class LockAcquisitionResult:
    """Result of attempting to acquire the single-instance lock."""

    acquired: bool
    failure_reason: LockFailureReason | None = None
    message: str | None = None


def configure_application_metadata() -> None:
    """Configure stable metadata used by Qt services."""
    QCoreApplication.setApplicationName(APPLICATION_NAME)
    QCoreApplication.setApplicationVersion(__version__)
    QCoreApplication.setOrganizationName(ORGANIZATION_NAME)
    QCoreApplication.setOrganizationDomain(ORGANIZATION_DOMAIN)


def application_lock_path(
    runtime_directory: str | Path | None = None,
) -> Path:
    """Return the per-user single-instance lock path."""
    if runtime_directory is None:
        location = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.RuntimeLocation
        )

        if not location:
            raise RuntimeError("Qt could not determine the user runtime directory.")

        directory = Path(location)
    else:
        directory = Path(runtime_directory)

    return directory / LOCK_FILENAME


class SingleInstanceLock:
    """Prevent more than one Tunnel Toggle process from running."""

    def __init__(
        self,
        lock_path: str | Path | None = None,
    ) -> None:
        """Create an initially unlocked single-instance guard."""
        self._path = (
            Path(lock_path) if lock_path is not None else application_lock_path()
        )
        self._lock_file = QLockFile(str(self._path))
        self._lock_file.setStaleLockTime(0)
        self._acquired = False

    @property
    def path(self) -> Path:
        """Return the filesystem path used for locking."""
        return self._path

    @property
    def is_acquired(self) -> bool:
        """Return whether this guard currently owns the lock."""
        return self._acquired and self._lock_file.isLocked()

    def acquire(
        self,
        *,
        timeout_ms: int = 100,
    ) -> LockAcquisitionResult:
        """Attempt to acquire the lock without blocking indefinitely."""
        if timeout_ms < 0:
            raise ValueError("timeout_ms must be greater than or equal to zero.")

        if self.is_acquired:
            return LockAcquisitionResult(acquired=True)

        directory_result = self._ensure_parent_directory()

        if directory_result is not None:
            return directory_result

        if self._lock_file.tryLock(timeout_ms):
            self._acquired = True
            return LockAcquisitionResult(acquired=True)

        return self._failure_result(self._lock_file.error())

    def release(self) -> None:
        """Release the lock when this guard owns it."""
        if not self.is_acquired:
            self._acquired = False
            return

        self._lock_file.unlock()
        self._acquired = False

    def _ensure_parent_directory(
        self,
    ) -> LockAcquisitionResult | None:
        """Create the lock parent directory when necessary."""
        try:
            self._path.parent.mkdir(
                mode=0o700,
                parents=True,
                exist_ok=True,
            )
        except PermissionError:
            return LockAcquisitionResult(
                acquired=False,
                failure_reason=LockFailureReason.PERMISSION_DENIED,
                message=("Tunnel Toggle cannot create its single-instance lock."),
            )
        except OSError:
            return LockAcquisitionResult(
                acquired=False,
                failure_reason=LockFailureReason.UNKNOWN,
                message=("Tunnel Toggle could not prepare its single-instance lock."),
            )

        return None

    @staticmethod
    def _failure_result(
        error: QLockFile.LockError,
    ) -> LockAcquisitionResult:
        """Normalize a Qt lock error for the future user interface."""
        if error is QLockFile.LockError.LockFailedError:
            return LockAcquisitionResult(
                acquired=False,
                failure_reason=LockFailureReason.ALREADY_RUNNING,
                message=("Another Tunnel Toggle instance is already running."),
            )

        if error is QLockFile.LockError.PermissionError:
            return LockAcquisitionResult(
                acquired=False,
                failure_reason=LockFailureReason.PERMISSION_DENIED,
                message=("Tunnel Toggle cannot create its single-instance lock."),
            )

        return LockAcquisitionResult(
            acquired=False,
            failure_reason=LockFailureReason.UNKNOWN,
            message=("Tunnel Toggle could not acquire its single-instance lock."),
        )
