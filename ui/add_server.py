import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib
import requests, threading
from config import save_json, FAVS_FILE

class AddServerView:
    def __init__(self, panel, favorites, set_status):
        self.panel      = panel
        self.favorites  = favorites
        self.set_status = set_status
        self._queried   = None

    def build(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); outer.set_vexpand(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.add_css_class("settings-group")
        box.set_halign(Gtk.Align.CENTER); box.set_valign(Gtk.Align.CENTER)
        box.set_vexpand(True); box.set_size_request(380, -1)

        lbl = Gtk.Label(label="ADD SERVER"); lbl.add_css_class("settings-title"); lbl.set_halign(Gtk.Align.START); box.append(lbl)

        self.ip_e = Gtk.Entry(); self.ip_e.set_placeholder_text("Server IP  e.g. 193.25.252.82"); self.ip_e.add_css_class("settings-input"); box.append(self.ip_e)
        self.pt_e = Gtk.Entry(); self.pt_e.set_placeholder_text("Game port  e.g. 2402"); self.pt_e.add_css_class("settings-input"); box.append(self.pt_e)
        self.nm_e = Gtk.Entry(); self.nm_e.set_placeholder_text("Name (optional — auto-detected)"); self.nm_e.add_css_class("settings-input"); box.append(self.nm_e)

        self.res = Gtk.Label(label=""); self.res.add_css_class("status-txt"); box.append(self.res)

        brow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        qb = Gtk.Button(label="Query server"); qb.add_css_class("btn-ghost"); qb.connect("clicked", self._query); brow.append(qb)
        ab = Gtk.Button(label="Add to Favorites"); ab.add_css_class("btn-connect"); ab.connect("clicked", self._add); brow.append(ab)
        box.append(brow); outer.append(box); self.panel.append(outer)

    def _query(self, b):
        ip = self.ip_e.get_text().strip()
        pt = self.pt_e.get_text().strip() or "2302"
        if not ip: self.res.set_text("Enter an IP address."); return
        self.res.set_text("Querying…")
        def q():
            try:
                d = requests.get(f"https://dayzsalauncher.com/api/v1/query/{ip}/{pt}", timeout=8).json().get("result", {})
                self._queried = {"ip": ip, "port": int(pt), "name": d.get("name", f"{ip}:{pt}"), "map": d.get("map", "?"), "players": d.get("players", 0), "maxPlayers": d.get("maxPlayers", 0), "mods": d.get("mods", []), "firstPersonOnly": d.get("firstPersonOnly", False)}
                GLib.idle_add(self.res.set_text, f"Found: {self._queried['name']}")
            except:
                self._queried = {"ip": ip, "port": int(pt), "name": self.nm_e.get_text() or f"{ip}:{pt}", "map": "?", "players": 0, "maxPlayers": 0, "mods": [], "firstPersonOnly": False}
                GLib.idle_add(self.res.set_text, "Could not query — will save manually.")
        threading.Thread(target=q, daemon=True).start()

    def _add(self, b):
        ip = self.ip_e.get_text().strip()
        pt = self.pt_e.get_text().strip() or "2302"
        if not ip: self.res.set_text("Enter an IP address."); return
        srv = self._queried or {"ip": ip, "port": int(pt), "name": self.nm_e.get_text() or f"{ip}:{pt}", "map": "?", "players": 0, "maxPlayers": 0, "mods": [], "firstPersonOnly": False}
        if not any(f.get("ip") == ip and str(f.get("port")) == pt for f in self.favorites):
            self.favorites.append(srv); save_json(FAVS_FILE, self.favorites)
            self.res.set_text("OK Added to Favorites"); self.set_status(f"Saved {srv['name']}")
        else:
            self.res.set_text("Already in Favorites.")
