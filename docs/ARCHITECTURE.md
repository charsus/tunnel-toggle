# Tunnel Toggle Architecture

## Status

This document records the approved architecture for Tunnel Toggle version
0.1.0-alpha.

## Application identity

- Application name: Tunnel Toggle
- Repository name: tunnel-toggle
- Python distribution: tunnel-toggle
- Executable command: tunnel-toggle
- Python import package: tunnel_toggle

## Supported environment

Tunnel Toggle targets:

- Linux
- KDE Plasma 6
- NetworkManager
- Python 3.11 or newer
- PySide6 and Qt 6
- Wayland and X11 sessions

Other operating systems, desktop environments, and network-management systems
are outside the initial project scope.

## Architectural principles

- Use an event-driven Qt application architecture.
- Keep user-interface code separate from network-control code.
- Access NetworkManager through an abstract backend.
- Use asynchronous processes and network requests.
- Never require root privileges or perform privilege escalation.
- Store the selected NetworkManager connection by UUID.
- Store application settings through Qt QSettings.
- Resolve filesystem locations through XDG-aware APIs.
- Avoid hard-coded user paths and machine-specific values.
- Treat logs and diagnostics as potentially sensitive.
- Keep the default Git branch in a working state.

## Initial modules

- `main.py`: Minimal process entry point
- `application.py`: Application lifecycle and dependency construction
- `controller.py`: Coordination and application state
- `models.py`: Typed domain models and enumerations
- `tray.py`: System tray icon, menu, and notifications
- `settings.py`: Typed QSettings access and migrations
- `network_manager.py`: NetworkManager discovery, state, and control
- `network_monitor.py`: Event-driven NetworkManager monitoring
- `process_monitor.py`: Protected-application monitoring
- `public_ip.py`: Optional asynchronous public-IP checking
- `log_config.py`: Rotating and sanitized logging
- `diagnostics.py`: Sanitized diagnostic reporting
- `icons.py`: Theme icon lookup and bundled fallbacks

Modules will be added only when their implementation milestone begins. Empty
placeholder modules should be avoided.

## System tray shell

The system tray shell owns the persistent `QSystemTrayIcon`, its context menu,
and presentation-only actions.

The initial shell exposes read-only startup status and an explicit quit action.
It does not call NetworkManager directly. Controller integration will update
the tray through immutable application-state changes.

The tray menu is retained by the shell because the tray icon does not own its
context menu.

## Qt application lifecycle

Application metadata is configured centrally before services or user
interface components are created.

A per-user `QLockFile` in Qt's runtime directory prevents multiple Tunnel
Toggle processes from running simultaneously. Lock acquisition uses a short
bounded timeout and reports normalized failure reasons.

The lock is held for the complete Qt application lifetime and released during
orderly shutdown.

## Application controller

The application controller owns the aggregate immutable application state.

It translates user requests into backend operations, represents transitional
states immediately, and performs a canonical NetworkManager state query after
successful connect or disconnect commands.

NetworkManager monitor output is treated only as an activity notification.
The controller responds by requesting canonical state for the selected UUID.

The tray and dialogs must not call NetworkManager services directly.

## NetworkManager strategy

Version 0.1.0 will use `nmcli` through an abstract backend.

NetworkManager monitor output will be treated only as a signal that something
changed. Canonical connection state will be obtained through a separate,
machine-readable state query.

All external commands will be asynchronous and will pass arguments without
using a shell.

## State model

Tunnel state is not represented by one Boolean value.

Initial tunnel states:

- Unconfigured
- Unknown
- Disconnected
- Connecting
- Connected
- Disconnecting
- Error

Protected-application state, public-IP state, and tray presentation state will
be modeled separately.

## Privacy defaults

- No telemetry
- No analytics
- No automatic crash reporting
- Public-IP checking disabled by default
- No public IP addresses in logs
- No complete connection UUIDs in diagnostics
- No NetworkManager profiles in logs
- No protected-application command lines in logs

## Git policy

Git is used locally from the beginning of development.

No GitHub remote will be created before `v0.1.0-alpha`. Before publication,
the local history will be reviewed and curated. The public repository will
begin with meaningful, working commits rather than raw experimentation.
