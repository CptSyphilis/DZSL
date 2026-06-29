# Security Policy

## Reporting a vulnerability

Do not disclose exploitable vulnerabilities, credentials, server passwords, or
sensitive logs in a public issue. Use GitHub private vulnerability reporting for
this repository.

Include the affected version, reproduction steps, impact, and any suggested
mitigation. Reports will be acknowledged as soon as practical. A supported
release is any release currently published on dayzlinux.com.

## Local data

DZSL stores configuration, favorites, recent servers, filters, and optionally a
saved server password under `$XDG_CONFIG_HOME/dzsl/` (normally
`~/.config/dzsl/`). These files are created with user-only permissions. DayZ
requires server passwords on its command line, so a password can be visible to
other processes running as the same local user while the game starts.
