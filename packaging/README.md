# Packaging

This directory contains source metadata used for Linux desktop integration.

## Application identity

The stable freedesktop and AppStream application ID is:

    io.github.charsus.TunnelToggle

The Python distribution and executable remain:

    tunnel-toggle

## Files

- `io.github.charsus.TunnelToggle.desktop`
  - KDE application-menu launcher
  - Launches the installed `tunnel-toggle` entry point
  - Uses the desktop theme's `network-vpn` icon

- `io.github.charsus.TunnelToggle.metainfo.xml`
  - AppStream software-center metadata
  - Uses the same stable application identity
  - Documents the application's security boundaries

## Intended installation locations

A user-local installer will later place the files under the XDG data
directory:

    ${XDG_DATA_HOME:-$HOME/.local/share}/applications/
    ${XDG_DATA_HOME:-$HOME/.local/share}/metainfo/

The installer must also ensure that the `tunnel-toggle` executable is
discoverable by the graphical desktop session before installing the launcher.

These source files are not installed automatically by setuptools. Installation
and removal will be implemented as an explicit, tested packaging workflow.
