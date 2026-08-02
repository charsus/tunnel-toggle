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

## Freedesktop application metadata

Tunnel Toggle uses `io.github.charsus.TunnelToggle` as its stable desktop and
AppStream application identity.

The desktop launcher starts the installed `tunnel-toggle` entry point, uses the
desktop theme's `network-vpn` icon, and is scoped to KDE sessions.

AppStream metadata uses the same application identity and explicitly describes
the boundary between NetworkManager profile control and stronger protections
such as kill switches, application binding, or leak prevention.

Desktop metadata is maintained as packaging source data and is installed by a
separate explicit installer rather than setuptools `data-files`.

## Runtime setup integration

The runtime owns one dedicated setup discovery backend, setup controller, and
reusable setup dialog.

The tray presenter exposes Configure only while the main controller is
unconfigured. Repeated requests raise the same dialog rather than constructing
duplicates.

After settings are persisted successfully, the runtime applies the selected
UUID to the running application controller. The controller then performs its
normal canonical NetworkManager state query.

Setup discovery uses a backend separate from tunnel state and control
operations.

## Connection setup dialog

The connection setup dialog is a presentation-only Qt view over
`ConnectionSetupController`.

It displays loading, ready, empty, and error states; stores profile UUIDs as
combo-box item data; and forwards Refresh, selection, and Save requests to the
controller.

Profile names and connection types are display values only. Profile identity
always uses the NetworkManager UUID.

The dialog closes with an accepted result only after the controller emits a
successful settings-save result. It does not access NetworkManager or raw
`QSettings` keys.

## Connection setup controller

Connection setup is coordinated outside the future dialog.

The setup controller requests asynchronous NetworkManager discovery, exposes
an immutable loading/ready/error state, validates selections against the latest
discovery result, and retains selection by UUID rather than display name.

Saving completes setup through the typed settings repository. The selected
profile's UUID, last-known name, and type are replaced atomically while all
unrelated application settings are preserved.

The dialog must not access NetworkManager or raw `QSettings` keys directly.

## Runtime configuration

Normal startup loads the complete validated `AppSettings` value through the
typed settings repository.

The runtime factory uses the selected NetworkManager UUID only when setup is
marked complete. An incomplete setup remains unconfigured even if a partial or
stale UUID exists in storage.

Smoke-test startup does not read persistent application settings.

## Runtime composition

The application runtime owns the production NetworkManager backend, monitor,
application controller, tray shell, and tray presenter as one Qt object graph.

Runtime construction does not start services. Startup first activates the
controller and monitor, then exposes the tray. Shutdown first hides the tray,
then stops the controller and monitor.

The runtime forwards the tray's quit request without giving presentation
components access to the `QApplication` object.

The executable entry point connects runtime cleanup to Qt's `aboutToQuit`
signal and also performs idempotent cleanup in its finalization path.

## Tray presenter

The tray presenter is the only component that connects the application
controller to the system tray shell.

It converts domain tunnel states into complete tray view states and routes the
currently valid Connect or Disconnect action to the controller. Transitional,
unknown, unconfigured, and error states expose no actionable toggle operation.

The tray shell remains unaware of NetworkManager and application-state rules.

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
