"""Privacy-conscious logging configuration for Tunnel Toggle."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final

from PySide6.QtCore import QStandardPaths

LOGGER_NAME: Final = "tunnel_toggle"
LOG_FILE_NAME: Final = "tunnel-toggle.log"
DEFAULT_MAX_BYTES: Final = 1_048_576
DEFAULT_BACKUP_COUNT: Final = 5

_UUID_PATTERN = re.compile(
    r"(?<![0-9A-Fa-f])"
    r"[0-9A-Fa-f]{8}-"
    r"[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{12}"
    r"(?![0-9A-Fa-f])"
)

_IPV4_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:"
    r"(?:25[0-5]|2[0-4]\d|1?\d?\d)\."
    r"){3}"
    r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?!\d)"
)

_IPV6_PATTERN = re.compile(
    r"(?<![0-9A-Fa-f:])"
    r"(?:"
    r"(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,7}:|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,5}"
    r"(?::[0-9A-Fa-f]{1,4}){1,2}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,4}"
    r"(?::[0-9A-Fa-f]{1,4}){1,3}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,3}"
    r"(?::[0-9A-Fa-f]{1,4}){1,4}|"
    r"(?:[0-9A-Fa-f]{1,4}:){1,2}"
    r"(?::[0-9A-Fa-f]{1,4}){1,5}|"
    r"[0-9A-Fa-f]{1,4}:"
    r"(?:(?::[0-9A-Fa-f]{1,4}){1,6})|"
    r":(?:(?::[0-9A-Fa-f]{1,4}){1,7}|:)"
    r")"
    r"(?![0-9A-Fa-f:])"
)

_SECRET_PATTERN = re.compile(
    r"(?i)"
    r"\b("
    r"password|passwd|token|secret|"
    r"private[_ -]?key|preshared[_ -]?key"
    r")"
    r"(\s*[:=]\s*)"
    r"([^\s,;]+)"
)


class LoggingConfigurationError(RuntimeError):
    """Raised when application logging cannot be configured safely."""


def redact_text(
    text: str,
    *,
    home_directory: Path | None = None,
) -> str:
    """Remove common sensitive values from log text."""
    redacted = text

    if home_directory is not None:
        home_text = str(home_directory)

        if home_text:
            redacted = redacted.replace(home_text, "~")

    redacted = _SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        redacted,
    )
    redacted = _UUID_PATTERN.sub("[REDACTED_UUID]", redacted)
    redacted = _IPV4_PATTERN.sub("[REDACTED_IP]", redacted)
    redacted = _IPV6_PATTERN.sub("[REDACTED_IP]", redacted)

    return redacted


class UtcRedactingFormatter(logging.Formatter):
    """Format records in UTC and redact sensitive values."""

    def __init__(self, *, home_directory: Path | None = None) -> None:
        """Create a formatter with an optional home-path replacement."""
        super().__init__(fmt=("%(asctime)s %(levelname)s %(name)s %(message)s"))
        self._home_directory = home_directory

    def formatTime(
        self,
        record: logging.LogRecord,
        datefmt: str | None = None,
    ) -> str:
        """Return an ISO 8601 timestamp in UTC."""
        timestamp = datetime.fromtimestamp(
            record.created,
            tz=UTC,
        )

        if datefmt is not None:
            return timestamp.strftime(datefmt)

        return timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def format(self, record: logging.LogRecord) -> str:
        """Format and then redact the complete rendered record."""
        rendered = super().format(record)
        return redact_text(
            rendered,
            home_directory=self._home_directory,
        )


def default_log_directory() -> Path:
    """Return the XDG-aware application log directory."""
    state_location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.StateLocation
    )

    if not state_location:
        raise LoggingConfigurationError("Qt did not provide a writable state location.")

    return Path(state_location) / "logs"


def configure_logging(
    *,
    log_directory: Path | None = None,
    debug: bool = False,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    home_directory: Path | None = None,
) -> Path:
    """Configure rotating application logging and return the log path."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero.")

    if backup_count < 0:
        raise ValueError("backup_count must not be negative.")

    directory = log_directory if log_directory is not None else default_log_directory()

    try:
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)
    except OSError as error:
        raise LoggingConfigurationError(
            f"Could not prepare the log directory: {error}"
        ) from error

    log_path = directory / LOG_FILE_NAME
    formatter = UtcRedactingFormatter(
        home_directory=home_directory,
    )

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    for handler in logger.handlers:
        handler.close()

    logger.handlers.clear()

    try:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        log_path.chmod(0o600)
    except OSError as error:
        raise LoggingConfigurationError(
            f"Could not create the application log: {error}"
        ) from error

    file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if debug:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.info(
        "LOGGING_CONFIGURED level=%s",
        logging.getLevelName(logger.level),
    )

    return log_path
