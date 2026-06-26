import subprocess, threading, os, re, time, shlex
import concurrent.futures
import requests
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GLib, Adw, Gtk
from config import (
    DAYZ_APPID, mod_installed, mod_subscribed, mod_subscribed_per_steam_log,
    is_steam_running, save_json, RECENT_FILE, load_json, load_cfg, FAVS_FILE,
    workshop_dir,
)

from ui.progress import ModProgressDialog
from ui.helpers import filter_server_mods, forward_steam_uri, notify_check_steam, server_key
from applog import get_logger

log = get_logger("connect")

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

def launch_steam():
    proc = subprocess.Popen(
        ["steam"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )

    def _log_stderr():
        for line in proc.stderr:
            line = line.strip()
            if line:
                log.warning("steam: %s", line)

    threading.Thread(target=_log_stderr, daemon=True).start()

class Connector:
    def __init__(self, cfg, win, set_status, set_downloading=None):
        self.cfg             = cfg
        self.win             = win
        self.set_status      = set_status
        self.set_downloading = set_downloading or (lambda *_: None)
        self._busy = False
        self._download_scheduled = False

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
            if mid:
                mods.append(mid)
        return mods

    def _mod_names_from_server(self, server):
        names = {}
        for m in filter_server_mods(server.get("mods") or []):
            mid = str(m.get("steamWorkshopId") or m.get("id") or "").strip()
            if mid:
                names[mid] = m.get("name") or mid
        return names

    def _start(self, server, launch=True, password=None):
        if self._busy:
            log.info("Ignoring connect/load-mods click — already busy")
            self.set_status("Download in progress — wait for it to finish before connecting.")
            return
        self._busy = True
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

    def is_steam_running(self):
        return subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0

    def is_dayz_running(self):
        return subprocess.run(["pgrep", "-f", "DayZ_x64"], capture_output=True).returncode == 0

    def kill_dayz(self):
        subprocess.run(["pkill", "-f", "DayZ_x64"])
        time.sleep(2)

    def _server_addr(self, ip, port):
        return f"{ip}:{port}"

    def _get_server_info(self, ip, port):
        try:
            return requests.get(
                f"https://dayzsalauncher.com/api/v1/query/{ip}/{port}",
                headers={"User-Agent": "DZSL/1.0"},
                timeout=10,
            ).json().get("result", {})
        except Exception:
            return {}

    def _get_server_mods(self, ip, query_port):
        info = self._get_server_info(ip, query_port)
        return [
            str(m.get("steamWorkshopId", m.get("id", "")))
            for m in info.get("mods", [])
            if m.get("steamWorkshopId") or m.get("id")
        ]

    def _mod_names(self, ip, query_port):
        info = self._get_server_info(ip, query_port)
        names = {}
        for m in info.get("mods", []):
            mid = str(m.get("steamWorkshopId", m.get("id", "")))
            if mid:
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

    def _launcher_cmd(self, server, mod_ids=None, launch=True, password=None):
        """Build argv for bin/dayz-launcher.sh (see --help in that script)."""
        ip = self._server_ip(server)
        port = self._game_port(server)
        query_port = self._query_port(server)
        lp = self.cfg.get("launcher_path") or ""
        sr = self.cfg.get("steam_root") or ""
        if not lp or not os.path.isfile(lp):
            raise FileNotFoundError(f"Launcher not found: {lp}")
        cmd = ["env", f"STEAM_ROOT={sr}", lp]
        if launch:
            cmd.append("--launch")
        cmd.extend(["-s", self._server_addr(ip, port)])
        if query_port and int(query_port) != int(port):
            cmd.extend(["-p", str(query_port)])
        profile = (self.cfg.get("profile_name") or "").strip()
        if profile:
            cmd.extend(["-n", profile])
        seen = set()
        for mid in mod_ids or []:
            mid = str(mid).strip()
            if mid and mid not in seen:
                seen.add(mid)
                cmd.append(mid)
        extra_mods = (self.cfg.get("extra_mods") or "").strip()
        if extra_mods:
            for mid in extra_mods.split(";"):
                mid = mid.strip()
                if mid and mid not in seen:
                    seen.add(mid)
                    cmd.append(mid)
        if launch:
            game_params = self._game_params(password)
            if game_params:
                cmd.append("--")
                cmd.extend(game_params)
        return cmd

    def _run_launcher(self, server, mod_ids=None, launch=True, password=None):
        try:
            cmd = self._launcher_cmd(server, mod_ids=mod_ids, launch=launch, password=password)
        except (OSError, FileNotFoundError) as exc:
            return subprocess.CompletedProcess(cmd=[], returncode=1, stdout="", stderr=str(exc))
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
            self.win,
            f"Downloading {len(queue)} mods",
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
            missing = [m for m in server_mods if not mod_installed(self.cfg, m)]
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
            if server_mods:
                self._sync_steam_subscriptions(server_mods)
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
        return progress and progress.is_cancelled()

    def _count_installed_mods(self, mod_ids):
        return sum(1 for m in mod_ids if mod_installed(self.cfg, m))

    def _open_steam_downloads(self):
        self._forward_steam_uri("steam://open/downloads")

    def _forward_steam_uri(self, uri):
        """Send a steam:// URI to the running Steam client (never xdg-open — that opens a browser)."""
        return forward_steam_uri(uri)

    def _mod_download_timeout(self, nbytes):
        nbytes = int(nbytes or 0)
        if nbytes >= 5 * 1024 ** 3:
            return 6 * 3600
        if nbytes >= 1024 ** 3:
            return 3 * 3600
        if nbytes >= 100 * 1024 ** 2:
            return 3600
        return 900

    def _depotdownloader_path(self):
        candidates = [
            os.path.expanduser("~/tools/depotdownloader/DepotDownloader"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "DepotDownloader"),
        ]
        for p in candidates:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        return None

    def _get_steam_username(self):
        vdf = os.path.expanduser("~/.local/share/Steam/config/loginusers.vdf")
        try:
            text = open(vdf, errors="ignore").read()
            for m in re.finditer(r'"(\d{17})"[^{]*\{([^}]*)\}', text, re.DOTALL):
                block = m.group(2)
                if '"MostRecent"\t\t"1"' in block or '"MostRecent"  "1"' in block:
                    nm = re.search(r'"AccountName"\s+"([^"]+)"', block)
                    if nm:
                        return nm.group(1)
        except OSError:
            pass
        return None

    def _download_mod_depotdownloader(self, mid, mod_name, dest_dir, progress=None, size_bytes=0):
        depot_bin = self._depotdownloader_path()
        username = self._get_steam_username()
        if not depot_bin or not username:
            return False, "DepotDownloader not available"

        os.makedirs(dest_dir, exist_ok=True)
        max_chunks = int(self.cfg.get("download_max_chunks", 8))
        cmd = [depot_bin, "-app", DAYZ_APPID, "-pubfile", mid,
               "-username", username, "-remember-password", "-dir", dest_dir,
               "-max-downloads", str(max(1, min(max_chunks, 8)))]
        speed_kbps = int(self.cfg.get("download_speed_kbps", 0) or 0)
        if speed_kbps > 0:
            import shutil as _shutil
            if _shutil.which("trickle"):
                cmd = ["trickle", "-d", str(speed_kbps)] + cmd
            else:
                log.warning("Speed limit set but trickle not found — downloading unlimited")
        log.info("DepotDownloader: %s (%s) -> %s", mod_name, mid, dest_dir)
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            prev_pct = 0.0
            last_lines = []
            speed_window = []  # list of (timestamp, bytes_done) for sliding window
            WINDOW_SECS = 4.0
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                log.debug("depot: %s", line)
                last_lines.append(line)
                if len(last_lines) > 8:
                    last_lines.pop(0)
                m = re.match(r'\s*(\d+\.\d+)%', line)
                if m:
                    pct = float(m.group(1))
                    now = time.time()
                    if progress:
                        GLib.idle_add(progress.set_mod_progress, mid, pct / 100.0)
                    if size_bytes:
                        bytes_done = pct / 100.0 * size_bytes
                        speed_window.append((now, bytes_done))
                        # drop samples older than WINDOW_SECS
                        cutoff = now - WINDOW_SECS
                        while len(speed_window) > 1 and speed_window[0][0] < cutoff:
                            speed_window.pop(0)
                        if len(speed_window) >= 2:
                            dt = speed_window[-1][0] - speed_window[0][0]
                            db = speed_window[-1][1] - speed_window[0][1]
                            if dt >= 0.5 and db >= 0:
                                bps = db / dt
                                GLib.idle_add(progress.set_speed, self._format_size(bps) + "/s")
                    prev_pct = pct
                if progress and progress.is_cancelled():
                    proc.terminate()
                    proc.wait()
                    self._cleanup_partial_mod(dest_dir, mid)
                    return False, "cancelled"
            proc.wait()
            if progress:
                GLib.idle_add(progress.set_speed, "—")
            if proc.returncode == 0:
                log.info("DepotDownloader done: %s (%s)", mod_name, mid)
                return True, ""
            self._cleanup_partial_mod(dest_dir, mid)
            tail = "\n".join(last_lines[-3:]) if last_lines else ""
            err_msg = f"DepotDownloader exited {proc.returncode}"
            if tail:
                err_msg += f":\n{tail}"
            log.error("DepotDownloader failed for %s: %s", mod_name, err_msg)
            return False, err_msg
        except Exception as exc:
            log.error("DepotDownloader error for %s: %s", mid, exc)
            self._cleanup_partial_mod(dest_dir, mid)
            return False, str(exc)

    def _cleanup_partial_mod(self, dest_dir, mid):
        import shutil as _shutil
        if os.path.isdir(dest_dir):
            log.warning("Cleaning up partial download for %s: %s", mid, dest_dir)
            try:
                _shutil.rmtree(dest_dir)
            except OSError as e:
                log.error("Failed to clean up %s: %s", dest_dir, e)

    def _subscribe_mod_steam(self, mod_id, mod_name):
        self._forward_steam_uri(f"steam://installworkshop/221100/{str(mod_id)}")


    def _open_workshop_page(self, mod_id, mod_name):
        mid = str(mod_id)
        log.warning("Auto-subscribe unresponsive for %s (%s) — opening Workshop page for manual subscribe", mod_name, mid)
        self.set_status(f"Opened Steam Workshop page for {mod_name} — click Subscribe there to continue.")
        self._forward_steam_uri(f"steam://url/CommunityFilePage/{mid}")

    def _sync_steam_subscriptions(self, mod_ids, start_if_needed=True):
        if not mod_ids:
            return
        if start_if_needed and not self.is_steam_running():
            self.set_status("Starting Steam to subscribe mods…")
            launch_steam()
            self._wait_for_steam_start(iterations=20, ready_sleep=2)
        if not self.is_steam_running():
            return
        notify_check_steam()
        for mid in mod_ids:
            mid = str(mid)
            self._subscribe_mod_steam(mid, mid)

    def _subscribe_and_wait_mods(self, mod_ids, mod_names, sizes=None, progress=None):
        self._refresh_cfg()
        names = mod_names or {}
        total = len(mod_ids)
        log.info("Need %d mod(s): %s", total, ", ".join(names.get(str(m), str(m)) for m in mod_ids))

        pending = []
        done = 0
        for mid in mod_ids:
            mid = str(mid)
            if mod_installed(self.cfg, mid):
                log.info("Already installed: %s", names.get(mid, mid))
                self._mark_mod_progress(progress, mid)
                done += 1
            else:
                pending.append(mid)
        if progress:
            progress.set_download_progress(done, total)
        if not pending:
            return True, ""
        if progress and progress.is_cancelled():
            return False, "cancelled"

        backend = self.cfg.get("download_backend", "auto")
        depot_bin = self._depotdownloader_path()
        username = self._get_steam_username()
        if backend == "depot":
            use_depot = True
        elif backend == "steam":
            use_depot = False
        else:  # auto
            use_depot = bool(depot_bin and username)
        if not use_depot:
            notify_check_steam()

        n_parallel = max(1, int(self.cfg.get("download_parallel", 3)))
        log.info("Downloading %d mod(s) with up to %d in parallel", len(pending), n_parallel)
        if progress:
            progress.set_action_prompt(f"Downloading {len(pending)} mod(s)…")

        done_lock = threading.Lock()
        errors = []

        def download_one(mid):
            if progress and progress.is_cancelled():
                return
            mod_name = names.get(mid, mid)
            log.info("Downloading: %s (%s)", mod_name, mid)
            self.set_status(f"Downloading {mod_name}…")

            if use_depot:
                dest = os.path.join(workshop_dir(self.cfg), mid)
                ok, err = self._download_mod_depotdownloader(
                    mid, mod_name, dest, progress, size_bytes=sizes.get(mid, 0) if sizes else 0
                )
            else:
                self._subscribe_mod_steam(mid, mod_name)
                ok = self._wait_for_mod_installed(mid, progress, mod_name)
                err = "" if ok else f"Timeout waiting for {mod_name}"

            if not ok:
                log.error("Failed %s: %s", mod_name, err)
                with done_lock:
                    errors.append(err)
                return
            self._mark_mod_progress(progress, mid)
            with done_lock:
                done_ref[0] += 1
                current_done = done_ref[0]
            if progress:
                progress.set_download_progress(current_done, total)
            log.info("Done: %s", mod_name)

        done_ref = [done]
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_parallel) as ex:
            futs = {ex.submit(download_one, mid): mid for mid in pending}
            for fut in concurrent.futures.as_completed(futs):
                try:
                    fut.result()
                except Exception as exc:
                    mid = futs[fut]
                    log.error("Unhandled error downloading %s: %s", mid, exc)
                    with done_lock:
                        errors.append(str(exc))

        if errors:
            return False, errors[0]
        return True, ""

    def _wait_for_mod_installed(self, mod_id, progress, mod_name, size_bytes=0):
        mid = str(mod_id)
        self.set_status(f"Waiting for {mod_name} download…")
        start = time.time()
        step = 2
        steps = 600 // step  # 10 minutes
        fallback_opened = False
        for i in range(steps):
            if progress and progress.is_cancelled():
                log.info("Wait for %s cancelled after %ds", mod_name, int(time.time() - start))
                return False
            self._refresh_cfg()
            if mod_installed(self.cfg, mid):
                log.info("%s installed after %ds", mod_name, int(time.time() - start))
                return True
            # workshop_log.txt reflects a subscribe instantly; appworkshop_*.acf
            # (mod_subscribed) lags behind it — check both so the fallback-page
            # and resend logic below don't act as if nothing happened yet.
            subscribed = mod_subscribed(self.cfg, mid) or mod_subscribed_per_steam_log(mid)
            if progress and progress.continue_requested():
                if subscribed:
                    log.info("User advanced past %s after %ds (subscription confirmed)", mod_name, int(time.time() - start))
                    progress.clear_continue()
                    return True
                log.warning("Next-mod click for %s ignored — not yet subscribed per Steam", mod_name)
                progress.clear_continue()
                progress.set_hint(f"Not subscribed yet in Steam — click Subscribe first for:\n{mod_name}")
            elapsed = i * step
            opened_fallback_now = False
            if not fallback_opened and elapsed >= 10 and not subscribed:
                # Steam gave no sign of life (not even a subscription) within 10s —
                # subscribe/installworkshop URIs are silently dropped by current
                # Steam clients, so fall back to the Workshop page for a manual click.
                fallback_opened = True
                opened_fallback_now = True
                self._open_workshop_page(mid, mod_name)
                notify_check_steam()
            elif elapsed and elapsed % 30 == 0 and not subscribed:  # keep retrying in case Steam fixes the verbs
                log.warning("No progress on %s after %ds, resending subscribe URI", mod_name, elapsed)
                self._subscribe_mod_steam(mid, mod_name)
            if progress:
                if opened_fallback_now:
                    progress.set_action_prompt(f"Click Subscribe in Steam for:\n{mod_name}")
                else:
                    progress.set_action_prompt(f"Waiting for download: {mod_name}")
            time.sleep(step)
        ok = mod_installed(self.cfg, mid)
        if not ok:
            log.error("Timed out waiting for %s after %ds", mod_name, int(time.time() - start))
        return ok

    def _format_size(self, nbytes):
        nbytes = int(nbytes or 0)
        if nbytes < 1024:
            return f"{nbytes} B"
        if nbytes < 1024 ** 2:
            return f"{nbytes / 1024:.1f} KB"
        if nbytes < 1024 ** 3:
            return f"{nbytes / 1024 ** 2:.1f} MB"
        return f"{nbytes / 1024 ** 3:.2f} GB"

    def _get_mod_size(self, mid):
        """Return the on-disk size of a workshop mod (sum of all files)."""
        total = 0
        for wd in workshop_dirs(self.cfg):
            p = os.path.join(wd, str(mid))
            if os.path.isdir(p):
                for dirpath, _, filenames in os.walk(p):
                    for f in filenames:
                        try:
                            total += os.path.getsize(os.path.join(dirpath, f))
                        except OSError:
                            pass
                return total
        return 0

    def _fetch_mod_sizes(self, mod_ids):
        sizes = {}
        ids = [str(m) for m in mod_ids]
        if not ids:
            return sizes
        try:
            payload = {"itemcount": len(ids)}
            for i, mid in enumerate(ids):
                payload[f"publishedfileids[{i}]"] = mid
            response = requests.post(
                "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                data=payload,
                timeout=20,
            ).json()
            for detail in response.get("response", {}).get("publishedfiledetails", []):
                mid = str(detail.get("publishedfileid", ""))
                if mid:
                    sizes[mid] = int(detail.get("file_size", 0) or 0)
        except Exception as exc:
            log.warning("Could not fetch mod sizes: %s", exc)
        return sizes

    def _prepare_mod_queue(self, mod_ids, mod_names=None):
        sizes = self._fetch_mod_sizes(mod_ids)
        queue = sorted(mod_ids, key=lambda mid: sizes.get(str(mid), 0))
        if queue:
            order = ", ".join(
                f"{(mod_names or {}).get(str(m), m)} ({self._format_size(sizes.get(str(m), 0))})"
                for m in queue[:6]
            )
            log.info("Mod queue (smallest first): %s", order)
        return queue, sizes

    def _mark_mod_progress(self, progress, mod_id):
        mid = str(mod_id)
        if not progress:
            return
        if mod_installed(self.cfg, mid):
            progress.mark_installed(mid)
        elif mod_subscribed(self.cfg, mid):
            progress.mark_subscribed(mid)

    def _dl_and_finish(self, mod_ids, sizes, server, mod_names, name, launch, password, progress):
        self._refresh_cfg()
        names = mod_names or {}
        total = len(mod_ids)

        try:
            if progress:
                progress.set_download_progress(0, total)
            self.set_status(f"Downloading {total} mods (smallest first)…")

            ok, err = self._subscribe_and_wait_mods(
                mod_ids, names, sizes=sizes, progress=progress,
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
                self._sync_steam_subscriptions(mod_ids)
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
        """Hide the DZSL window after successfully launching DayZ (if enabled), so
        it gets out of the way while the game runs. The Python process (and its
        background threads) stays alive; a daemon watcher thread polls for DayZ
        to start and then exit, and restores the window once DayZ has closed."""
        if not self.cfg.get("close_on_launch", True):
            return
        if not self.win:
            return
        self.win.set_visible(False)
        threading.Thread(target=self._watch_dayz_and_restore, daemon=True).start()

    def _watch_dayz_and_restore(self):
        """Runs on a background daemon thread. Waits for DayZ to appear (giving up
        after ~3 minutes if it never does), then waits for it to exit, then asks
        the main thread to re-show the DZSL window."""
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
