"""Tests for NetworkManager monitor configuration."""

import pytest

from tunnel_toggle.network_monitor import (
    NetworkManagerMonitor,
    monitor_arguments,
)


def test_monitor_arguments_start_general_monitor() -> None:
    """The monitor should subscribe to general NetworkManager events."""
    assert monitor_arguments() == ("monitor",)


@pytest.mark.parametrize(
    ("argument_name", "arguments"),
    [
        (
            "debounce_ms",
            {"debounce_ms": 0},
        ),
        (
            "restart_delay_ms",
            {"restart_delay_ms": 0},
        ),
    ],
)
def test_monitor_rejects_invalid_timing_values(
    argument_name: str,
    arguments: dict[str, int],
) -> None:
    """Monitor timing values must be positive."""
    with pytest.raises(ValueError, match=argument_name):
        NetworkManagerMonitor(**arguments)
