"""Executable Qt application entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path

from PySide6.QtWidgets import QApplication

from tunnel_toggle import __version__
from tunnel_toggle.application import (
    APPLICATION_NAME,
    APPLICATION_SLUG,
    SingleInstanceLock,
    configure_application_metadata,
)
from tunnel_toggle.runtime import (
    ApplicationRuntime,
    create_application_runtime,
)


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the Tunnel Toggle command-line parser."""
    parser = argparse.ArgumentParser(
        prog=APPLICATION_SLUG,
        description=("Control a selected NetworkManager tunnel from the system tray."),
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help=("initialize the Qt lifecycle and exit without entering the event loop"),
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    lock_path: str | Path | None = None,
) -> int:
    """Start Tunnel Toggle or run its non-blocking smoke test."""
    command_arguments = list(sys.argv[1:]) if argv is None else list(argv)
    options = build_argument_parser().parse_args(command_arguments)

    application = _get_or_create_application()
    configure_application_metadata()
    application.setQuitOnLastWindowClosed(False)

    instance_lock = SingleInstanceLock(lock_path)
    lock_result = instance_lock.acquire(timeout_ms=100)

    if not lock_result.acquired:
        print(
            lock_result.message or "Tunnel Toggle could not start.",
            file=sys.stderr,
        )
        return 1

    runtime: ApplicationRuntime | None = None
    quit_handler: Callable[[], None] | None = None
    stop_handler: Callable[[], None] | None = None

    try:
        if options.smoke_test:
            print(f"{APPLICATION_NAME} {__version__}")
            return 0

        runtime = create_application_runtime()
        quit_handler = application.quit
        stop_handler = runtime.stop

        runtime.quit_requested.connect(quit_handler)
        application.aboutToQuit.connect(stop_handler)

        runtime.start()

        return _execute_application(application)
    finally:
        if runtime is not None:
            if stop_handler is not None:
                with suppress(RuntimeError, TypeError):
                    application.aboutToQuit.disconnect(stop_handler)

            if quit_handler is not None:
                with suppress(RuntimeError, TypeError):
                    runtime.quit_requested.disconnect(quit_handler)

            runtime.stop()

        instance_lock.release()


def _execute_application(
    application: QApplication,
) -> int:
    """Enter the Qt event loop."""
    return application.exec()


def _get_or_create_application() -> QApplication:
    """Return the process QApplication, creating it when needed."""
    existing_application = QApplication.instance()

    if existing_application is None:
        return QApplication([APPLICATION_SLUG])

    if not isinstance(existing_application, QApplication):
        raise RuntimeError("A non-widget Qt application already exists.")

    return existing_application
