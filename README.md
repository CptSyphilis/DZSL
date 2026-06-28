# DZSL — DayZ Server Launcher for Linux

Native GTK4 + Libadwaita launcher for DayZ on Linux. Browse servers, manage favorites, auto-handle Workshop mods, and launch directly — no Wine, no Windows app required.

Replaces the functionality of the popular Windows **DZSA Launcher** (DayZ Standalone Launcher).

Replaces the functionality of the Windows [DayZ Server App](https://dayzserverapp.com/).

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Linux-green)

## Features

- Browse and filter public DayZ servers (map, players, ping, mods, 1PP, BattlEye, etc.)
- Favorites + recent servers list
- Auto-subscribe and download missing Workshop mods via Steam when joining
- Built-in mod manager (installed mods, updates, unsubscribe)
- Right-click server actions (join, load mods only, copy IP, properties)
- Settings for Steam paths, profile name, and launch options
- Native Linux UI (GTK 4 + Libadwaita)

## Requirements

- Linux (Ubuntu, Debian, Fedora, Arch, Pop!_OS, etc.)
- Python 3.10+
- Steam + DayZ installed
- `gawk`, `curl`, `jq` for the optional standalone `bin/dayz-launcher.sh`

## Workshop downloads

DayZ Workshop mods are downloaded as directories containing `.pbo` payload files,
not as a single archive. By default they are stored under:

`<Steam library>/steamapps/workshop/content/221100/<Workshop ID>/`

DZSL uses Steam Workshop for subscriptions, downloads, updates, and progress.

## Quick Install

```bash
git clone https://github.com/CptSyphilis/DZSL.git
cd DZSL
bash bin/install.sh
