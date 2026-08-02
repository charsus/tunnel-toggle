# Security Policy

## Project maturity

Tunnel Toggle is alpha software and has not received an independent security
audit.

It should not be treated as a kill switch or as proof that application traffic
is confined to a VPN or WireGuard interface.

## Supported versions

Security fixes are provided for the most recent published alpha release when
maintenance capacity permits.

Older development snapshots and superseded alpha releases may not receive
security updates.

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

An active state means NetworkManager reports the selected connection as active.
It does not establish that every application or packet is using that
connection.

## Reporting vulnerabilities

Prefer GitHub private vulnerability reporting through the repository's
**Security** page.

Do not publish vulnerability details in a public issue.

When private vulnerability reporting is unavailable, open a public issue that
contains no sensitive technical details and request a private reporting
channel. Wait for a maintainer response before sharing reproduction steps,
proof-of-concept material, logs, or other vulnerability details.

Include, when safe and relevant:

- The affected Tunnel Toggle version
- Operating-system and KDE Plasma versions
- NetworkManager version
- A concise description of the impact
- Reproduction steps with secrets removed
- Whether the issue is already being exploited

No response-time or remediation-time guarantee is currently offered.

## Sensitive information

Do not include any of the following in reports, logs, screenshots, or
diagnostic submissions:

- VPN usernames or passwords
- WireGuard private keys
- Complete NetworkManager connection profiles
- Authentication tokens
- Public IP addresses
- Private keys or certificates
- Unredacted logs from unrelated applications

Tunnel Toggle diagnostics are designed to avoid collecting this information,
but reporters must still inspect submitted material carefully.

## Disclosure

Please allow maintainers a reasonable opportunity to investigate and prepare a
fix before public disclosure. Coordinated disclosure timing will be discussed
through the private reporting channel.
