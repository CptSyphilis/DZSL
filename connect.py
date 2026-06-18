import subprocess, threading, os, re, time, shlex
import requests
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GLib, Adw, Gtk
from config import (
    DAYZ_APPID, mod_installed, mod_subscribed, is_steam_running,
    save_json, RECENT_FILE, load_json, load_cfg, FAVS_FILE,
    _detect_steamcmd,
)

from ui.progress import ModProgressDialog
from ui.helpers import filter_server_mods

def launch_steam():
    subprocess.Popen(
        ["steam"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

class Connector:
    def __init__(self, cfg, win, set_status):
        self.cfg        = cfg
        self.win        = win
        self.set_status = set_status

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
        ip = self._server_ip(server)
        port = self._game_port(server)
        name = server.get("name", f"{ip}:{port}")
        if launch:
            self._save_recent(server)
        verb = "Connecting to" if launch else "Loading mods for"
        self.set_status(f"{verb} {name}…")
        threading.Thread(
            target=self._thread,
            args=(server, launch, password),
            daemon=True,
        ).start()

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

    def _missing_from_output(self, result):
        return re.findall(
            r"Subscribe the mod here: (https://\S+)",
            (result.stdout or "") + (result.stderr or ""),
        )

    def _ensure_steam_for_launch(self):
        if self.is_steam_running():
            return True
        self.set_status("Starting Steam…")
        launch_steam()
        for _ in range(45):
            time.sleep(2)
            if self.is_steam_running():
                time.sleep(3)
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
                progress = ModProgressDialog(
                    self.win,
                    f"Downloading {len(queue)} mods",
                    queue,
                    mod_names or {},
                    on_open_downloads=self._open_steam_downloads,
                )
                threading.Thread(
                    target=self._dl_and_finish,
                    args=(queue, sizes, server, mod_names, name, launch, password, progress),
                    daemon=True,
                ).start()
                return

        result = self._run_launcher(server, mod_ids=server_mods, launch=False, password=password)
        missing_urls = self._missing_from_output(result)
        if missing_urls:
            ids = [u.split("=")[-1] for u in missing_urls]
            self._refresh_cfg()
            queue, sizes = self._prepare_mod_queue(ids, mod_names)
            progress = ModProgressDialog(
                self.win,
                f"Downloading {len(queue)} mods",
                queue,
                mod_names or {},
                on_open_downloads=self._open_steam_downloads,
            )
            threading.Thread(
                target=self._dl_and_finish,
                args=(queue, sizes, server, mod_names, name, launch, password, progress),
                daemon=True,
            ).start()
            return
        if result.returncode:
            err = self._launcher_error(result)
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
                self.set_status(f"Failed to launch DayZ — {err}")
                self._show_error("Could not launch DayZ", err or "The launcher script failed.")
            else:
                self.set_status(f"Launched DayZ — {name}")
                GLib.idle_add(self._close_app)
        else:
            if server_mods and self.is_steam_running():
                self._sync_steam_subscriptions(server_mods, start_if_needed=False)
            self.set_status(f"Mods ready for {name}")

    def _ensure_steam_for_workshop(self):
        if self.is_steam_running():
            return True
        self.set_status("Starting Steam for workshop mods…")
        launch_steam()
        for _ in range(45):
            time.sleep(2)
            if self.is_steam_running():
                time.sleep(4)
                return True
        return False

    def _show_dl_dialog(self, mod_ids, server, mod_names, name, launch, password):
        names = mod_names or {}
        lines = [f"• {names.get(m, m)}" for m in mod_ids]
        action = "download, set up mods, and connect" if launch else "download and set up mods"
        d = Adw.MessageDialog(transient_for=self.win)
        d.set_heading(f"{len(mod_ids)} mods required")
        d.set_body(
            "Missing:\n" + "\n".join(lines[:12])
            + ("\n…" if len(lines) > 12 else "")
            + f"\n\nDZSL will download and set up mods for {action} (via steamcmd if available, or Steam client)."
        )
        d.add_response("cancel", "Cancel")
        d.add_response("dl", "Download & Connect" if launch else "Download Mods")
        d.set_response_appearance("dl", Adw.ResponseAppearance.SUGGESTED)
        def on_r(_, r):
            if r == "dl":
                self._refresh_cfg()
                queue, sizes = self._prepare_mod_queue(mod_ids, names)
                progress = ModProgressDialog(
                    self.win,
                    f"Downloading {len(queue)} mods",
                    queue,
                    names,
                    on_open_downloads=self._open_steam_downloads,
                )
                threading.Thread(
                    target=self._dl_and_finish,
                    args=(queue, sizes, server, mod_names, name, launch, password, progress),
                    daemon=True,
                ).start()
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
        try:
            subprocess.Popen(["steam", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[DZSL] steam uri -> steam: {uri}", flush=True)
            return True
        except OSError:
            pass
        try:
            steam_bin = os.path.expanduser("~/.steam/root/ubuntu12_32/steam")
            if os.path.isfile(steam_bin):
                subprocess.Popen([steam_bin, uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"[DZSL] steam uri -> {steam_bin}: {uri}", flush=True)
                return True
        except OSError:
            pass
        return False

    def _mod_download_timeout(self, nbytes):
        nbytes = int(nbytes or 0)
        if nbytes >= 5 * 1024 ** 3:
            return 6 * 3600
        if nbytes >= 1024 ** 3:
            return 3 * 3600
        if nbytes >= 100 * 1024 ** 2:
            return 3600
        return 900

    def _steamcmd_path(self):
        path = self.cfg.get("steamcmd_path") or ""
        if not path or not os.path.isfile(path):
            # fallback detection
            path = _detect_steamcmd() or ""
            if not path or not os.path.isfile(path):
                bundled = os.path.expanduser("~/.config/dzsl/steamcmd/steamcmd.sh")
                if os.path.isfile(bundled):
                    path = bundled
        return path if path and os.path.isfile(path) else ""

    def _steamcmd_login_args(self):
        user = (self.cfg.get("steam_username") or "").strip()
        pwd = (self.cfg.get("steam_password") or "").strip()
        if user and pwd:
            return ["+login", user, pwd]
        return ["+login", "anonymous"]

    def _steamcmd_download_mod(self, mod_id, mod_name, size_bytes=0, retries=2):
        mid = str(mod_id)
        steamcmd = self._steamcmd_path()
        if not steamcmd:
            return False, "steamcmd not found"

        steam_root = self.cfg.get("steam_root") or ""
        if not steam_root or not os.path.isdir(steam_root):
            return False, f"Steam root not found: {steam_root}"

        cmd = [
            steamcmd,
            "+force_install_dir", steam_root,
            *self._steamcmd_login_args(),
            "+workshop_download_item", DAYZ_APPID, mid,
            "+quit",
        ]
        print(f"[DZSL] steamcmd download: {mod_name} ({mid})", flush=True)
        for attempt in range(max(retries, 1)):
            if attempt:
                print(f"[DZSL] steamcmd retry {attempt + 1} for {mod_name}", flush=True)
                time.sleep(5)
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self._mod_download_timeout(size_bytes),
                )
            except subprocess.TimeoutExpired:
                return False, f"Timed out downloading {mod_name}"
            except OSError as exc:
                return False, str(exc)

            output = (result.stdout or "") + (result.stderr or "")
            self._refresh_cfg()
            if mod_installed(self.cfg, mid):
                print(f"[DZSL] Downloaded: {mod_name}", flush=True)
                return True, ""
            if "Success. Downloaded item" in output:
                time.sleep(1)
                self._refresh_cfg()
                if mod_installed(self.cfg, mid):
                    return True, ""

            last_err = ""
            for line in output.splitlines():
                low = line.lower()
                if "error" in low or "failed" in low or "denied" in low:
                    last_err = line.strip()
                    break
            if not last_err and result.returncode:
                last_err = "\n".join(output.splitlines()[-3:]).strip()
            if last_err and "no connection" not in last_err.lower():
                return False, last_err or f"steamcmd failed for {mod_name}"

        if mod_installed(self.cfg, mid):
            return True, ""
        return False, last_err or f"Download finished but mod folder missing for {mod_name}"

    def _ensure_steamcmd(self):
        """Ensure steamcmd is available, auto-downloading if necessary."""
        path = self._steamcmd_path()
        if path:
            return path
        steamcmd_dir = os.path.expanduser("~/.config/dzsl/steamcmd")
        os.makedirs(steamcmd_dir, exist_ok=True)
        steamcmd_sh = os.path.join(steamcmd_dir, "steamcmd.sh")
        if os.path.isfile(steamcmd_sh):
            self.cfg["steamcmd_path"] = steamcmd_sh
            return steamcmd_sh
        self.set_status("Installing steamcmd for mod downloads...")
        try:
            import urllib.request
            import tarfile
            import io
            url = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz"
            print("[DZSL] Downloading steamcmd...", flush=True)
            with urllib.request.urlopen(url, timeout=120) as resp:
                data = resp.read()
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                tar.extractall(steamcmd_dir)
            os.chmod(steamcmd_sh, 0o755)
            self.cfg["steamcmd_path"] = steamcmd_sh
            try:
                from config import save_cfg
                save_cfg(self.cfg)
            except Exception:
                pass
            print(f"[DZSL] steamcmd installed to {steamcmd_sh}", flush=True)
            self.set_status("steamcmd ready.")
            return steamcmd_sh
        except Exception as exc:
            print(f"[DZSL] Auto-install steamcmd failed: {exc}", flush=True)
            self.set_status("Could not set up steamcmd, using Steam client...")
            return ""

    def _subscribe_mod_steam(self, mod_id, mod_name):
        mid = str(mod_id)
        if mod_installed(self.cfg, mid):
            return
        print(f"[DZSL] Steam subscribe: {mod_name} ({mid})", flush=True)
        self._forward_steam_uri(f"steam://subscribe/{mid}")
        time.sleep(1)

    def _sync_steam_subscriptions(self, mod_ids, start_if_needed=True):
        if not mod_ids:
            return
        if start_if_needed and not self.is_steam_running():
            self.set_status("Starting Steam to subscribe mods…")
            launch_steam()
            for _ in range(20):
                time.sleep(2)
                if self.is_steam_running():
                    time.sleep(2)
                    break
        if not self.is_steam_running():
            return
        for mid in mod_ids:
            mid = str(mid)
            self._forward_steam_uri(f"steam://subscribe/{mid}")
            time.sleep(0.3)
            self._forward_steam_uri(f"steam://installworkshop/{DAYZ_APPID}/{mid}")
            time.sleep(0.5)

    def _subscribe_and_wait_mods(self, mod_ids, mod_names, sizes=None, progress=None):
        """Subscribe to needed mods (restored to original simple working logic, with steamcmd if available)."""
        self._refresh_cfg()
        sc = self._steamcmd_path()
        if sc and os.path.isfile(sc):
            sr = self.cfg.get("steam_root") or ""
            for mid in mod_ids:
                if progress and progress.is_cancelled():
                    return False, "cancelled"
                mid = str(mid)
                mod_name = (mod_names or {}).get(mid, mid)
                size_bytes = (sizes or {}).get(mid, 0)
                size_str = self._format_size(size_bytes)
                if mod_installed(self.cfg, mid):
                    self._mark_mod_progress(progress, mid)
                    done = sum(1 for m in mod_ids if mod_installed(self.cfg, m))
                    if progress:
                        progress.set_download_progress(done, len(mod_ids))
                    continue
                self.set_status(f"Downloading {mod_name} ({size_str}) via steamcmd…")
                if progress:
                    progress.set_action_prompt(f"Downloading via steamcmd:\n{mod_name}\n({size_str})")
                cmd = [sc, "+force_install_dir", sr, "+login", "anonymous", "+workshop_download_item", "221100", mid, "+quit"]
                subprocess.Popen(cmd)
                # wait for dir
                for _ in range(120):
                    if progress and progress.is_cancelled():
                        return False, "cancelled"
                    if mod_installed(self.cfg, mid):
                        break
                    time.sleep(5)
                self._mark_mod_progress(progress, mid)
                print(f"[DZSL] Done with: {mod_name}", flush=True)
            return True, ""
        # simple client like original
        names = mod_names or {}
        done = 0
        total = len(mod_ids)
        for mid in mod_ids:
            if progress and progress.is_cancelled():
                return False, "cancelled"
            mid = str(mid)
            mod_name = names.get(mid, mid)
            if mod_installed(self.cfg, mid):
                self._mark_mod_progress(progress, mid)
                done += 1
                if progress:
                    progress.set_download_progress(done, total)
                continue
            self.set_status(f"Subscribing to {mod_name}…")
            if progress:
                progress.set_action_prompt(f"Subscribing via Steam:\n{mod_name}")
            self._subscribe_mod_steam(mid, mod_name)
            if not self._wait_for_mod_installed(mid, progress, mod_name):
                return False, f"Timeout waiting for {mod_name}"
            self._mark_mod_progress(progress, mid)
            done += 1
            if progress:
                progress.set_download_progress(done, total)
            print(f"[DZSL] Done with: {mod_name}", flush=True)
        return True, ""

    def _wait_for_mod_installed(self, mod_id, progress, mod_name, size_bytes=0):
        mid = str(mod_id)
        self.set_status(f"Waiting for {mod_name} download…")
        for _ in range(120):  # 10 minutes
            if progress and progress.is_cancelled():
                return False
            self._refresh_cfg()
            if mod_installed(self.cfg, mid):
                return True
            done = sum(1 for m in [mod_id] if mod_installed(self.cfg, m))  # simplistic
            if progress:
                progress.set_action_prompt(f"Waiting for download: {mod_name}")
            time.sleep(5)
        return mod_installed(self.cfg, mid)

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
            print(f"[DZSL] Could not fetch mod sizes: {exc}", flush=True)
        return sizes

    def _prepare_mod_queue(self, mod_ids, mod_names=None):
        sizes = self._fetch_mod_sizes(mod_ids)
        queue = sorted(mod_ids, key=lambda mid: sizes.get(str(mid), 0))
        if queue:
            order = ", ".join(
                f"{(mod_names or {}).get(str(m), m)} ({self._format_size(sizes.get(str(m), 0))})"
                for m in queue[:6]
            )
            print(f"[DZSL] Mod queue (smallest first): {order}", flush=True)
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
        self._ensure_steamcmd()
        names = mod_names or {}
        total = len(mod_ids)

        try:
            if progress:
                progress.set_download_progress(0, total)
            self.set_status(f"Downloading {total} mods (smallest first)…")

            ok, err = self._subscribe_and_wait_mods(
                mod_ids, names, sizes=sizes, progress=progress,
            )
            if err == "cancelled" or self._download_cancelled(progress):
                self.set_status("Download cancelled.")
                return
            if not ok:
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
                    self.set_status(f"Failed to launch DayZ — {err}")
                    self._show_error("Could not launch DayZ", err or "The launcher script failed.")
                else:
                    self.set_status(f"Launched DayZ — {name}")
                    GLib.idle_add(self._close_app)
            else:
                self.set_status(f"Mods loaded for {name}")
        finally:
            if progress:
                progress.close()

    def _save_recent(self, server):
        recent = load_json(RECENT_FILE)
        ip = server.get("ip") or server.get("endpoint", {}).get("ip")
        port = server.get("port") or server.get("gamePort") or server.get("endpoint", {}).get("port")
        recent = [r for r in recent if not (r.get("ip") == ip and r.get("port") == port)]
        entry = dict(server)
        entry["joined_at"] = time.time()
        recent.insert(0, entry)
        save_json(RECENT_FILE, recent[:20])

    def _close_app(self):
        """Close the main window after successfully launching DayZ (if enabled)."""
        if self.cfg.get("close_on_launch", True):
            if self.win:
                self.win.close()
