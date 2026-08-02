# Tunnel Toggle

Tunnel Toggle is a KDE Plasma system tray application for controlling a
user-selected NetworkManager VPN or WireGuard connection.

## Project status

Tunnel Toggle is currently in private, pre-alpha development.

It is not yet ready for installation or normal use.

## Target platform

- Linux
- KDE Plasma 6
- NetworkManager
- Python 3.11 or newer
- PySide6 and Qt 6

Support for GNOME, Windows, macOS, and other network-management systems is
outside the scope of version 0.1.0.

## Safety boundaries

Tunnel Toggle reports whether the selected NetworkManager connection is active
or inactive.

It does not currently:

- Provide a network kill switch
- Verify that an application is bound to a specific interface
- Guarantee that all traffic uses the selected tunnel
- Verify DNS routing
- Guarantee that traffic cannot leak during connection transitions

## Development

Run the current development entry point:

    python3 -m tunnel_toggle

Run the available project checks:

    ./scripts/check.sh

Installation instructions will be added when the installer is implemented.

## License

Tunnel Toggle is licensed under the MIT License.
