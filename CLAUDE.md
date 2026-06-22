# CLAUDE.md — DZSL Project Context

## What is DZSL?

DZSL is a native Linux replacement for DZSA Launcher — the popular Windows-only DayZ community server browser and mod manager. DZSA Launcher (by maca134) was last updated June 1, 2024 and is now abandoned. DZSL replicates its full feature set as a GTK4 + Libadwaita desktop app written in Python, so Linux DayZ players don't need Wine or Windows.

**Repo:** https://github.com/CptSyphilis/DZSL  
**Local path:** `/mnt/Storage1tb/coding/DZSL`  
**Current version:** 0.0.5.5  
**Entry point:** `bin/dzsl.sh` → `main.py`

## Architecture

- `main.py` — `Adw.Application` entry point, Steam detection/auto-launch, tab routing, favorites toggle, global connect callback
- `config.py` — reads/writes `~/.config/dzsl/config.json`, Steam path detection, `is_steam_running()`
- `connect.py` — `Connector` class: mod diffing, Steam Workshop subscription via `steam://` URIs, DayZ launch orchestration via `bin/dayz-launcher.sh`. Also handles hiding DZSL window when DayZ launches and re-showing it when DayZ exits.
- `css.py` — all GTK CSS loaded at startup
- `ui/servers.py` — `ServersView`: fetches server list from `dayzsalauncher.com/api/v1/launcher/servers/dayz`, filtering, sorting, ping batching
- `ui/server_row.py` — `ServerRow` widget: individual server row with accordion expand, star/fav button, info button, connect button
- `ui/favorites.py` — `ListView`: reused for both Favorites and Recent tabs
- `ui/server_properties.py` — modal dialog showing full server details (mods, security, tags)
- `ui/mods.py` — installed mod manager (list, verify, unsubscribe)
- `ui/settings.py` — settings UI (Steam path, launch options, profile name, etc.)
- `ui/ping.py` — `ping_servers()`: thread pool pinging visible servers via system `ping` command (ICMP)
- `ui/helpers.py` — shared utilities: `recent_map()`, `server_key()`, `format_played()`, `clear_box()`, etc.
- `ui/add_server.py` — manual server add by IP:port
- `ui/progress.py` — progress dialog shown during mod downloads
- `bin/dayz-launcher.sh` — builds actual DayZ launch command (`-connect=`, `-mod=`, `-nolauncher`, `-name=`, BattlEye flags) and execs via Steam
- `bin/install.sh` — one-shot installer: detects distro, installs GTK4/Python deps, copies to `~/DZSL`, registers `.desktop` entry

## Key Data Files (runtime, not in repo)

- `~/.config/dzsl/config.json` — user settings
- `~/.config/dzsl/favorites.json` — favorited servers
- `~/.config/dzsl/recent.json` — recently joined servers

## Bugs Fixed (session Jun 22 2026)

1. **`IndentationError` in `ui/servers.py` line 452** — `_update_map_filter` was accidentally nested inside `_save_and_filter()` with broken indentation and a duplicated code block. Fixed by un-nesting as a proper class method.

2. **`AttributeError: 'ServersView' object has no attribute '_update_version_filter'`** — method existed in early commits, was deleted in refactor `fe452ae` but call site (`GLib.idle_add(self._update_version_filter)`) was re-added in `f296029` without restoring the method. This caused every server fetch to silently fail ("Failed to load servers" in status bar). Restored the method.

3. **Per-row `recent_map()` disk reads** — `ServerRow.__init__` had a fallback `played_lookup.get(...) or recent_map().get(...)` that re-read and re-parsed `recent.json` from disk on every single row construction. With up to 500 rows rebuilt on every filter/sort/keystroke, this caused serious UI lag. Fixed: read `recent_map()` once per list build in the parent view and pass as `played_lookup`.

4. **Per-keystroke ping spam** — search and IP filter boxes triggered `_save_and_filter()` on every keystroke with no debounce, spawning up to 80 concurrent `ping` subprocesses per keypress. Fixed with 300ms debounce via `GLib.timeout_add` (matching the existing map filter debounce pattern).

5. **`gtk_scrolled_window_set_max_content_height` GTK-CRITICAL** — in `ui/server_properties.py`, `min_content_height = min(len(mods), 8) * 28` could reach 224px while `max_content_height` was hardcoded to 220px. GTK requires max ≥ min. Triggered on any server with 8+ mods. Fixed by clamping `min_h = min(calculated, max_h)`.

6. **steamcmd anonymous mod downloads always failing** — `_subscribe_and_wait_mods()` used `+login anonymous` hardcoded, which Valve blocks for Workshop items on paid games. The working fallback (Steam URI subscription via already-running Steam client) was bypassed when steamcmd existed. Fixed by removing the broken steamcmd path entirely — mod subscriptions now always go through `steam://installworkshop/` URIs.

7. **`connect.py` `_close_app()` fully quitting instead of hiding** — when "close on launch" was enabled, DZSL destroyed its window and exited. Changed to hide the window and spawn a background watcher thread that polls `pgrep -f DayZ_x64`, waits for DayZ to start (up to 3 min timeout), then waits for it to exit and calls `win.set_visible(True)` + `win.present()` to bring DZSL back.

## Features Added (session Jun 22 2026)

- **Accordion row expand** — only one server row can be expanded at a time. Shared `_expand_tracker = [None]` list passed to each `ServerRow`; expanding a row calls `_collapse()` on the previously expanded one.
- **Info button visual state** — the `i` button on each row now uses `btn-info-active` CSS class (white border/text) when the server has actual custom info (`description`/`info`/`notes` field non-empty), vs dim `btn-ghost` when it doesn't. Mirrors DZSA's white info icon convention.
- **DZSL reopens after DayZ exits** — see bug fix #7 above.

## Known Pending Items

- **Ping improvement plan** — see `ping-improvement-plan.md` in the repo root (if present). Summary:
  - Phase 1: average 2–3 pings instead of 1; distinguish ICMP-blocked servers from dead ones in the UI
  - Phase 2: switch to A2S_INFO UDP queries (game protocol) for more accurate, firewall-resistant latency
- **Confirmation dialogs** — "Unsubscribe all mods", per-mod unsubscribe, and mod update (which deletes local folder before re-downloading) have no confirmation. Easy to add with `Adw.MessageDialog`.
- **Settings auto-save** — settings changes are held in memory until you explicitly click Save. Silently lost if you navigate away.
- **Status bar** — sole feedback channel for errors, progress, and success. Easy to miss.

## Important Notes for Claude Code

- **Do not use steamcmd for Workshop downloads** — anonymous steamcmd cannot download Workshop items for paid games. Always use `steam://installworkshop/` URIs via the running Steam client.
- **All background threads must be `daemon=True`** — so they don't block process exit.
- **GTK/GLib UI updates from background threads must use `GLib.idle_add()`** — never touch GTK widgets from a non-main thread directly.
- **`_update_version_filter` and `_update_map_filter`** are called from both the main thread and via `GLib.idle_add()` from the fetch thread — they must be safe to call from either context (they are, as long as they only touch GTK via the GLib main loop).
- The app **requires Steam to be running** before it allows any action. `config.py`'s `is_steam_running()` checks PID files, `pgrep`, and Flatpak Steam.
- DayZ Workshop mods are identified by numeric Steam Workshop IDs. The game AppID is `221100`.
- Server list comes from `https://dayzsalauncher.com/api/v1/launcher/servers/dayz` — a community API, not official Bohemia/Valve.

## Running the App

```bash
/mnt/Storage1tb/coding/DZSL/bin/dzsl.sh
```

Requires: Python 3.10+, GTK4, libadwaita, `python3-gi`, `python3-requests`. Install via `bin/install.sh` on first run.
