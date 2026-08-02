"""Tests for Qt application lifecycle support."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from tunnel_toggle import __version__
from tunnel_toggle.application import (
    APPLICATION_NAME,
    LOCK_FILENAME,
    ORGANIZATION_DOMAIN,
    ORGANIZATION_NAME,
    LockFailureReason,
    SingleInstanceLock,
    application_lock_path,
    configure_application_metadata,
)


def test_configure_application_metadata() -> None:
    """Qt should receive stable Tunnel Toggle metadata."""
    configure_application_metadata()

    assert QCoreApplication.applicationName() == APPLICATION_NAME
    assert QCoreApplication.applicationVersion() == __version__
    assert QCoreApplication.organizationName() == ORGANIZATION_NAME
    assert QCoreApplication.organizationDomain() == ORGANIZATION_DOMAIN


def test_application_lock_path_uses_runtime_directory(
    tmp_path: Path,
) -> None:
    """The lock filename should be stable inside the runtime path."""
    assert application_lock_path(tmp_path) == (tmp_path / LOCK_FILENAME)


def test_lock_creates_missing_parent_directory(
    tmp_path: Path,
) -> None:
    """Lock acquisition should prepare its private parent path."""
    lock_path = tmp_path / "missing" / "runtime" / LOCK_FILENAME
    lock = SingleInstanceLock(lock_path)

    try:
        result = lock.acquire(timeout_ms=0)

        assert result.acquired is True
        assert result.failure_reason is None
        assert result.message is None
        assert lock_path.parent.is_dir()
        assert lock.is_acquired is True
    finally:
        lock.release()


def test_lock_acquisition_is_idempotent(
    tmp_path: Path,
) -> None:
    """Repeated acquisition by one guard should not relock Qt."""
    lock = SingleInstanceLock(tmp_path / LOCK_FILENAME)

    try:
        first_result = lock.acquire(timeout_ms=0)
        second_result = lock.acquire(timeout_ms=0)

        assert first_result.acquired is True
        assert second_result.acquired is True
        assert lock.is_acquired is True
    finally:
        lock.release()


def test_second_guard_reports_existing_instance(
    tmp_path: Path,
) -> None:
    """A second guard should identify an already-running instance."""
    lock_path = tmp_path / LOCK_FILENAME
    first_lock = SingleInstanceLock(lock_path)
    second_lock = SingleInstanceLock(lock_path)

    try:
        first_result = first_lock.acquire(timeout_ms=0)
        second_result = second_lock.acquire(timeout_ms=0)

        assert first_result.acquired is True
        assert second_result.acquired is False
        assert second_result.failure_reason is (LockFailureReason.ALREADY_RUNNING)
        assert second_result.message == (
            "Another Tunnel Toggle instance is already running."
        )
        assert first_lock.is_acquired is True
        assert second_lock.is_acquired is False
    finally:
        second_lock.release()
        first_lock.release()


def test_released_lock_can_be_acquired_by_another_guard(
    tmp_path: Path,
) -> None:
    """Explicit release should permit a later application instance."""
    lock_path = tmp_path / LOCK_FILENAME
    first_lock = SingleInstanceLock(lock_path)
    second_lock = SingleInstanceLock(lock_path)

    try:
        assert first_lock.acquire(timeout_ms=0).acquired is True
        first_lock.release()

        result = second_lock.acquire(timeout_ms=0)

        assert result.acquired is True
        assert second_lock.is_acquired is True
    finally:
        second_lock.release()
        first_lock.release()


def test_release_is_idempotent(
    tmp_path: Path,
) -> None:
    """Releasing an unlocked guard should be harmless."""
    lock = SingleInstanceLock(tmp_path / LOCK_FILENAME)

    lock.release()
    lock.release()

    assert lock.is_acquired is False


def test_lock_rejects_negative_timeout(
    tmp_path: Path,
) -> None:
    """The application must never request an indefinite startup wait."""
    lock = SingleInstanceLock(tmp_path / LOCK_FILENAME)

    with pytest.raises(
        ValueError,
        match="greater than or equal to zero",
    ):
        lock.acquire(timeout_ms=-1)

    assert lock.is_acquired is False
