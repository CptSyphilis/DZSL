# WORK ORDER → codex

**Branch:** do this on `codex/work`.
**Priority:** high — breaks every multi-mod download.
**Author:** claude (diagnosed, handing implementation to codex)
**Date:** 2026-06-30

---

## Symptom

Joining a server with several mods to download: Steam shows **"Downloads Paused — 1 Item Queued"**, 0 bps, stuck at 0%, while DZSL sits in its download wait ("Waiting for <mod> download…", e.g. `0 B / 64.8 MB`). DayZ is NOT running. The download never progresses; DZSL eventually times out / reports incomplete.

Evidence screenshot: `/home/cptsyphilis/Pictures/Screenshots/Screenshot from 2026-06-30 00-51-11.png`

User's note (`/mnt/Storage1tb/coding/dzslnotes`, item 2): "when downloading several mods, steam pauses the download randomly… i think its because dayz is trying to start or the launch command is given prematurely."

## Root cause (confirmed)

The native Steam-API helper masquerades as DayZ, and Steam pauses content downloads while a game is "running."

- `dzsl/steam/api.py` (~lines 38-39) sets `os.environ["SteamAppId"] = "221100"` and `os.environ["SteamGameId"] = "221100"`, then calls `SteamAPI_InitFlat`. Initializing the Steam API with a game's AppID makes Steam treat **AppID 221100 (DayZ) as running.**
- `dzsl/ui/subscribe.py::wait_for_mod_installed` (~line 98) calls `_wait_with_native_monitor` FIRST (~lines 101-103), which spawns `python3 -m dzsl.steam.api monitor <mid>` and keeps it alive for the **entire** download.
- So for the whole download, Steam thinks DayZ is running → **pauses the very download being monitored.** Self-inflicted deadlock: DZSL waits on a download paused *because* DZSL is watching it.

This is NOT a premature-launch problem; the launch never fires here.

## Required fix

### 1. Primary — stop the masquerade during downloads (fixes the pause)

In `dzsl/ui/subscribe.py::wait_for_mod_installed`, do **not** use the native monitor to wait. Use the **ACF-manifest polling** path that already exists in the same method (the `for _ in range(steps)` loop using `mod_download_progress` + `mod_installed`). Reading the ACF from disk does not init the Steam API, so it does not pause downloads.

- Remove the `native_result = self._wait_with_native_monitor(...)` short-circuit (~lines 101-103) and the follow-on `log.warning(... "Steam API monitor unavailable" ...)`.
- Keep/promote the manifest-polling loop as the sole wait mechanism. It already updates the progress bar from `mod_download_progress` (Steam writes `BytesDownloaded`/`BytesToDownload` to the workshop ACF every few seconds — accurate enough).
- `_wait_with_native_monitor` (subscribe.py ~line 141) and the `monitor` subcommand in `dzsl/steam/api.py` then become **dead code** — remove them (user wants no dead code), but ONLY after grepping to confirm nothing else calls `dzsl.steam.api monitor` / `_wait_with_native_monitor`.

### 2. Evaluate the native SUBSCRIBE too

`subscribe_mod_steam` (subscribe.py ~line 64) also runs `python3 -m dzsl.steam.api subscribe <mid>` which inits the API as 221100, but only briefly (timeout 30, then `SteamAPI_Shutdown`). Test whether this brief masquerade also leaves Steam paused/stuck. If it does, switch subscribe to the URI form `steam://installworkshop/221100/<id>` (the fallback already at the end of that method, and what the Flatpak path already uses) — it does not init the API.

### 3. Secondary — `mod_installed` should not report a half-downloaded mod as installed

`dzsl/core/config.py::mod_installed` (~line 320) falls back to `validate_mod_folder`, which returns True as soon as `meta.cpp` + one non-empty `.pbo` exist — true mid-download for multi-PBO mods. Add a guard at the top of the `if manifests:` block:

```
downloaded, total = item_download_progress(manifests, mid)
if total and downloaded < total:
    return False
```

(`item_download_progress` is already imported in config.py.) This stops a still-downloading mod from being counted "installed" in the initial check (`connector.py::_thread`, ~line 413) and in `download.py::subscribe_and_wait_mods` (~line 55), which is the path that can also cause a premature launch when mods read installed.

## Files to touch
- `dzsl/ui/subscribe.py` — remove native-monitor use; make ACF polling primary; remove dead `_wait_with_native_monitor` if unused.
- `dzsl/steam/api.py` — remove the now-dead `monitor` subcommand if unused; consider whether `subscribe` should stop init-ing as 221100.
- `dzsl/core/config.py` — add the `item_download_progress` guard to `mod_installed`.

## Acceptance criteria (verify with a real multi-mod download)
1. Join a server needing several uninstalled mods. Steam's download bar **progresses continuously** — never "Downloads Paused" while DZSL waits.
2. DZSL's per-mod progress mirrors Steam's bytes; mods complete one after another.
3. DayZ launches **only after all mods are fully downloaded**, and the launch does not strand a still-downloading mod.
4. A mod that is half-downloaded is not treated as installed (no premature launch / skip).

## Constraints
- Branch `codex/work`. Do not touch `main` or `claude/codex-base`.
- **No `#` comments and no docstrings in code** — hard user rule.
- Keep the Flatpak path working (`is_flatpak()` already bypasses the native API and uses URIs).
- Don't regress the launch flow (`connector.py::_dl_and_finish` / `_thread`).
- After it works, add an entry to `updatelogs` (shared changelog, repo root, gitignored).

## Notes
- Don't run simultaneously with claude in this same working folder — one checkout at a time (see CLAUDE.md "Branch model").
- claude verified the diagnosis by reading the code; the actual fix + live multi-mod download verification is yours.

## Empirical confirmation (2026-06-30, from Andreas testing)
Pressing **Stop** in the DZSL download toast made **Steam resume downloading**.
Stop terminates the native monitor subprocess (`python3 -m dzsl.steam.api monitor`),
which was the process holding AppID 221100 open. With it dead, Steam no longer
sees DayZ as "running" and resumes. This is direct proof the monitor process is
the cause of the pause. Download also stopped after as few as 1 mod (count varies
with timing) — consistent with "monitor spawned -> Steam pauses," not "after N mods."
