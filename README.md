# DZSL — DayZ Server List for Linux

A native Linux DayZ server browser and launcher. Browse servers, manage mods, and launch DayZ — all from one app.

## Features
- Browse all DayZ servers with filters (map, players, ping, mods, 1PP, BattlEye etc)
- Auto-detect and download missing mods via Steam
- Mod manager — check for updates, verify, unsubscribe
- Save favourite servers
- Automatic Steam startup check
- Works on any Linux distro

## Requirements
- Linux (Ubuntu, Debian, Fedora, Arch, Pop!_OS etc)
- Python 3.10+
- Steam with DayZ installed
- [dayz-linux-cli-launcher](https://github.com/bastimeyer/dayz-linux-cli-launcher)

## Install

```bash
git clone https://github.com/CptSyphilis/DZSL.git
cd DZSL
chmod +x install.sh
./install.sh
```

The install script will:
- Install all Python/GTK dependencies for your distro
- Auto-detect your Steam library and DayZ installation
- Install the CLI launcher if missing
- Create a desktop shortcut

## Manual Run

```bash
python3 main.py
```

## Project Structure

```
main.py          — App entry point
config.py        — Config and file helpers
css.py           — All styling
connect.py       — Connection logic and mod handling
ui/
  servers.py     — Server browser with filters
  favorites.py   — Favorites and recent servers
  server_row.py  — Server row widget
  add_server.py  — Add server form
  mods.py        — Mod manager
  settings.py    — Settings page
install.sh       — Auto installer
```

## Settings

On first run, check Settings to verify:
- Steam Library Root path
- CLI Launcher path
- Your in-game name

## Credits

Built on top of [dayz-linux-cli-launcher](https://github.com/bastimeyer/dayz-linux-cli-launcher) by bastimeyer.
Server data from [dayzsalauncher.com](https://dayzsalauncher.com).
