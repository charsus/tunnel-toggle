# Packaging

This directory contains source metadata used for Linux desktop integration.

## Application identity

The stable freedesktop and AppStream application ID is:

    io.github.charsus.TunnelToggle

The Python distribution and executable remain:

    tunnel-toggle

## Metadata files

- `io.github.charsus.TunnelToggle.desktop`
  - KDE application-menu launcher source
  - Uses the desktop theme's `network-vpn` icon

- `io.github.charsus.TunnelToggle.metainfo.xml`
  - AppStream software-center metadata
  - Documents the application's security boundaries

## User-local installation

From a source checkout, install or update Tunnel Toggle with:

    python -m tunnel_toggle.local_installer install

Remove the managed installation with:

    python -m tunnel_toggle.local_installer uninstall

The installer does not use `sudo`. It creates an isolated virtual environment
under the user's XDG data directory and installs managed files under:

    ${XDG_DATA_HOME:-$HOME/.local/share}/tunnel-toggle/
    $HOME/.local/bin/tunnel-toggle
    ${XDG_DATA_HOME:-$HOME/.local/share}/applications/
    ${XDG_DATA_HOME:-$HOME/.local/share}/metainfo/

The installed desktop entry uses the managed launcher's absolute path and does
not depend on the graphical session's `PATH`.

An ownership manifest records the installed launcher and metadata hashes.
Updates and removal are refused when those files are missing, unrecognized, or
modified after installation.
