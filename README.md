# DZSL — DayZ Server List for Linux

**DZSA for Linux.** A native desktop app that does what [DayZ Server App](https://dayzserverapp.com/) does on Windows: browse servers, filter, favorite, handle mods, and launch straight into a server — without Wine or the Windows launcher.

## Features

- Browse DayZ servers with filters (map, players, ping, mods, 1PP, BattlEye, etc.)
- Favorites and recent servers
- Auto-subscribe and download missing workshop mods via Steam when joining
- Mod manager — installed mods, updates, unsubscribe, tools
- Right-click server actions (join, load mods, copy IP, properties)
- Settings for Steam path, launcher, in-game name, launch options
- Native GTK 4 + Libadwaita UI

## Requirements

- Linux (Ubuntu, Debian, Fedora, Arch, Pop!_OS, etc.)
- Python 3.10+
- Steam with DayZ installed
- `gawk`, `curl`, `jq` (installed automatically by the installer on supported distros)

## Install

```bash
git clone https://github.com/CptSyphilis/DZSL.git
cd DZSL
bash bin/install.sh
```

The installer will:

- Install Python/GTK dependencies for your distro (if missing)
- Detect your Steam library and DayZ installation
- Copy the app (including bundled `bin/dayz-launcher.sh`) to `~/DZSL`
- Write config to `~/.config/dzsl/` with paths for Steam and the launcher
- Create a desktop menu entry

Your clone folder is left untouched.

## Run

After install:

```bash
~/DZSL/bin/dzsl.sh
```

Or launch **DZSL** from your application menu.

To run from the clone without installing:

```bash
bash bin/dzsl.sh
```

## Uninstall

```bash
bash ~/DZSL/bin/uninstall.sh
```

Removes `~/DZSL`, `~/.config/dzsl`, and the menu entry. Does not delete your clone/source folder.

## Settings

On first run, check Settings:

- **Steam Library Root** — where DayZ is installed
- **CLI Launcher Path** — bundled `bin/dayz-launcher.sh`
- **In-game Name** — required by some servers
- **Launch options** — nosplash, window mode, close on launch, etc.

## How it works

| Part | Source |
|------|--------|
| Server list API | [dayzsalauncher.com](https://dayzsalauncher.com) |
| DayZ launch + mod setup | Bundled `bin/dayz-launcher.sh` (installed with DZSL) |
| UI | Python 3 + GTK 4 + Libadwaita |

## Credits

- [DayZ Server App (DZSA)](https://dayzserverapp.com/) — the app this replaces on Linux
- Server data from [dayzsalauncher.com](https://dayzsalauncher.com)