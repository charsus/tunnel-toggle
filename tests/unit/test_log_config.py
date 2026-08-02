"""Tests for Tunnel Toggle logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tunnel_toggle.log_config import (
    LOGGER_NAME,
    LoggingConfigurationError,
    configure_logging,
    redact_text,
)


@pytest.fixture(autouse=True)
def reset_application_logger() -> None:
    """Remove application handlers before and after each test."""
    logger = logging.getLogger(LOGGER_NAME)

    for handler in logger.handlers:
        handler.close()

    logger.handlers.clear()

    yield

    for handler in logger.handlers:
        handler.close()

    logger.handlers.clear()


def test_redact_text_hides_sensitive_values() -> None:
    """Known sensitive values should not survive redaction."""
    text = (
        "uuid=12345678-1234-1234-1234-123456789abc "
        "ipv4=203.0.113.15 "
        "ipv6=2001:db8::10 "
        "password=hunter2 "
        "private_key: abcdef"
    )

    redacted = redact_text(text)

    assert "12345678-1234-1234-1234-123456789abc" not in redacted
    assert "203.0.113.15" not in redacted
    assert "2001:db8::10" not in redacted
    assert "hunter2" not in redacted
    assert "abcdef" not in redacted
    assert "[REDACTED_UUID]" in redacted
    assert "[REDACTED_IP]" in redacted
    assert "[REDACTED]" in redacted


def test_redact_text_replaces_home_directory(tmp_path: Path) -> None:
    """User-specific home paths should be shortened in logs."""
    home_directory = tmp_path / "home" / "example"
    text = f"Loaded {home_directory}/config/settings.ini"

    redacted = redact_text(
        text,
        home_directory=home_directory,
    )

    assert str(home_directory) not in redacted
    assert "~/config/settings.ini" in redacted


def test_configure_logging_writes_redacted_record(
    tmp_path: Path,
) -> None:
    """The rotating file handler should redact rendered messages."""
    log_path = configure_logging(
        log_directory=tmp_path,
        home_directory=Path("/home/example"),
    )

    logger = logging.getLogger(f"{LOGGER_NAME}.test")
    logger.info(
        "Connection %s reported IP %s from %s",
        "12345678-1234-1234-1234-123456789abc",
        "203.0.113.15",
        "/home/example/.config",
    )

    for handler in logging.getLogger(LOGGER_NAME).handlers:
        handler.flush()

    contents = log_path.read_text(encoding="utf-8")

    assert "[REDACTED_UUID]" in contents
    assert "[REDACTED_IP]" in contents
    assert "~/.config" in contents
    assert "12345678-1234-1234-1234-123456789abc" not in contents
    assert "203.0.113.15" not in contents
    assert "/home/example" not in contents


def test_reconfiguration_does_not_duplicate_handlers(
    tmp_path: Path,
) -> None:
    """Repeated configuration should replace existing handlers."""
    configure_logging(log_directory=tmp_path)
    configure_logging(log_directory=tmp_path)

    logger = logging.getLogger(LOGGER_NAME)

    assert len(logger.handlers) == 1


def test_debug_mode_adds_terminal_handler(tmp_path: Path) -> None:
    """Debug mode should add a stream handler for developers."""
    configure_logging(
        log_directory=tmp_path,
        debug=True,
    )

    logger = logging.getLogger(LOGGER_NAME)

    assert len(logger.handlers) == 2


def test_invalid_rotation_values_are_rejected(
    tmp_path: Path,
) -> None:
    """Invalid rotation settings should fail before configuration."""
    with pytest.raises(ValueError, match="max_bytes"):
        configure_logging(
            log_directory=tmp_path,
            max_bytes=0,
        )

    with pytest.raises(ValueError, match="backup_count"):
        configure_logging(
            log_directory=tmp_path,
            backup_count=-1,
        )


def test_unusable_log_path_raises_configuration_error(
    tmp_path: Path,
) -> None:
    """A file cannot be used where a log directory is required."""
    invalid_directory = tmp_path / "not-a-directory"
    invalid_directory.write_text("occupied", encoding="utf-8")

    with pytest.raises(LoggingConfigurationError, match="directory"):
        configure_logging(log_directory=invalid_directory)
