import subprocess, threading, os, re, time, shlex
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GLib, Adw, Gtk
from dzsl.core.config import (
    mod_installed, mod_subscribed, save_json, RECENT_FILE, load_json, load_cfg,
    FAVS_FILE,
)
from dzsl.core.logging import get_logger
from dzsl.paths import ENV_FILE
from dzsl.runtime import is_flatpak, open_external_uri
from dzsl.services.dayz import ModSetupError, build_launch_command, build_launch_uri, setup_mod_links
from dzsl.services.server_api import fetch_server
from dzsl.steam import gate as workshop_gate

from dzsl.ui.download import ModDownloadManager
from dzsl.ui.helpers import filter_server_mods, server_key
from dzsl.ui.progress import ModProgressDialog
from dzsl.ui.subscribe import SteamSubscriptionManager, launch_steam

log = get_logger("connect")

from dzsl.core.environment import load_environment

load_environment(ENV_FILE)

class Connector:
    def __init__(self, cfg, win, set_status, set_downloading=None):
        self.cfg             = cfg
        self.win             = win
        self.set_status      = set_status
        self.set_downloading = set_downloading or (lambda *_: None)
        self._busy = False
        self._download_scheduled = False
        self.subscriptions = SteamSubscriptionManager(
            lambda: self.cfg,
            self._refresh_cfg,
            self.set_status,
            self.is_steam_running,
            self._wait_for_steam_start,
            launch_steam,
        )
        self.downloads = ModDownloadManager(
            lambda: self.cfg,
            self._refresh_cfg,
            self.set_status,
            self.subscriptions,
        )

    def _refresh_cfg(self):
        self.cfg = load_cfg()

    def _needs_password(self, server):
        return bool(server.get("password") or server.get("hasPassword"))

    def connect(self, server):
        self._refresh_cfg()
        password = server.get("saved_password")
        if self._needs_password(server) and not password:
            GLib.idle_add(self._prompt_password, server, True)
            return
        self._start(server, launch=True, password=password)

    def load_mods(self, server):
        self._start(server, launch=False, password=None)

    def _prompt_password(self, server, launch):
        d = Adw.MessageDialog(transient_for=self.win)
        d.set_heading("Server Password")
        name = server.get("name", "This server")
        d.set_body(f"{name} requires a password to join.")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_placeholder_text("Enter server password")
        entry.set_activates_default(True)
        remember = Gtk.CheckButton(label="Remember for this server")
        box.append(entry)
        box.append(remember)
        d.set_extra_child(box)

        d.add_response("cancel", "Cancel")
        d.add_response("join", "Join" if launch else "Continue")
        d.set_response_appearance("join", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("join")
        d.set_close_response("cancel")

        def on_r(dialog, response):
            if response == "join":
                password = entry.get_text()
                if remember.get_active() and password:
                    self._save_password(server, password)
                self._start(server, launch=launch, password=password or None)
            dialog.destroy()

        d.connect("response", on_r)
        d.present()
        entry.grab_focus()

    def _save_password(self, server, password):
        server["saved_password"] = password
        ip = server.get("ip") or server.get("endpoint", {}).get("ip")
        port = server.get("port") or server.get("gamePort") or server.get("endpoint", {}).get("port")
        favs = load_json(FAVS_FILE)
        for f in favs:
            f_ip = f.get("ip") or f.get("endpoint", {}).get("ip")
            f_port = f.get("port") or f.get("gamePort") or f.get("gameport")
            if f_ip == ip and f_port == port:
                f["saved_password"] = password
        save_json(FAVS_FILE, favs)

    def _server_ip(self, server):
        return server.get("ip") or server.get("endpoint", {}).get("ip")

    def _game_port(self, server):
        ep = server.get("endpoint", {})
        return (
            server.get("gamePort")
            or server.get("port")
            or ep.get("port")
            or 2302
        )

    def _query_port(self, server):
        ep = server.get("endpoint", {})
        return (
            server.get("queryPort")
            or ep.get("port")
            or server.get("port")
            or 27016
        )

    def _mods_from_server(self, server):
        mods = []
        for m in filter_server_mods(server.get("mods") or []):
            mid = str(m.get("steamWorkshopId") or m.get("id") or "").strip()
            if mid.isdigit():
                mods.append(mid)
        return mods

    def _mod_names_from_server(self, server):
        names = {}
        for m in filter_server_mods(server.get("mods") or []):
            mid = str(m.get("steamWorkshopId") or m.get("id") or "").strip()
            if mid.isdigit():
                names[mid] = m.get("name") or mid
        return names

    def _start(self, server, launch=True, password=None):
        if self._busy:
            log.info("Ignoring connect/load-mods click — already busy")
            self.set_status("Download in progress — wait for it to finish before connecting.")
            return
        acquired, active = workshop_gate.try_begin(
            "Downloading server mods" if launch else "Loading server mods"
        )
        if not acquired:
            self.set_status(f"Wait for the current Workshop operation to finish: {active}")
            return
        self._busy = True
        self._workshop_gate_active = True
        self._download_scheduled = False
        ip = self._server_ip(server)
        port = self._game_port(server)
        name = server.get("name", f"{ip}:{port}")
        if launch:
            self._save_recent(server)
        verb = "Connecting to" if launch else "Loading mods for"
        log.info("%s %s (%s:%s)", verb, name, ip, port)
        self.set_status(f"{verb} {name}…")
        threading.Thread(
            target=self._thread_wrapper,
            args=(server, launch, password),
            daemon=True,
        ).start()

    def _thread_wrapper(self, server, launch, password):
        try:
            self._thread(server, launch, password)
        finally:
            if not self._download_scheduled:
                self._busy = False
                self._finish_workshop_operation()

    def _finish_workshop_operation(self):
        if getattr(self, "_workshop_gate_active", False):
            self._workshop_gate_active = False
            workshop_gate.finish()

    def is_steam_running(self):
        if is_flatpak():
            return True
        return subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0

    def is_dayz_running(self):
        if is_flatpak():
            return False
        return subprocess.run(["pgrep", "-f", "DayZ_x64"], capture_output=True).returncode == 0

    def kill_dayz(self):
        if is_flatpak():
            return
        subprocess.run(["pkill", "-f", "DayZ_x64"])
        time.sleep(2)

    def _server_addr(self, ip, port):
        return f"{ip}:{port}"

    def _get_server_info(self, ip, port):
        try:
            return fetch_server(ip, port)
        except (OSError, RuntimeError, ValueError):
            return {}

    def _get_server_mods(self, ip, query_port):
        info = self._get_server_info(ip, query_port)
        ids = []
        for mod in info.get("mods", []):
            mod_id = str(mod.get("steamWorkshopId") or mod.get("id") or "").strip()
            if mod_id.isdigit():
                ids.append(mod_id)
        return ids

    def _mod_names(self, ip, query_port):
        info = self._get_server_info(ip, query_port)
        names = {}
        for m in info.get("mods", []):
            mid = str(m.get("steamWorkshopId", m.get("id", "")))
            if mid.isdigit():
                names[mid] = m.get("name", mid)
        return names

    def _resolve_mods(self, server):
        server_mods = self._mods_from_server(server)
        if server_mods:
            return server_mods, self._mod_names_from_server(server)
        ip = self._server_ip(server)
        query_port = self._query_port(server)
        ids = self._get_server_mods(ip, query_port)
        if ids:
            return ids, self._mod_names(ip, query_port)
        return [], {}

    def _game_params(self, password=None):
        params = []
        if password:
            params.append(f"-password={password}")
        if self.cfg.get("no_splash"):
            params.append("-nosplash")
        if self.cfg.get("no_pause"):
            params.append("-noPause")
        if self.cfg.get("no_benchmark"):
            params.append("-noBenchmark")
        if self.cfg.get("window_mode"):
            params.append("-window")
        if self.cfg.get("script_debug"):
            params.append("-scriptDebug")
        if self.cfg.get("skip_battleye"):
            params.append("-skipBattleye")
        extra = self.cfg.get("extra_args", "").strip()
        if extra:
            params.extend(shlex.split(extra))
        return params

    def _effective_mod_ids(self, mod_ids=None):
        ids = []
        seen = set()
        for raw_id in mod_ids or []:
            mid = str(raw_id).strip()
            if mid.isdigit() and mid not in seen:
                seen.add(mid)
                ids.append(mid)
        for raw_id in (self.cfg.get("extra_mods") or "").split(";"):
            mid = raw_id.strip()
            if mid.isdigit() and mid not in seen:
                seen.add(mid)
                ids.append(mid)
        return ids

    def _launcher_cmd(self, server, mod_links=None, password=None):
        ip = self._server_ip(server)
        port = self._game_port(server)
        profile = (self.cfg.get("profile_name") or "").strip()
        return build_launch_command(
            self._server_addr(ip, port),
            mod_links or [],
            profile,
            self._game_params(password),
        )

    def _run_launcher(self, server, mod_ids=None, launch=True, password=None):
        try:
            ids = self._effective_mod_ids(mod_ids)
            mod_links = setup_mod_links(self.cfg, ids)
            if not launch:
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            if is_flatpak():
                ip = self._server_ip(server)
                port = self._game_port(server)
                profile = (self.cfg.get("profile_name") or "").strip()
                uri = build_launch_uri(
                    self._server_addr(ip, port),
                    mod_links,
                    profile,
                    self._game_params(password),
                )
                if open_external_uri(uri):
                    return subprocess.CompletedProcess(args=[uri], returncode=0, stdout="", stderr="")
                return subprocess.CompletedProcess(
                    args=[uri], returncode=1, stdout="", stderr="Could not open Steam launch link"
                )
            cmd = self._launcher_cmd(server, mod_links=mod_links, password=password)
        except (ModSetupError, OSError, ValueError) as exc:
            return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=str(exc))
        return subprocess.run(cmd, capture_output=True, text=True)

    def _launcher_error(self, result):
        text = ((result.stdout or "") + (result.stderr or "")).strip()
        for line in text.splitlines():
            if "[error]" in line:
                return line.split("[error]", 1)[-1].strip()
        if result.returncode:
            return text.splitlines()[-1] if text else f"Launcher exited with code {result.returncode}"
        return ""

    def _show_error(self, heading, body):
        def show():
            d = Adw.MessageDialog(transient_for=self.win)
            d.set_heading(heading)
            d.set_body(body)
            d.add_response("ok", "OK")
            d.set_default_response("ok")
            d.set_close_response("ok")
            d.connect("response", lambda dialog, _: dialog.destroy())
            d.present()
        GLib.idle_add(show)

    def _open_mod_progress(self, queue, sizes, server, mod_names, name, launch, password):
        """Create the mod progress UI and start the download worker (GTK main thread only)."""
        progress = ModProgressDialog(
            queue,
            mod_names or {},
            on_open_downloads=self._open_steam_downloads,
        )
        self.set_downloading(True, progress)
        try:
            subprocess.Popen(
                ["notify-send", "-a", "DZSL", "-u", "normal",
                 "Downloading mods…",
                 f"Downloading {len(queue)} mod(s). Don't launch DayZ until complete."],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass
        threading.Thread(
            target=self._dl_and_finish,
            args=(queue, sizes, server, mod_names, name, launch, password, progress),
            daemon=True,
        ).start()

    def _schedule_mod_download(self, queue, sizes, server, mod_names, name, launch, password):
        self._download_scheduled = True
        def run():
            self._open_mod_progress(queue, sizes, server, mod_names, name, launch, password)
            return False
        GLib.idle_add(run)

    def _missing_from_output(self, result):
        return re.findall(
            r"Subscribe the mod here: (https://\S+)",
            (result.stdout or "") + (result.stderr or ""),
        )

    def _wait_for_steam_start(self, iterations=90, step=2, ready_sleep=3):
        for i in range(iterations):
            time.sleep(step)
            if self.is_steam_running():
                time.sleep(ready_sleep)
                return True
            elapsed = (i + 1) * step
            if elapsed % 20 == 0:
                self.set_status(f"Waiting for Steam to start ({elapsed}s)…")
        return False

    def _ensure_steam_for_launch(self):
        if self.is_steam_running():
            return True
        self.set_status("Starting Steam…")
        launch_steam()
        if self._wait_for_steam_start(ready_sleep=3):
            self.set_status("Steam ready.")
            return True
        self.set_status("Steam did not start in time.")
        self._show_error(
            "Steam required to launch",
            "Could not start Steam automatically. Please start Steam and try again.",
        )
        return False

    def _thread(self, server, launch, password):
        name = server.get("name", "server")

        if launch and self.is_dayz_running():
            self.set_status("Restarting DayZ with correct mods…")
            self.kill_dayz()

        self.set_status("Resolving server mod list…")
        server_mods, mod_names = self._resolve_mods(server)

        if server_mods:
            missing = [
                m for m in server_mods
                if not mod_installed(self.cfg, m) or not mod_subscribed(self.cfg, m)
            ]
            if missing:
                self._refresh_cfg()
                queue, sizes = self._prepare_mod_queue(missing, mod_names)
                self._schedule_mod_download(queue, sizes, server, mod_names, name, launch, password)
                return

        result = self._run_launcher(server, mod_ids=server_mods, launch=False, password=password)
        missing_urls = self._missing_from_output(result)
        if missing_urls:
            ids = [u.split("=")[-1] for u in missing_urls]
            self._refresh_cfg()
            queue, sizes = self._prepare_mod_queue(ids, mod_names)
            self._schedule_mod_download(queue, sizes, server, mod_names, name, launch, password)
            return
        if result.returncode:
            err = self._launcher_error(result)
            log.error("Mod setup failed for %s: %s", name, err)
            self.set_status(f"Failed to set up mods — {err}")
            self._show_error("Could not set up mods", err or "The launcher script failed.")
            return

        if launch:
            if not self._ensure_steam_for_launch():
                return
            self.set_status(f"Launching DayZ — {name}…")
            launch_result = self._run_launcher(
                server, mod_ids=server_mods, launch=True, password=password,
            )
            if launch_result.returncode:
                err = self._launcher_error(launch_result)
                log.error("DayZ launch failed for %s: %s", name, err)
                self.set_status(f"Failed to launch DayZ — {err}")
                self._show_error("Could not launch DayZ", err or "The launcher script failed.")
            else:
                log.info("Launched DayZ — %s", name)
                self.set_status(f"Launched DayZ — {name}")
                GLib.idle_add(self._close_app)
        else:
            if server_mods and self.is_steam_running():
                self._sync_steam_subscriptions(server_mods, start_if_needed=False)
            self.set_status(f"Mods ready for {name}")

    def _show_dl_dialog(self, mod_ids, server, mod_names, name, launch, password):
        names = mod_names or {}
        lines = [f"• {names.get(m, m)}" for m in mod_ids]
        action = "download, set up mods, and connect" if launch else "download and set up mods"
        d = Adw.MessageDialog(transient_for=self.win)
        d.set_heading(f"{len(mod_ids)} mods required")
        d.set_body(
            "Missing:\n" + "\n".join(lines[:12])
            + ("\n…" if len(lines) > 12 else "")
            + f"\n\nDZSL will download and set up mods for {action} via the Steam client."
        )
        d.add_response("cancel", "Cancel")
        d.add_response("dl", "Download & Connect" if launch else "Download Mods")
        d.set_response_appearance("dl", Adw.ResponseAppearance.SUGGESTED)
        def on_r(_, r):
            if r != "dl":
                return

            def begin_download():
                self._refresh_cfg()
                queue, sizes = self._prepare_mod_queue(mod_ids, names)
                self._open_mod_progress(queue, sizes, server, mod_names, name, launch, password)
                return False

            GLib.idle_add(begin_download)

        d.connect("response", on_r)
        d.present()

    def _download_cancelled(self, progress):
        return self.downloads.download_cancelled(progress)

    def _count_installed_mods(self, mod_ids):
        return self.downloads.count_installed_mods(mod_ids)

    def _open_steam_downloads(self):
        self.subscriptions.open_steam_downloads()

    def _sync_steam_subscriptions(self, mod_ids, start_if_needed=True):
        self.subscriptions.sync_steam_subscriptions(mod_ids, start_if_needed)

    def _subscribe_and_wait_mods(self, mod_ids, mod_names=None, progress=None, sizes=None):
        return self.downloads.subscribe_and_wait_mods(mod_ids, mod_names, progress, sizes)

    def _prepare_mod_queue(self, mod_ids, mod_names=None):
        return self.downloads.prepare_mod_queue(mod_ids, mod_names)

    def _dl_and_finish(self, mod_ids, sizes, server, mod_names, name, launch, password, progress):
        self._refresh_cfg()
        names = mod_names or {}
        total = len(mod_ids)

        try:
            if progress:
                progress.set_download_progress(0, total)
            self.set_status(f"Downloading {total} mods (smallest first)…")

            ok, err = self._subscribe_and_wait_mods(
                mod_ids,
                names,
                progress,
                sizes,
            )
            self.set_downloading(False)

            if err == "cancelled" or self._download_cancelled(progress):
                log.info("Mod download for %s cancelled by user", name)
                self.set_status("Download cancelled.")
                return
            if not ok:
                log.error("Mod download failed for %s: %s", name, err)
                self.set_status("Mod download failed.")
                self._show_error("Mod download failed", err or "Could not download mods.")
                return

            done = self._count_installed_mods(mod_ids)
            if done < total:
                missing = [
                    names.get(str(m), str(m))
                    for m in mod_ids
                    if not mod_installed(self.cfg, m)
                ]
                self.set_status(f"Only {done}/{total} mods downloaded.")
                self._show_error(
                    "Downloads incomplete",
                    f"Missing {len(missing)} mod(s):\n"
                    + "\n".join(f"• {n}" for n in missing[:8])
                    + ("\n…" if len(missing) > 8 else "")
                    + "\n\nPress ▶ again to retry.",
                )
                return

            if progress:
                progress.set_setup_progress("Setting up mod symlinks…")
            self.set_status("Setting up mod symlinks…")
            time.sleep(2)
            if self._download_cancelled(progress):
                self.set_status("Download cancelled.")
                return

            result = self._run_launcher(server, mod_ids=mod_ids, launch=False, password=password)
            still_missing = self._missing_from_output(result)
            if still_missing:
                self.set_status("Some mods still missing — check Steam downloads.")
                return
            if result.returncode:
                err = self._launcher_error(result)
                self.set_status(f"Failed to set up mods — {err}")
                self._show_error("Could not set up mods", err or "The launcher script failed.")
                return

            if launch:
                if not self._ensure_steam_for_launch():
                    return
                self.set_status(f"Launching DayZ — {name}…")
                time.sleep(1)
                if self._download_cancelled(progress):
                    self.set_status("Download cancelled.")
                    return
                launch_result = self._run_launcher(
                    server, mod_ids=mod_ids, launch=True, password=password,
                )
                if launch_result.returncode:
                    err = self._launcher_error(launch_result)
                    log.error("DayZ launch failed for %s: %s", name, err)
                    self.set_status(f"Failed to launch DayZ — {err}")
                    self._show_error("Could not launch DayZ", err or "The launcher script failed.")
                else:
                    log.info("Launched DayZ — %s (after mod download)", name)
                    self.set_status(f"Launched DayZ — {name}")
                    GLib.idle_add(self._close_app)
            else:
                self.set_status(f"Mods loaded for {name}")
        finally:
            self._busy = False
            self._finish_workshop_operation()
            if progress:
                progress.close()

    def _save_recent(self, server):
        recent = load_json(RECENT_FILE)
        key = server_key(server)
        recent = [r for r in recent if server_key(r) != key]
        entry = dict(server)
        entry["joined_at"] = time.time()
        recent.insert(0, entry)
        save_json(RECENT_FILE, recent[:20])

    def _close_app(self):
        if is_flatpak():
            return
        if not self.cfg.get("close_on_launch", True):
            return
        if not self.win:
            return
        self.win.set_visible(False)
        threading.Thread(target=self._watch_dayz_and_restore, daemon=True).start()

    def _watch_dayz_and_restore(self):
        started = False
        for _ in range(90):
            if self.is_dayz_running():
                started = True
                break
            time.sleep(2)
        if started:
            while self.is_dayz_running():
                time.sleep(3)
        GLib.idle_add(self._restore_window)

    def _restore_window(self):
        if self.win:
            self.win.set_visible(True)
            self.win.present()
