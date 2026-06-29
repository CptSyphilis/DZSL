# DZSL — DayZ Server Launcher for Linux

Native GTK4 + Libadwaita launcher for DayZ on Linux. Browse servers, keep favorites, handle Workshop mods, and launch the game directly. No Wine, no Windows app.

Replaces the abandoned Windows-only [DZSA](https://dayzsalauncher.com/).

Website: [DZSA Linux version](https://www.dayzlinux.com/)

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Linux-green)

## Features

- Browse and filter public servers (map, players, ping, mods, 1PP, BattlEye)
- Favorites and recent servers
- Auto-subscribe and download missing Workshop mods through Steam when joining
- Mod manager: installed mods, updates, verify, repair, unsubscribe
- Right-click server actions (join, load mods, copy IP, properties)
- Settings for Steam paths, profile name, and launch options

## Requirements

- Linux (Ubuntu, Debian, Fedora, Arch, Pop!_OS, ...)
- Python 3.10+, GTK4, libadwaita
- Steam with DayZ installed
- `gawk`, `curl`, `jq` for the standalone `bin/dayz-launcher.sh`

## Install

```bash
git clone https://github.com/CptSyphilis/DZSL.git
cd DZSL
bash bin/install.sh
```

Run from a source checkout without installing:

```bash
bin/dzsl.sh
```

## Workshop mods

Mods download as directories of `.pbo` files, not archives, under:

`<Steam library>/steamapps/workshop/content/221100/<Workshop ID>/`

Subscriptions, downloads, updates, and progress go through Steam.

## Layout

```text
dzsl/         application package
  core/       config, constants, logging, URI parsing
  services/   launch, connection, server API
  steam/      native Steam API and Workshop state
  ui/         GTK views, widgets, styles
  assets/     packaged images
bin/          launch, install, uninstall scripts
packaging/    Flatpak manifest
```

Config lives in `~/.config/dzsl/`.

## License

MIT
