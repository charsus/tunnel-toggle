# Tunnel Toggle

Tunnel Toggle is a KDE Plasma system tray application for controlling a
user-selected NetworkManager VPN or WireGuard connection.

## Project status

Tunnel Toggle is alpha software.

The core connection-selection, monitoring, connection-control, installation,
and desktop-integration workflows are implemented and tested. Expect rough
edges, incomplete usability features, and changes between alpha releases.

## Supported platform

Tunnel Toggle currently targets:

- Linux
- KDE Plasma 6
- NetworkManager
- Python 3.11 or newer
- PySide6 and Qt 6
- Wayland or X11 KDE sessions

Support for GNOME, Windows, macOS, and network-management systems other than
NetworkManager is outside the scope of version 0.1.0.

## Requirements

Before installation, the system must provide:

- Python 3.11 or newer
- Python virtual-environment support
- `pip`
- NetworkManager and `nmcli`
- An existing NetworkManager VPN or WireGuard connection profile

Tunnel Toggle controls existing NetworkManager profiles. It does not create or
import VPN or WireGuard configurations.

## Install from a source checkout

Clone or download the source, enter the project directory, and run:

    python3 -m tunnel_toggle.local_installer install

The installer:

- Does not use `sudo`
- Creates an isolated application virtual environment
- Installs a managed launcher under `$HOME/.local/bin`
- Installs KDE desktop and AppStream metadata under the user data directory
- Records managed file hashes for safe updates and removal

The default application launcher is:

    $HOME/.local/bin/tunnel-toggle

After installation, Tunnel Toggle should also appear in the KDE application
menu.

## Uninstall

From a Tunnel Toggle source checkout, run:

    python3 -m tunnel_toggle.local_installer uninstall

The uninstaller removes only the installation recorded in Tunnel Toggle's
ownership manifest. It refuses to remove managed files that were modified
after installation.

## Use

1. Start Tunnel Toggle from the KDE application menu or managed launcher.
2. Open the tray menu.
3. Choose the setup action.
4. Select an existing NetworkManager VPN or WireGuard profile.
5. Use the tray toggle action to request connection or disconnection.

The selected connection is stored by its NetworkManager UUID.

## Safety boundaries

Tunnel Toggle reports and controls the state of the selected NetworkManager
connection.

It does not:

- Provide a network kill switch
- Verify that an application is bound to a specific interface
- Guarantee that all traffic uses the selected tunnel
- Verify DNS routing
- Enforce firewall policy
- Guarantee that traffic cannot leak during connection transitions

An active status means NetworkManager reports the selected connection as
active. It is not proof of complete traffic isolation.

## Development

Create and activate a virtual environment, then install the development
dependencies:

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -e '.[dev]'

Run the complete project gate:

    ./scripts/check.sh

Run the development entry point:

    python -m tunnel_toggle

Run the noninteractive startup check:

    QT_QPA_PLATFORM=offscreen python -m tunnel_toggle --smoke-test

## Release version

The first public alpha uses:

- Python package version: `0.1.0a1`
- Git release tag: `v0.1.0-alpha`

## Security

Do not include credentials, private keys, complete NetworkManager profiles, or
other secrets in public bug reports.

See [SECURITY.md](SECURITY.md) for the vulnerability-reporting process and
security boundaries.

## License

Tunnel Toggle is licensed under the MIT License.
