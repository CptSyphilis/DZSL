import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib
import threading
from dzsl.core.config import save_json, FAVS_FILE
from dzsl.core.uri import validate_host_port
from dzsl.services.server_api import fetch_server, fetch_servers

class AddServerView:
    def __init__(self, panel, favorites, set_status, on_added=None):
        self.panel      = panel
        self.favorites  = favorites
        self.set_status = set_status
        self.on_added   = on_added

    def build(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); outer.set_vexpand(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.add_css_class("settings-group")
        box.set_halign(Gtk.Align.CENTER); box.set_valign(Gtk.Align.CENTER)
        box.set_vexpand(True); box.set_size_request(380, -1)

        lbl = Gtk.Label(label="ADD SERVER"); lbl.add_css_class("settings-title"); lbl.set_halign(Gtk.Align.START); box.append(lbl)

        paste_btn = Gtk.Button(label="Paste IP from Clipboard")
        paste_btn.add_css_class("btn-ghost")
        def do_paste(b):
            from gi.repository import Gdk
            display = Gdk.Display.get_default()
            clipboard = display.get_clipboard()
            def on_text(clip, result):
                try:

                    text = clip.read_text_finish(result).strip()
                    if ":" in text:
                        parts = text.rsplit(":", 1)
                        self.ip_e.set_text(parts[0])
                        self.pt_e.set_text(parts[1])
                    else:
                        self.ip_e.set_text(text)
                except:
                    pass

            clipboard.read_text_async(None, on_text)
        paste_btn.connect("clicked", do_paste)
        box.append(paste_btn)

        self.ip_e = Gtk.Entry(); self.ip_e.set_placeholder_text("Server IP  e.g. 193.25.252.82"); self.ip_e.add_css_class("settings-input"); box.append(self.ip_e)
        self.pt_e = Gtk.Entry(); self.pt_e.set_placeholder_text("Game port  e.g. 2402"); self.pt_e.add_css_class("settings-input"); box.append(self.pt_e)
        self.nm_e = Gtk.Entry(); self.nm_e.set_placeholder_text("Name (optional — auto-detected)"); self.nm_e.add_css_class("settings-input"); box.append(self.nm_e)

        self.res = Gtk.Label(label=""); self.res.add_css_class("status-txt"); box.append(self.res)

        self.add_btn = Gtk.Button(label="Add to Favorites"); self.add_btn.add_css_class("btn-connect"); self.add_btn.connect("clicked", self._add)
        box.append(self.add_btn); outer.append(box); self.panel.append(outer)

    def _add(self, b):
        ip = self.ip_e.get_text().strip()
        pt = self.pt_e.get_text().strip() or "2302"
        try:
            ip, pt_value = validate_host_port(ip, pt)
        except ValueError as exc:
            self.res.set_text(str(exc).capitalize() + ".")
            return
        if any(f.get("ip") == ip and str(f.get("port")) == str(pt_value) for f in self.favorites):
            self.res.set_text("Already in Favorites.")
            return
        name = self.nm_e.get_text().strip()
        self.add_btn.set_sensitive(False)
        self.res.set_text("Looking up server…")
        def q():
            try:
                srv = _lookup(ip, pt_value)
            except (OSError, RuntimeError, ValueError):
                srv = {"ip": ip, "port": pt_value, "name": f"{ip}:{pt_value}", "map": "?", "players": 0, "maxPlayers": 0, "mods": [], "firstPersonOnly": False}
            if name and srv["name"] == f"{ip}:{pt_value}":
                srv["name"] = name
            GLib.idle_add(self._save, srv)
        threading.Thread(target=q, daemon=True).start()

    def _save(self, srv):
        self.add_btn.set_sensitive(True)
        if not any(f.get("ip") == srv["ip"] and str(f.get("port")) == str(srv["port"]) for f in self.favorites):
            self.favorites.append(srv); save_json(FAVS_FILE, self.favorites)
            self.set_status(f"Saved {srv['name']}")
            if self.on_added:
                self.on_added()
        else:
            self.res.set_text("Already in Favorites.")
        return False


def _lookup(ip, port):
    from dzsl.ui.servers import _filter_state
    rows = _filter_state.get("servers") or fetch_servers(timeout=10)
    for s in rows:
        s_ip = s.get("ip") or s.get("endpoint", {}).get("ip")
        if s_ip == ip and str(s.get("gamePort") or s.get("port")) == str(port):
            return dict(s, ip=ip, port=port)
    d = fetch_server(ip, port, timeout=8)
    return {"ip": ip, "port": port, "name": d.get("name", f"{ip}:{port}"), "map": d.get("map", "?"), "players": d.get("players", 0), "maxPlayers": d.get("maxPlayers", 0), "mods": d.get("mods", []), "firstPersonOnly": d.get("firstPersonOnly", False)}
