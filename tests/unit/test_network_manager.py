"""Tests for NetworkManager connection discovery parsing."""

import pytest

from tunnel_toggle.network_manager import (
    NetworkManagerParseError,
    discovery_arguments,
    parse_active_connection_uuids,
    parse_connection_profiles,
    state_query_arguments,
)


def test_discovery_arguments_request_machine_readable_fields() -> None:
    """Discovery should request only the required escaped fields."""
    assert discovery_arguments() == (
        "--terse",
        "--escape",
        "yes",
        "--fields",
        "UUID,TYPE,NAME",
        "connection",
        "show",
    )


def test_parse_connection_profiles_filters_unsupported_types() -> None:
    """Only VPN and WireGuard profiles should be returned."""
    output = "\n".join(
        [
            "11111111-1111-1111-1111-111111111111:ethernet:Wired",
            "22222222-2222-2222-2222-222222222222:vpn:Work VPN",
            "33333333-3333-3333-3333-333333333333:wifi:Home Wi-Fi",
            "44444444-4444-4444-4444-444444444444:wireguard:Home Tunnel",
        ]
    )

    profiles = parse_connection_profiles(output)

    assert [profile.connection_type for profile in profiles] == [
        "wireguard",
        "vpn",
    ]
    assert [profile.name for profile in profiles] == [
        "Home Tunnel",
        "Work VPN",
    ]


def test_parse_connection_profiles_decodes_escaped_names() -> None:
    """Escaped colons and backslashes should remain in profile names."""
    output = "\n".join(
        [
            (
                "11111111-1111-1111-1111-111111111111:"
                r"vpn:Office\:Primary"
            ),
            (
                "22222222-2222-2222-2222-222222222222:"
                r"wireguard:Home\\Tunnel"
            ),
        ]
    )

    profiles = parse_connection_profiles(output)

    assert profiles[0].name == r"Home\Tunnel"
    assert profiles[1].name == "Office:Primary"


def test_parse_connection_profiles_normalizes_uuid_and_type() -> None:
    """UUID and connection type output should be normalized."""
    output = "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA:VPN:Example VPN"

    profiles = parse_connection_profiles(output)

    assert len(profiles) == 1
    assert profiles[0].uuid == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert profiles[0].connection_type == "vpn"


def test_parse_connection_profiles_removes_duplicate_uuid() -> None:
    """Duplicate rows should not produce duplicate selections."""
    output = "\n".join(
        [
            "11111111-1111-1111-1111-111111111111:vpn:Example VPN",
            "11111111-1111-1111-1111-111111111111:vpn:Example VPN",
        ]
    )

    profiles = parse_connection_profiles(output)

    assert len(profiles) == 1


@pytest.mark.parametrize(
    "output",
    [
        "not-a-uuid:vpn:Example VPN",
        "11111111-1111-1111-1111-111111111111:vpn",
        ("11111111-1111-1111-1111-111111111111:vpn:Example VPN\\"),
    ],
)
def test_parse_connection_profiles_rejects_malformed_output(
    output: str,
) -> None:
    """Malformed machine-readable output should fail explicitly."""
    with pytest.raises(NetworkManagerParseError, match="line 1"):
        parse_connection_profiles(output)


def test_state_query_arguments_request_active_connections() -> None:
    """State queries should request active UUID and type fields."""
    assert state_query_arguments() == (
        "--terse",
        "--escape",
        "yes",
        "--fields",
        "UUID,TYPE",
        "connection",
        "show",
        "--active",
    )


def test_parse_active_connection_uuids_filters_types() -> None:
    """Only active VPN and WireGuard UUIDs should be retained."""
    output = "\n".join(
        [
            "11111111-1111-1111-1111-111111111111:ethernet",
            "22222222-2222-2222-2222-222222222222:vpn",
            "33333333-3333-3333-3333-333333333333:wifi",
            "44444444-4444-4444-4444-444444444444:wireguard",
        ]
    )

    active_uuids = parse_active_connection_uuids(output)

    assert active_uuids == frozenset(
        {
            "22222222-2222-2222-2222-222222222222",
            "44444444-4444-4444-4444-444444444444",
        }
    )


def test_parse_active_connection_uuids_normalizes_values() -> None:
    """Active UUIDs and types should be normalized."""
    output = "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA:VPN"

    active_uuids = parse_active_connection_uuids(output)

    assert active_uuids == frozenset({"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"})


def test_parse_active_connection_uuids_removes_duplicates() -> None:
    """Duplicate active rows should produce one UUID."""
    output = "\n".join(
        [
            "11111111-1111-1111-1111-111111111111:vpn",
            "11111111-1111-1111-1111-111111111111:vpn",
        ]
    )

    active_uuids = parse_active_connection_uuids(output)

    assert active_uuids == frozenset({"11111111-1111-1111-1111-111111111111"})


@pytest.mark.parametrize(
    "output",
    [
        "not-a-uuid:vpn",
        "11111111-1111-1111-1111-111111111111",
        "11111111-1111-1111-1111-111111111111:vpn:extra",
    ],
)
def test_parse_active_connection_uuids_rejects_malformed_output(
    output: str,
) -> None:
    """Malformed active-state output should fail explicitly."""
    with pytest.raises(NetworkManagerParseError, match="line 1"):
        parse_active_connection_uuids(output)
