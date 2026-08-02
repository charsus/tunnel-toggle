"""Tests for the executable Qt entry point."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from tunnel_toggle import __version__
from tunnel_toggle.application import (
    APPLICATION_NAME,
    LOCK_FILENAME,
    LockFailureReason,
    SingleInstanceLock,
)
from tunnel_toggle.main import main


def test_smoke_test_initializes_and_exits(
    qapp: QApplication,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Smoke mode should initialize Qt without entering exec()."""
    del qapp
    lock_path = tmp_path / LOCK_FILENAME

    exit_code = main(
        ["--smoke-test"],
        lock_path=lock_path,
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == (f"{APPLICATION_NAME} {__version__}\n")
    assert captured.err == ""

    probe_lock = SingleInstanceLock(lock_path)

    try:
        assert probe_lock.acquire(timeout_ms=0).acquired is True
    finally:
        probe_lock.release()


def test_smoke_test_reports_existing_instance(
    qapp: QApplication,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A held lock should produce a normalized startup failure."""
    del qapp
    lock_path = tmp_path / LOCK_FILENAME
    existing_lock = SingleInstanceLock(lock_path)

    try:
        existing_result = existing_lock.acquire(timeout_ms=0)

        assert existing_result.acquired is True

        exit_code = main(
            ["--smoke-test"],
            lock_path=lock_path,
        )

        captured = capsys.readouterr()

        assert exit_code == 1
        assert captured.out == ""
        assert captured.err == ("Another Tunnel Toggle instance is already running.\n")
    finally:
        existing_lock.release()


def test_lock_contention_reason_remains_specific(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    """The entry point relies on an explicit contention reason."""
    del qapp
    lock_path = tmp_path / LOCK_FILENAME
    first_lock = SingleInstanceLock(lock_path)
    second_lock = SingleInstanceLock(lock_path)

    try:
        assert first_lock.acquire(timeout_ms=0).acquired is True

        result = second_lock.acquire(timeout_ms=0)

        assert result.failure_reason is (LockFailureReason.ALREADY_RUNNING)
    finally:
        second_lock.release()
        first_lock.release()
