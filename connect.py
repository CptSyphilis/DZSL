import subprocess, threading, os, re, time, shlex
import requests
from gi.repository import GLib, Adw
from config import workshop_dir, save_json, RECENT_FILE, load_json, load_cfg

class Connector:
    def __init__(self, cfg, win, set_status):
        self.cfg        = cfg
        self.win        = win
        self.set_status = set_status

    def _refresh_cfg(self):
        self.cfg = load_cfg()

    def connect(self, server):
        self._start(server, launch=True)

    def load_mods(self, server):
        self._start(server, launch=False)

    def _start(self, server, launch=True):
        self._refresh_cfg()
        ip   = server.get("ip") or server.get("endpoint", {}).get("ip")
        port = server.get("port") or server.get("gamePort") or server.get("endpoint", {}).get("port", 2302)
        name = server.get("name", f"{ip}:{port}")
        if launch:
            self._save_recent(server)
        verb = "Connecting to" if launch else "Loading mods for"
        self.set_status(f"{verb} {name}…")
        threading.Thread(target=self._thread, args=(ip, port, name, launch), daemon=True).start()

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

    def _get_server_mods(self, ip, port):
        info = self._get_server_info(ip, port)
        return [
            str(m.get("steamWorkshopId", m.get("id", "")))
            for m in info.get("mods", [])
            if m.get("steamWorkshopId") or m.get("id")
        ]

    def _mod_names(self, ip, port):
        info = self._get_server_info(ip, port)
        names = {}
        for m in info.get("mods", []):
            mid = str(m.get("steamWorkshopId", m.get("id", "")))
            if mid:
                names[mid] = m.get("name", mid)
        return names

    def _game_params(self):
        params = []
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

    def _launcher_cmd(self, ip, port, launch=True):
        lp = self.cfg["launcher_path"]
        sr = self.cfg["steam_root"]
        cmd = ["env", f"STEAM_ROOT={sr}", lp]
        if launch:
            cmd.append("--launch")
        cmd.extend(["-s", self._server_addr(ip, port)])
        if self.cfg.get("profile_name"):
            cmd.extend(["-n", self.cfg["profile_name"]])
        extra_mods = self.cfg.get("extra_mods", "").strip()
        if extra_mods:
            for mid in extra_mods.split(";"):
                mid = mid.strip()
                if mid:
                    cmd.append(mid)
        if launch:
            game_params = self._game_params()
            if game_params:
                cmd.append("--")
                cmd.extend(game_params)
        return cmd

    def _run_launcher(self, ip, port, launch=True):
        return subprocess.run(
            self._launcher_cmd(ip, port, launch=launch),
            capture_output=True,
            text=True,
        )

    def _missing_from_output(self, result):
        return re.findall(
            r"Subscribe the mod here: (https://\S+)",
            (result.stdout or "") + (result.stderr or ""),
        )

    def _ensure_steam(self):
        if self.is_steam_running():
            return True
        self.set_status("Starting Steam…")
        subprocess.Popen(["steam"])
        for _ in range(15):
            time.sleep(2)
            if self.is_steam_running():
                time.sleep(3)
                return True
        self.set_status("Steam failed to start.")
        return False

    def _thread(self, ip, port, name, launch):
        if not self._ensure_steam():
            return

        if launch and self.is_dayz_running():
            self.set_status("Restarting DayZ with correct mods…")
            self.kill_dayz()

        self.set_status("Fetching server mod list…")
        server_mods = self._get_server_mods(ip, port)
        wd = workshop_dir(self.cfg)

        if server_mods:
            missing = [m for m in server_mods if not os.path.isdir(f"{wd}/{m}")]
            if missing:
                GLib.idle_add(
                    self._show_dl_dialog,
                    missing,
                    ip,
                    port,
                    name,
                    launch,
                )
                return

        result = self._run_launcher(ip, port, launch=False)
        missing_urls = self._missing_from_output(result)
        if missing_urls:
            ids = [u.split("=")[-1] for u in missing_urls]
            GLib.idle_add(self._show_dl_dialog, ids, ip, port, name, launch)
            return

        if launch:
            self.set_status(f"Launching DayZ — {name}…")
            subprocess.Popen(self._launcher_cmd(ip, port, launch=True))
        else:
            self.set_status(f"Mods ready for {name}")

    def _show_dl_dialog(self, mod_ids, ip, port, name, launch):
        names = self._mod_names(ip, port)
        lines = [f"• {names.get(m, m)}" for m in mod_ids]
        action = "download, set up mods, and connect" if launch else "download and set up mods"
        d = Adw.MessageDialog(transient_for=self.win)
        d.set_heading(f"{len(mod_ids)} mods required")
        d.set_body(
            "Missing:\n" + "\n".join(lines[:12])
            + ("\n…" if len(lines) > 12 else "")
            + f"\n\nDZSL will {action} via Steam."
        )
        d.add_response("cancel", "Cancel")
        d.add_response("dl", "Download & Connect" if launch else "Download Mods")
        d.set_response_appearance("dl", Adw.ResponseAppearance.SUGGESTED)
        def on_r(_, r):
            if r == "dl":
                threading.Thread(
                    target=self._dl_and_finish,
                    args=(mod_ids, ip, port, name, launch),
                    daemon=True,
                ).start()
        d.connect("response", on_r)
        d.present()

    def _dl_and_finish(self, mod_ids, ip, port, name, launch):
        wd = workshop_dir(self.cfg)
        total = len(mod_ids)
        self.set_status(f"Subscribing to {total} mods…")
        for mid in mod_ids:
            subprocess.Popen(["steam", f"steam://subscribe/{mid}"])
            time.sleep(1)

        self.set_status("Waiting for Steam downloads…")
        for _ in range(120):
            done = sum(1 for m in mod_ids if os.path.isdir(f"{wd}/{m}"))
            if done == total:
                break
            self.set_status(f"Downloading mods… {done}/{total}")
            time.sleep(5)

        self.set_status("Setting up mod symlinks…")
        time.sleep(2)
        result = self._run_launcher(ip, port, launch=False)
        still_missing = self._missing_from_output(result)
        if still_missing:
            self.set_status("Some mods still missing — check Steam downloads.")
            return

        if launch:
            self.set_status(f"Launching DayZ — {name}…")
            time.sleep(1)
            subprocess.Popen(self._launcher_cmd(ip, port, launch=True))
        else:
            self.set_status(f"Mods loaded for {name}")

    def _save_recent(self, server):
        recent = load_json(RECENT_FILE)
        ip = server.get("ip") or server.get("endpoint", {}).get("ip")
        port = server.get("port") or server.get("gamePort") or server.get("endpoint", {}).get("port")
        recent = [r for r in recent if not (r.get("ip") == ip and r.get("port") == port)]
        recent.insert(0, server)
        save_json(RECENT_FILE, recent[:20])