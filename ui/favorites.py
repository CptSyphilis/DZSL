import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from ui.server_row import ServerRow

class ListView:
    def __init__(self, panel, servers, empty_msg, favorites, connect_cb, fav_cb, load_mods_cb=None):
        self.panel      = panel
        self.servers    = servers
        self.empty_msg  = empty_msg
        self.favorites  = favorites
        self.connect_cb = connect_cb
        self.fav_cb     = fav_cb
        self.load_mods_cb = load_mods_cb

    def build(self):
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tb.add_css_class("toolbar")
        se = Gtk.Entry(); se.set_placeholder_text("Search...")
        se.add_css_class("search-box"); se.set_hexpand(True); tb.append(se)
        rb = Gtk.Button(label="Refresh"); rb.add_css_class("toolbar-btn")
        rb.connect("clicked", lambda b: self._populate(box, self.servers))
        tb.append(rb)
        self.panel.append(tb)

        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._populate(box, self.servers)

        se.connect("changed", lambda e: self._populate(box, [
            s for s in self.servers
            if e.get_text().lower() in s.get("name", "").lower()
            or e.get_text().lower() in s.get("map", "").lower()
        ]))

        rb.connect("clicked", lambda b: self._populate(box, self.servers))
        scroll.set_child(box); self.panel.append(scroll)

    def _populate(self, box, servers):
        c = box.get_first_child()
        while c: n = c.get_next_sibling(); box.remove(c); c = n
        if not servers:
            el = Gtk.Label(label=self.empty_msg)
            el.add_css_class("empty"); el.set_justify(Gtk.Justification.CENTER)
            el.set_margin_top(80); box.append(el)
            return
        for s in servers:
            is_fav = any(f.get("ip") == s.get("ip") and f.get("port") == s.get("port") for f in self.favorites)
            box.append(ServerRow(s, self.connect_cb, self.fav_cb, is_fav, self.load_mods_cb))
