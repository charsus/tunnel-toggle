"""NetworkManager connection discovery and output parsing."""

from __future__ import annotations

from typing import Final
from uuid import UUID

from tunnel_toggle.models import ConnectionProfile

SUPPORTED_CONNECTION_TYPES: Final[frozenset[str]] = frozenset(
    {
        "vpn",
        "wireguard",
    }
)


class NetworkManagerParseError(ValueError):
    """Raised when machine-readable NetworkManager output is invalid."""


def discovery_arguments() -> tuple[str, ...]:
    """Return arguments for machine-readable connection discovery."""
    return (
        "--terse",
        "--escape",
        "yes",
        "--fields",
        "UUID,TYPE,NAME",
        "connection",
        "show",
    )


def parse_connection_profiles(output: str) -> tuple[ConnectionProfile, ...]:
    """Parse supported VPN and WireGuard profiles from nmcli output."""
    profiles_by_uuid: dict[str, ConnectionProfile] = {}

    for line_number, raw_line in enumerate(output.splitlines(), start=1):
        if not raw_line:
            continue

        try:
            uuid_text, connection_type, name = _split_escaped_fields(
                raw_line,
                expected_fields=3,
            )
            normalized_uuid = str(UUID(uuid_text.strip()))
        except (NetworkManagerParseError, ValueError) as error:
            raise NetworkManagerParseError(
                f"Invalid NetworkManager discovery output on line {line_number}."
            ) from error

        normalized_type = connection_type.strip().lower()

        if normalized_type not in SUPPORTED_CONNECTION_TYPES:
            continue

        try:
            profile = ConnectionProfile(
                uuid=normalized_uuid,
                name=name,
                connection_type=normalized_type,
            )
        except ValueError as error:
            raise NetworkManagerParseError(
                f"Invalid NetworkManager connection profile on line {line_number}."
            ) from error

        profiles_by_uuid.setdefault(profile.uuid, profile)

    return tuple(
        sorted(
            profiles_by_uuid.values(),
            key=lambda profile: (
                profile.name.casefold(),
                profile.uuid,
            ),
        )
    )


def _split_escaped_fields(
    line: str,
    *,
    expected_fields: int,
) -> tuple[str, ...]:
    """Split one escaped nmcli terse-output line into fields."""
    fields: list[str] = []
    current: list[str] = []
    escaped = False

    for character in line:
        if escaped:
            current.append(character)
            escaped = False
            continue

        if character == "\\":
            escaped = True
            continue

        if character == ":":
            fields.append("".join(current))
            current.clear()
            continue

        current.append(character)

    if escaped:
        raise NetworkManagerParseError(
            "A field ended with an incomplete escape sequence."
        )

    fields.append("".join(current))

    if len(fields) != expected_fields:
        raise NetworkManagerParseError(
            f"Expected {expected_fields} fields but received {len(fields)}."
        )

    return tuple(fields)
