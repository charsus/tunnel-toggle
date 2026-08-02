# Changelog

All notable changes to Tunnel Toggle will be documented in this file.

## [Unreleased]

### Added

- Initial local Git repository
- Foundational project directory structure
- Minimal Python package entry point
- Initial project quality-check script
- Architecture, security, and project documentation
- Typed domain models for application state
- Validated QSettings schema and typed settings repository
- Rotating, privacy-conscious application logging
- NetworkManager VPN and WireGuard profile parsing
- Asynchronous NetworkManager connection discovery
- Read-only NetworkManager active tunnel-state queries
- Asynchronous NetworkManager connect and disconnect commands
- Event-driven NetworkManager monitoring with automatic restart
- Application controller with canonical tunnel state coordination
- Qt application metadata and single-instance lifecycle support
- Minimal Qt system tray shell and non-blocking startup smoke mode
- Controller-aware tray presentation and tunnel toggle action
- Production runtime composition with orderly Qt shutdown
- Safe loading of the selected NetworkManager connection from typed settings
