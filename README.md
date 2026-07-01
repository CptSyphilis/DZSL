# DZSL — DayZ Server Launcher for Linux

DZSL is a native GTK4 and Libadwaita server launcher for DayZ on Linux. It provides server browsing, favorites, recent servers, Steam Workshop mod management, and direct server connections without requiring the Windows DZSA Launcher.

DZSL itself is a native Linux application. DayZ still runs through Steam Play/Proton.

Website: [dayzlinux.com](https://dayzlinux.com/)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)](#requirements)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux-green)](#requirements)
[![Donate with PayPal](https://img.shields.io/badge/Donate-PayPal-00457C?logo=paypal&logoColor=white)](https://www.paypal.com/donate/?hosted_button_id=R8HE5J4J4FGZY)

## Features

- Browse and filter public DayZ servers by map, players, ping, perspective, and mod status
- Keep favorite and recently played servers
- Detect required Workshop mods before connecting
- Confirm, subscribe to, and download missing mods through Steam
- View installed mods and their current Workshop state
- Verify, repair, update, and unsubscribe from mods
- Connect with the required mods, server address, profile, password, and launch flags
- Continue browsing while Steam starts or Workshop downloads run

## Requirements

- Linux with a graphical desktop session
- Steam with DayZ installed and Steam Play enabled
- Python 3.10 or newer
- GTK4, Libadwaita, and PyGObject
- `gawk`, `curl`, and `jq` for the standalone shell launcher

The installer supports Ubuntu, Debian, Pop!_OS, Linux Mint, Fedora, Arch, Manjaro, EndeavourOS, and openSUSE-based systems. Other distributions can be configured manually.

## Install

```bash
git clone https://github.com/CptSyphilis/DZSL.git
cd DZSL
bash bin/install.sh
```

The installer:

- Installs required system packages when supported
- Detects the Steam library containing DayZ
- Copies DZSL to `~/DZSL` by default
- Creates a desktop application entry
- Registers `dzsl://` links
- Preserves existing user configuration

To update an installed copy, pull the latest changes and run the installer again:

```bash
git pull
bash bin/install.sh
```

## Run from source

From the repository root:

```bash
./bin/dzsl.sh
```

This uses the system Python installation because GTK and Libadwaita bindings are normally provided by the distribution.

## First DayZ launch

Steam may ask which DayZ launch option to use. Select **Run DayZ Client**, enable **Always use this option**, and continue.

Do not select **Play DayZ** or **Run DayZ Launcher**. Those options open Bohemia's launcher instead of starting the client with DZSL's server and mod arguments.

The selection can be changed later from DayZ's Steam Library page.

## Connecting to a server

1. Open **Servers**, **Favorites**, or **Recent**.
2. Select the desired server and choose **Connect**.
3. Review the required mods if DZSL finds missing Workshop content.
4. Confirm the download and wait for Steam to finish.
5. DZSL creates DayZ-relative mod links and launches the remembered DayZ Client option.

Large Workshop mods can take a long time. DZSL waits for Steam to report them installed and current; it does not fail solely because an hour has elapsed. Use the visible Stop action if you want to cancel the wait.

## Workshop mod handling

Steam remains the source of truth for subscriptions, downloads, updates, and installed state. DZSL coordinates the requested work and reads Steam's Workshop records instead of maintaining a separate download cache.

Workshop content is normally stored under:

```text
<Steam library>/steamapps/workshop/content/221100/<Workshop ID>/
```

DZSL considers a mod usable when its Workshop directory contains non-empty `.pbo` content and Steam reports the item installed and current. Optional files such as `meta.cpp` and `mod.cpp` are not required for every mod.

Unsubscribing through DZSL asks Steam to unsubscribe first. Local content is removed only after Steam accepts the request.

## Configuration

Configuration is stored in:

```text
~/.config/dzsl/config.json
```

The Settings view provides controls for:

- Steam library location
- Optional custom Workshop location
- DayZ profile name
- Additional Workshop mods
- Additional game arguments
- Windowed mode, splash screen, pause, benchmark, script debugging, and BattlEye options

Logs are stored under `~/.config/dzsl/`, including `connect.log` for connection activity.

## Flatpak

A development manifest is provided at:

```text
packaging/flatpak/com.dayzlinux.dzsl.yml
```

Build and install it from the repository root with Flatpak Builder and the GNOME 50 runtime/SDK available:

```bash
flatpak-builder --user --install --force-clean build-dir \
  packaging/flatpak/com.dayzlinux.dzsl.yml
```

The Flatpak build needs filesystem access to the Steam library. The included manifest covers common native and Flatpak Steam locations plus libraries mounted under `/mnt`, `/media`, and `/run/media`.

## Troubleshooting

### Steam opens the DayZ launcher

Change Steam's remembered launch option to **Run DayZ Client**, then connect again through DZSL.

### Mods remain pending

Open Steam's Downloads view and check whether Steam is downloading, paused, waiting for confirmation, or reporting a disk error. DZSL does not replace Steam's download service.

### A mod is reported missing

Confirm the Steam library path in Settings. The selected library must contain both DayZ and its `steamapps/workshop` data, unless a custom Workshop location is configured.

### The interface does not reflect a recent code change

Quit DZSL completely and start it again from the intended checkout. A running GTK process continues using the code loaded when it started.

## Project layout

```text
dzsl/         application package
  assets/     packaged images and icons
  core/       configuration, constants, logging, and URI parsing
  services/   server queries, connection flow, and game launching
  steam/      Steam API, Workshop metadata, and installed-state handling
  ui/         GTK views, dialogs, and widgets
bin/          install, uninstall, and launch scripts
packaging/    Flatpak metadata and manifest
tests/        focused regression tests
```

## License

DZSL is released under the [MIT License](LICENSE).
