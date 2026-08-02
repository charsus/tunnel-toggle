"""Tests for Tunnel Toggle domain models."""

from dataclasses import FrozenInstanceError

import pytest

from tunnel_toggle.models import (
    ApplicationState,
    ConnectionProfile,
    PresentationState,
    ProtectedApplicationStatus,
    ProtectionState,
    PublicIpState,
    TunnelState,
)


def test_application_state_has_safe_defaults() -> None:
    """A new application state should begin in unknown or disabled states."""
    state = ApplicationState()

    assert state.network.state is TunnelState.UNKNOWN
    assert state.protected_application.state is ProtectionState.UNKNOWN
    assert state.public_ip.state is PublicIpState.DISABLED
    assert state.presentation is PresentationState.UNKNOWN


@pytest.mark.parametrize("uuid", ["", "   "])
def test_connection_profile_requires_uuid(uuid: str) -> None:
    """A NetworkManager profile must have a non-empty UUID."""
    with pytest.raises(ValueError, match="UUID"):
        ConnectionProfile(
            uuid=uuid,
            name="Example VPN",
            connection_type="vpn",
        )


def test_protected_application_rejects_negative_process_count() -> None:
    """A process count cannot be negative."""
    with pytest.raises(ValueError, match="negative"):
        ProtectedApplicationStatus(process_count=-1)


def test_connection_profile_is_immutable() -> None:
    """Domain models should not be modified after creation."""
    profile = ConnectionProfile(
        uuid="12345678-1234-1234-1234-123456789abc",
        name="Example VPN",
        connection_type="vpn",
    )

    with pytest.raises(FrozenInstanceError):
        profile.name = "Changed VPN"  # type: ignore[misc]
