# Security Policy

## Project maturity

Tunnel Toggle is currently in pre-alpha development and has not received a
security audit.

It should not be treated as a kill switch or as proof that application traffic
is confined to a VPN or WireGuard interface.

## Safety boundaries

Tunnel Toggle is intended to inspect and control a selected NetworkManager
connection.

Unless a future feature explicitly verifies additional properties, the
application does not guarantee:

- Application-to-interface binding
- Complete traffic routing through the selected tunnel
- DNS protection
- Leak prevention
- Firewall enforcement
- Protection during tunnel connection transitions

## Sensitive information

Do not include any of the following in bug reports or diagnostic submissions:

- VPN usernames or passwords
- WireGuard private keys
- Complete NetworkManager connection profiles
- Authentication tokens
- Public IP addresses
- Private keys or certificates
- Unredacted logs from unrelated applications

Tunnel Toggle diagnostics must be designed to exclude this information.

## Reporting vulnerabilities

A private vulnerability-reporting method will be documented before the first
public alpha release.

Until then, the project remains local and unpublished.
