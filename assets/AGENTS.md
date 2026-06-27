# Repository Guidelines

## Project Structure & Module Organization
DZSL is a Python 3.10+ GTK4/libadwaita desktop launcher for DayZ on Linux. The Git root contains the main application modules: `main.py`, `config.py`, `connect.py`, `css.py`, and `applog.py`. UI views and widgets live in `ui/`, installer and launcher scripts live in `bin/`, and static/generated images live in `assets/`. This `assets/` directory contains `icon.png`, `dzsl-bg.png`, `dzsl-bg.svg`, and `build_bg.py`, the script that regenerates the background artwork.

## Build, Test, and Development Commands
Run commands from the Git root unless noted.

- `python3 main.py`: launch the GTK application locally.
- `bash bin/install.sh`: install runtime dependencies and copy the app to the configured install directory.
- `bash bin/uninstall.sh`: remove the installed app files.
- `python3 assets/build_bg.py`: regenerate `assets/dzsl-bg.svg` and `assets/dzsl-bg.png`; requires `cairosvg`.

There is no formal build step for the Python app.

## Coding Style & Naming Conventions
Use straightforward Python with 4-space indentation. Keep module filenames lowercase with underscores when needed, matching existing files such as `server_row.py` and `add_server.py`. Prefer explicit helper functions for GTK UI behavior, and keep view-specific logic inside the relevant `ui/` module. Shell scripts should use `bash`, `set -euo pipefail` where practical, and clear status messages.

## Testing Guidelines
No automated test suite is currently present. Before submitting changes, run `python3 main.py` from a graphical Linux session and smoke-test affected flows, such as server browsing, favorites, settings, mod handling, or asset rendering. For installer changes, test `bash bin/install.sh` on a disposable environment or clearly state the distro used.

## Commit & Pull Request Guidelines
Recent history uses short, descriptive commit messages such as `cleanup` and `workshop auto subscribe`, with longer details when a change spans multiple features. Prefer concise imperative or descriptive subjects under 72 characters, and add a body for behavior changes, migrations, or user-visible fixes.

Pull requests should include a summary, test notes, linked issues when relevant, and screenshots or short recordings for UI changes. Mention any new runtime dependency, configuration key, or Steam/DayZ path assumption.

## Security & Configuration Tips
Do not commit `.env`, local config, logs, virtual environments, or generated cache files. Treat Steam paths, profile names, and launcher settings as local user configuration.
