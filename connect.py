import subprocess, threading, os, re, time
import requests
from gi.repository import GLib, Adw
from config import workshop_dir, save_json, RECENT_FILE, load_json

class Connector:
    def __init__(self, cfg, win, set_status):
        self.cfg        = cfg
        self.win        = win
        self.set_status = set_status

    def connect(self, server):
        ip   = server.get("ip") or server.get("endpoint", {}).get("ip")
        port = server.get("port") or server.get("gamePort") or server.get("endpoint", {}).get("port", 2302)
        name = server.get("name", f"{ip}:{port}")
        self._save_recent(server)
        self.set_status(f"Preparing to connect to {name}…")
        threading.Thread(target=self._thread, args=(ip, port, name), daemon=True).start()

    def is_steam_running(self):
        return subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0

    def is_dayz_running(self):
        return subprocess.run(["pgrep", "-f", "DayZ_x64"], capture_output=True).returncode == 0

    def kill_dayz(self):
        subprocess.run(["pkill", "-f", "DayZ_x64"]); time.sleep(2)

    def _get_server_mods(self, ip, port):
        try:
            d = requests.get(f"https://dayzsalauncher.com/api/v1/query/{ip}/{port}", timeout=10).json().get("result", {})
            return [str(m.get("steamWorkshopId", m.get("id", ""))) for m in d.get("mods", []) if m.get("steamWorkshopId") or m.get("id")]
        except: return []

    def _thread(self, ip, port, name):
        lp = self.cfg["launcher_path"]
        sr = self.cfg["steam_root"]

        if not self.is_steam_running():
            self.set_status("Starting Steam…")
            subprocess.Popen(["steam"])
            for _ in range(15):
                time.sleep(2)
                if self.is_steam_running(): time.sleep(3); break
            else:
                self.set_status("Steam failed to start."); return

        if self.is_dayz_running():
            self.set_status("Restarting DayZ with correct mods…"); self.kill_dayz()

        self.set_status("Fetching server mod list…")
        server_mods = self._get_server_mods(ip, port)
        wd = workshop_dir(self.cfg)

        if server_mods:
            missing = [m for m in server_mods if not os.path.isdir(f"{wd}/{m}")]
            if missing:
                GLib.idle_add(self._show_dl_dialog, missing, ip, port, name); return

        result = subprocess.run(f"STEAM_ROOT={sr} {lp} -s {ip}:{port}", shell=True, capture_output=True, text=True)
        missing_urls = re.findall(r"Subscribe the mod here: (https://\S+)", result.stdout + result.stderr)
        if missing_urls:
            ids = [u.split("=")[-1] for u in missing_urls]
            GLib.idle_add(self._show_dl_dialog, ids, ip, port, name); return

        self.set_status(f"Connecting to {name}…")
        subprocess.Popen(f"STEAM_ROOT={sr} {lp} --launch -s {ip}:{port}", shell=True)

    def _show_dl_dialog(self, mod_ids, ip, port, name):
        d = Adw.MessageDialog(transient_for=self.win)
        d.set_heading(f"{len(mod_ids)} mods required")
        d.set_body("Missing:\n" + "\n".join(f"• {m}" for m in mod_ids) + "\n\nClick Download to subscribe via Steam then connect.")
        d.add_response("cancel", "Cancel")
        d.add_response("dl", "Download & Connect")
        d.set_response_appearance("dl", Adw.ResponseAppearance.SUGGESTED)
        def on_r(_, r):
            if r == "dl": threading.Thread(target=self._dl_and_connect, args=(mod_ids, ip, port, name), daemon=True).start()
        d.connect("response", on_r); d.present()

    def _dl_and_connect(self, mod_ids, ip, port, name):
        wd = workshop_dir(self.cfg)
        self.set_status(f"Subscribing to {len(mod_ids)} mods…")
        for mid in mod_ids: subprocess.Popen(["steam", f"steam://subscribe/{mid}"]); time.sleep(1)
        self.set_status("Waiting for downloads…")
        for _ in range(120):
            if all(os.path.isdir(f"{wd}/{m}") for m in mod_ids): break
            done = sum(1 for m in mod_ids if os.path.isdir(f"{wd}/{m}"))
            self.set_status(f"Downloading… {done}/{len(mod_ids)} done"); time.sleep(5)
        self.set_status(f"Connecting to {name}…"); time.sleep(2)
        subprocess.Popen(f"STEAM_ROOT={self.cfg['steam_root']} {self.cfg['launcher_path']} --launch -s {ip}:{port}", shell=True)

    def _save_recent(self, server):
        recent = load_json(RECENT_FILE)
        ip, port = server.get("ip"), server.get("port")
        recent = [r for r in recent if not (r.get("ip") == ip and r.get("port") == port)]
        recent.insert(0, server); save_json(RECENT_FILE, recent[:20])
