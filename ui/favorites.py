import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import threading
from ui.server_row import ServerRow
from ui.helpers import clear_box, recent_map
from ui.ping import ping_servers

class ListView:
    def __init__(self, panel, servers, empty_msg, favorites, connect_cb, fav_cb,
                 load_mods_cb=None, set_status=None, add_server_cb=None):
        self.panel      = panel
        self.servers    = servers
        self.empty_msg  = empty_msg
        self.favorites  = favorites
        self.connect_cb = connect_cb
        self.fav_cb     = fav_cb
        self.load_mods_cb = load_mods_cb
        self.set_status = set_status or (lambda _msg: None)
        self.add_server_cb = add_server_cb
        self.list_box = None
        self._ping_generation = 0
        self._expand_tracker = [None]

    def build(self):
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tb.add_css_class("toolbar")
        se = Gtk.Entry(); se.set_placeholder_text("Search...")
        se.add_css_class("search-box"); se.set_hexpand(True); tb.append(se)
        rb = Gtk.Button(label="Refresh"); rb.add_css_class("toolbar-btn")
        rb.connect("clicked", lambda b: self._populate(box, self.servers))
        tb.append(rb)
        if self.add_server_cb:
            ab = Gtk.Button(label="+ Add Server"); ab.add_css_class("toolbar-btn"); ab.add_css_class("accent")
            ab.connect("clicked", lambda _: self.add_server_cb())
            tb.append(ab)
        self.panel.append(tb)

        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.list_box = box
        self._populate(box, self.servers)

        se.connect("changed", lambda e: self._populate(box, [
            s for s in self.servers
            if e.get_text().lower() in s.get("name", "").lower()
            or e.get_text().lower() in s.get("map", "").lower()
        ]))

        rb.connect("clicked", lambda b: self._populate(box, self.servers))
        scroll.set_child(box); self.panel.append(scroll)

    def _populate(self, box, servers):
        clear_box(box)
        self._expand_tracker[0] = None
        if not servers:
            el = Gtk.Label(label=self.empty_msg)
            el.add_css_class("empty"); el.set_justify(Gtk.Justification.CENTER)
            el.set_margin_top(80); box.append(el)
            return
        played_lookup = recent_map()
        for s in servers:
            is_fav = any(f.get("ip") == s.get("ip") and f.get("port") == s.get("port") for f in self.favorites)
            box.append(ServerRow(
                s, self.connect_cb, self.fav_cb, is_fav,
                self.load_mods_cb, self.set_status, played_lookup=played_lookup,
                expand_tracker=self._expand_tracker,
            ))
        self._start_ping(servers)

    def _start_ping(self, servers):
        self._ping_generation += 1
        generation = self._ping_generation
        threading.Thread(
            target=self._ping_batch,
            args=(servers, generation),
            daemon=True,
        ).start()

    def _ping_batch(self, servers, generation):
        ping_servers(servers, limit=len(servers))
        if generation == self._ping_generation:
            GLib.idle_add(self._refresh_pings)

    def _refresh_pings(self):
        if not self.list_box:
            return
        row = self.list_box.get_first_child()
        while row:
            if hasattr(row, "update_ping"):
                row.update_ping()
            row = row.get_next_sibling()
