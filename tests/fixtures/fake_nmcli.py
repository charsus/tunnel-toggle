#!/usr/bin/env python3
"""Deterministic fake nmcli used by integration tests."""

from __future__ import annotations

import os
import sys
import time

EXPECTED_ARGUMENTS = [
    "--terse",
    "--escape",
    "yes",
    "--fields",
    "UUID,TYPE,NAME",
    "connection",
    "show",
]


def main() -> int:
    """Return deterministic output for the requested test mode."""
    if sys.argv[1:] != EXPECTED_ARGUMENTS:
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

    if mode == "success":
        print("11111111-1111-1111-1111-111111111111:wifi:Ignored Wi-Fi")
        print("22222222-2222-2222-2222-222222222222:wireguard:Home Tunnel")
        print(
            "33333333-3333-3333-3333-333333333333:"
            r"vpn:Work\:VPN"
        )
        return 0

    if mode == "failure":
        print(
            "password=do-not-leak",
            file=sys.stderr,
        )
        return 7

    if mode == "malformed":
        print("not-a-uuid:vpn:Broken")
        return 0

    if mode == "timeout":
        time.sleep(2)
        return 0

    print("Unknown fake mode.", file=sys.stderr)
    return 68


if __name__ == "__main__":
    raise SystemExit(main())
