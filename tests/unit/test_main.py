"""Tests for the executable Qt entry point."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

import tunnel_toggle.main as main_module
from tunnel_toggle import __version__
from tunnel_toggle.application import (
    APPLICATION_NAME,
    LOCK_FILENAME,
    LockFailureReason,
    SingleInstanceLock,
)
from tunnel_toggle.main import main
from tunnel_toggle.settings import (
    AppSettings,
    NetworkSettings,
    SettingsError,
)


class FakeSettingsRepository:
    """Settings repository identity used by entry-point tests."""

    def save(self, settings: AppSettings) -> None:
        del settings


class FakeApplicationRuntime(QObject):
    """Controllable runtime test double for the entry point."""

    quit_requested = Signal()

    def __init__(self) -> None:
        """Create a stopped fake runtime."""
        super().__init__()
        self.start_count = 0
        self.stop_count = 0

    def start(self) -> None:
        """Record runtime startup."""
        self.start_count += 1

    def stop(self) -> None:
        """Record runtime shutdown."""
        self.stop_count += 1


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


def test_smoke_test_does_not_load_permanent_services(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke mode should avoid settings and runtime services."""
    del qapp

    def fail_settings_load() -> AppSettings:
        raise AssertionError("Smoke mode loaded application settings.")

    def fail_runtime_creation(
        *,
        settings: AppSettings,
        repository: object,
    ) -> FakeApplicationRuntime:
        del settings, repository
        raise AssertionError("Smoke mode constructed the application runtime.")

    monkeypatch.setattr(
        main_module,
        "_load_application_settings",
        fail_settings_load,
    )
    monkeypatch.setattr(
        main_module,
        "create_application_runtime",
        fail_runtime_creation,
    )

    assert (
        main(
            ["--smoke-test"],
            lock_path=tmp_path / LOCK_FILENAME,
        )
        == 0
    )


def test_normal_start_loads_settings_and_runs_runtime(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ordinary startup should load settings and own one runtime."""
    del qapp
    lock_path = tmp_path / LOCK_FILENAME
    runtime = FakeApplicationRuntime()
    settings = AppSettings(
        setup_completed=True,
        network=NetworkSettings(
            connection_uuid=("44444444-4444-4444-4444-444444444444"),
        ),
    )
    repository = FakeSettingsRepository()
    received_settings: list[AppSettings] = []
    received_repositories: list[object] = []

    monkeypatch.setattr(
        main_module,
        "_load_application_settings",
        lambda: (repository, settings),
    )

    def create_runtime(
        *,
        settings: AppSettings,
        repository: object,
    ) -> FakeApplicationRuntime:
        received_settings.append(settings)
        received_repositories.append(repository)
        return runtime

    monkeypatch.setattr(
        main_module,
        "create_application_runtime",
        create_runtime,
    )
    monkeypatch.setattr(
        main_module,
        "_execute_application",
        lambda application: 23,
    )

    exit_code = main([], lock_path=lock_path)

    assert exit_code == 23
    assert received_settings == [settings]
    assert received_repositories == [repository]
    assert runtime.start_count == 1
    assert runtime.stop_count == 1

    probe_lock = SingleInstanceLock(lock_path)

    try:
        assert probe_lock.acquire(timeout_ms=0).acquired is True
    finally:
        probe_lock.release()


def test_settings_failure_prevents_runtime_start(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Unsafe or future settings should stop startup cleanly."""
    del qapp

    def fail_settings_load() -> AppSettings:
        raise SettingsError("Settings were created by a newer Tunnel Toggle version.")

    def fail_runtime_creation(
        *,
        settings: AppSettings,
        repository: object,
    ) -> FakeApplicationRuntime:
        del settings, repository
        raise AssertionError("Runtime was created after settings failed.")

    monkeypatch.setattr(
        main_module,
        "_load_application_settings",
        fail_settings_load,
    )
    monkeypatch.setattr(
        main_module,
        "create_application_runtime",
        fail_runtime_creation,
    )

    exit_code = main(
        [],
        lock_path=tmp_path / LOCK_FILENAME,
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == ("Settings were created by a newer Tunnel Toggle version.\n")


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
