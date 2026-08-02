#!/usr/bin/env python3
"""Deterministic fake nmcli used by integration tests."""

from __future__ import annotations

import os
import sys
import time

DISCOVERY_ARGUMENTS = [
    "--terse",
    "--escape",
    "yes",
    "--fields",
    "UUID,TYPE,NAME",
    "connection",
    "show",
]

STATE_QUERY_ARGUMENTS = [
    "--terse",
    "--escape",
    "yes",
    "--fields",
    "UUID,TYPE",
    "connection",
    "show",
    "--active",
]

TARGET_UUID = "44444444-4444-4444-4444-444444444444"

CONNECT_ARGUMENTS = [
    "connection",
    "up",
    "uuid",
    TARGET_UUID,
]

DISCONNECT_ARGUMENTS = [
    "connection",
    "down",
    "uuid",
    TARGET_UUID,
]


def main() -> int:
    """Return deterministic output for the requested test mode."""
    arguments = sys.argv[1:]

    if arguments == DISCOVERY_ARGUMENTS:
        operation = "discovery"
    elif arguments == STATE_QUERY_ARGUMENTS:
        operation = "state"
    elif arguments == CONNECT_ARGUMENTS:
        operation = "connect"
    elif arguments == DISCONNECT_ARGUMENTS:
        operation = "disconnect"
    else:
        print("Unexpected arguments.", file=sys.stderr)
        return 64

    if os.environ.get("LC_ALL") != "C":
        print("LC_ALL was not normalized.", file=sys.stderr)
        return 65

    if os.environ.get("LANG") != "C":
        print("LANG was not normalized.", file=sys.stderr)
        return 66

    if os.environ.get("NO_COLOR") != "1":
        print("NO_COLOR was not enabled.", file=sys.stderr)
        return 67

    mode = os.environ.get(
        "TUNNEL_TOGGLE_FAKE_NMCLI_MODE",
        "success",
    )

    if mode == "timeout":
        time.sleep(2)
        return 0

    if operation == "discovery":
        return run_discovery(mode)

    if operation == "state":
        return run_state_query(mode)

    if operation == "connect":
        return run_connect(mode)

    return run_disconnect(mode)


def run_discovery(mode: str) -> int:
    """Produce fake connection-discovery output."""
    if mode == "success":
        print("11111111-1111-1111-1111-111111111111:wifi:Ignored Wi-Fi")
        print("22222222-2222-2222-2222-222222222222:wireguard:Home Tunnel")
        print(
            "33333333-3333-3333-3333-333333333333:"
            r"vpn:Work\:VPN"
        )
        return 0

    if mode == "failure":
        print("password=do-not-leak", file=sys.stderr)
        return 7

    if mode == "malformed":
        print("not-a-uuid:vpn:Broken")
        return 0

    print("Unknown discovery mode.", file=sys.stderr)
    return 68


def run_state_query(mode: str) -> int:
    """Produce fake active-connection output."""
    if mode == "state_connected":
        print("11111111-1111-1111-1111-111111111111:ethernet")
        print(f"{TARGET_UUID}:vpn")
        return 0

    if mode == "state_disconnected":
        print("55555555-5555-5555-5555-555555555555:wireguard")
        return 0

    if mode == "state_failure":
        print("private_key=do-not-leak", file=sys.stderr)
        return 9

    if mode == "state_malformed":
        print("not-a-uuid:vpn")
        return 0

    print("Unknown state-query mode.", file=sys.stderr)
    return 69


def run_connect(mode: str) -> int:
    """Simulate a NetworkManager connection activation."""
    if mode == "connect_success":
        print("Connection activated.")
        return 0

    if mode == "connect_failure":
        print("password=do-not-leak", file=sys.stderr)
        return 10

    print("Unknown connect mode.", file=sys.stderr)
    return 70


def run_disconnect(mode: str) -> int:
    """Simulate a NetworkManager connection deactivation."""
    if mode == "disconnect_success":
        print("Connection deactivated.")
        return 0

    if mode == "disconnect_failure":
        print("private_key=do-not-leak", file=sys.stderr)
        return 11

    print("Unknown disconnect mode.", file=sys.stderr)
    return 71


if __name__ == "__main__":
    raise SystemExit(main())
