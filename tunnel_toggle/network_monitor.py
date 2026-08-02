"""Event-driven NetworkManager activity monitoring."""

from __future__ import annotations

from PySide6.QtCore import (
    QObject,
    QProcess,
    QProcessEnvironment,
    QStandardPaths,
    QTimer,
    Signal,
)


def monitor_arguments() -> tuple[str, ...]:
    """Return arguments for the long-running NetworkManager monitor."""
    return ("monitor",)


class NetworkManagerMonitor(QObject):
    """Watch NetworkManager activity without interpreting monitor text."""

    network_activity_detected = Signal()
    monitoring_started = Signal()
    monitoring_stopped = Signal()
    monitor_failed = Signal(str)

    def __init__(
        self,
        *,
        nmcli_executable: str | None = None,
        debounce_ms: int = 250,
        restart_delay_ms: int = 2_000,
        parent: QObject | None = None,
    ) -> None:
        """Create an event-driven NetworkManager monitor."""
        super().__init__(parent)

        if debounce_ms <= 0:
            raise ValueError("debounce_ms must be greater than zero.")

        if restart_delay_ms <= 0:
            raise ValueError("restart_delay_ms must be greater than zero.")

        self._nmcli_executable = (
            nmcli_executable
            if nmcli_executable is not None
            else QStandardPaths.findExecutable("nmcli")
        )
        self._debounce_ms = debounce_ms
        self._restart_delay_ms = restart_delay_ms
        self._process: QProcess | None = None
        self._desired_running = False

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._emit_debounced_activity)

        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.timeout.connect(self._restart_after_failure)

    @property
    def is_running(self) -> bool:
        """Return whether a monitor process exists."""
        return self._process is not None

    @property
    def restart_scheduled(self) -> bool:
        """Return whether an automatic restart is pending."""
        return self._restart_timer.isActive()

    def start(self) -> None:
        """Start monitoring NetworkManager activity."""
        if self._desired_running:
            return

        self._desired_running = True
        self._start_process()

    def stop(self) -> None:
        """Stop monitoring and cancel automatic restarts."""
        was_active = (
            self._desired_running
            or self._process is not None
            or self._restart_timer.isActive()
        )

        self._desired_running = False
        self._debounce_timer.stop()
        self._restart_timer.stop()

        process = self._process
        self._process = None

        if process is not None:
            process.blockSignals(True)
            process.kill()
            process.deleteLater()

        if was_active:
            self.monitoring_stopped.emit()

    def _start_process(self) -> None:
        """Start the long-running nmcli monitor process."""
        if not self._desired_running or self._process is not None:
            return

        if not self._nmcli_executable:
            self._desired_running = False
            self.monitor_failed.emit("The nmcli executable could not be found.")
            return

        process = QProcess(self)
        process.setProgram(self._nmcli_executable)
        process.setArguments(list(monitor_arguments()))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)

        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("LC_ALL", "C")
        environment.insert("LANG", "C")
        environment.insert("NO_COLOR", "1")
        process.setProcessEnvironment(environment)

        process.started.connect(self.monitoring_started)
        process.readyReadStandardOutput.connect(self._handle_standard_output)
        process.readyReadStandardError.connect(self._discard_standard_error)
        process.errorOccurred.connect(self._handle_process_error)
        process.finished.connect(self._handle_finished)

        self._process = process
        process.start()

    def _handle_standard_output(self) -> None:
        """Discard monitor text and debounce the activity event."""
        process = self._process

        if process is None:
            return

        output = process.readAllStandardOutput()

        if output.isEmpty():
            return

        self._debounce_timer.start(self._debounce_ms)

    def _discard_standard_error(self) -> None:
        """Drain stderr without exposing potentially sensitive text."""
        process = self._process

        if process is not None:
            process.readAllStandardError()

    def _emit_debounced_activity(self) -> None:
        """Emit one event after a burst of monitor output."""
        if self._desired_running and self._process is not None:
            self.network_activity_detected.emit()

    def _handle_process_error(
        self,
        error: QProcess.ProcessError,
    ) -> None:
        """Handle failure to launch the monitor."""
        if error != QProcess.ProcessError.FailedToStart or self._process is None:
            return

        self._desired_running = False
        self._cleanup_process()
        self.monitor_failed.emit("The nmcli monitor process could not be started.")

    def _handle_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        """Schedule a restart after unexpected monitor termination."""
        if self._process is None:
            return

        self._cleanup_process()

        if not self._desired_running:
            return

        self.monitor_failed.emit(
            f"NetworkManager monitor stopped unexpectedly with exit code {exit_code}."
        )
        self._restart_timer.start(self._restart_delay_ms)

    def _restart_after_failure(self) -> None:
        """Restart monitoring when it remains desired."""
        if self._desired_running:
            self._start_process()

    def _cleanup_process(self) -> None:
        """Release the current monitor process."""
        process = self._process
        self._process = None

        if process is not None:
            process.deleteLater()
