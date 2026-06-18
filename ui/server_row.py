import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gdk, GLib, Adw, Graphene
from ui.helpers import format_played, format_server_time, normalize_map_name, server_key, recent_map, format_server_subtitle, server_tags

def copy_text(text):
    Gdk.Display.get_default().get_clipboard().set(
        Gdk.ContentProvider.new_for_value(text))

def _unparent_popover(popover):
    if popover and popover.get_parent():
        popover.unparent()
    return False

def dismiss_popover(popover):
    if not popover:
        return
    popover.popdown()
    GLib.idle_add(_unparent_popover, popover)

def _scroll_parent(widget):
    parent = widget.get_parent()
    while parent:
        if isinstance(parent, Gtk.ScrolledWindow):
            return parent
        parent = parent.get_parent()
    return widget.get_root() or widget

def popup_at_cursor(popover, widget, x, y):
    anchor = _scroll_parent(widget)
    in_pt = Graphene.Point()
    in_pt.x = x
    in_pt.y = y
    ok, out_pt = widget.compute_point(anchor, in_pt)
    ax, ay = (out_pt.x, out_pt.y) if ok else (x, y)

    rect = Gdk.Rectangle()
    rect.x = int(ax)
    rect.y = int(ay)
    rect.width = 1
    rect.height = 1

    popover.set_parent(anchor)
    popover.set_has_arrow(False)
    popover.set_autohide(True)
    popover.set_pointing_to(rect)
    popover.set_position(Gtk.PositionType.BOTTOM)
    popover.popup()

class ServerRow(Gtk.Box):
    def __init__(self, server, on_connect, on_fav, is_fav=True, on_load_mods=None,
                 set_status=None, played_lookup=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add_css_class("table-row")
        self.server = server
        self.on_connect = on_connect
        self.on_fav = on_fav
        self.on_load_mods = on_load_mods or (lambda s: None)
        self.set_status = set_status or (lambda _msg: None)

        ip = server.get("ip") or server.get("endpoint", {}).get("ip", "")
        port = server.get("port") or server.get("gamePort") or 2302
        pw = server.get("password") or server.get("hasPassword", False)
        pl = server.get("players", 0)
        mxp = server.get("maxPlayers", server.get("maxplayers", 0))
        ping = server.get("ping")

        played_lookup = played_lookup or {}
        played_ts = played_lookup.get(server_key(server)) or recent_map().get(server_key(server))

        fb = Gtk.Button(label="★" if is_fav else "☆")
        fb.add_css_class("fav-star" if is_fav else "fav-star-empty")
        fb.set_size_request(36, -1)
        fb.connect("clicked", lambda b: on_fav(server, b))
        self.append(fb)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        info.set_hexpand(True)
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        nl = Gtk.Label(label=server.get("name", "Unknown"))
        nl.add_css_class("srv-name")
        nl.set_halign(Gtk.Align.START)
        nl.set_ellipsize(3)
        top.append(nl)
        if pw:
            lock = Gtk.Label(label="🔒")
            lock.add_css_class("tag")
            lock.add_css_class("tag-pass")
            top.append(lock)
        for tag in server_tags(server)[:3]:
            tl = Gtk.Label(label=tag)
            tl.add_css_class("tag")
            tl.add_css_class("tag-van")
            top.append(tl)
        info.append(top)
        ip_lbl = Gtk.Label(label=format_server_subtitle(server))
        ip_lbl.add_css_class("srv-ip")
        ip_lbl.set_halign(Gtk.Align.START)
        info.append(ip_lbl)
        self.append(info)

        time_lbl = Gtk.Label(label=format_server_time(server))
        time_lbl.add_css_class("srv-time")
        time_lbl.set_size_request(72, -1)
        time_lbl.set_halign(Gtk.Align.CENTER)
        self.append(time_lbl)

        played_lbl = Gtk.Label(label=format_played(played_ts))
        played_lbl.add_css_class("srv-played")
        played_lbl.set_size_request(90, -1)
        played_lbl.set_halign(Gtk.Align.CENTER)
        self.append(played_lbl)

        map_lbl = Gtk.Label(label=normalize_map_name(server.get("map")))
        map_lbl.add_css_class("srv-detail")
        map_lbl.set_size_request(100, -1)
        map_lbl.set_halign(Gtk.Align.CENTER)
        self.append(map_lbl)

        pl_lbl = Gtk.Label(label=f"{pl}/{mxp}")
        pl_lbl.add_css_class("srv-players")
        pl_lbl.set_size_request(72, -1)
        pl_lbl.set_halign(Gtk.Align.CENTER)
        self.append(pl_lbl)

        self.ping_lbl = Gtk.Label(label=self._ping_text(ping))
        self.ping_lbl.add_css_class(self._ping_class(ping))
        self.ping_lbl.set_size_request(52, -1)
        self.ping_lbl.set_halign(Gtk.Align.CENTER)
        self.append(self.ping_lbl)

        cb = Gtk.Button(label="▶")
        cb.add_css_class("btn-play")
        cb.set_size_request(44, -1)
        cb.connect("clicked", lambda b: on_connect(server))
        self.append(cb)

        # Right-click
        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)
        gesture.connect("pressed", self._on_right_click)
        self.add_controller(gesture)

    def _ping_text(self, ping):
        return f"{ping}" if ping else "-"

    def _ping_class(self, ping):
        if ping and ping < 80:
            return "ping-good"
        if ping and ping < 150:
            return "ping-ok"
        return "ping-bad"

    def update_ping(self):
        ping = self.server.get("ping")
        self.ping_lbl.set_text(self._ping_text(ping))
        self.ping_lbl.remove_css_class("ping-good")
        self.ping_lbl.remove_css_class("ping-ok")
        self.ping_lbl.remove_css_class("ping-bad")
        self.ping_lbl.add_css_class(self._ping_class(ping))

    def _on_right_click(self, gesture, n_press, x, y):
        if n_press != 1:
            return

        dismiss_popover(getattr(self, "_popover", None))
        popover = Gtk.Popover.new()
        self._popover = popover
        popover.connect("closed", lambda *_: dismiss_popover(popover))

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)

        for label, callback in [
            ("Join Server", self.on_connect),
            ("Load Mods Only", self._load_mods_only),
            ("Load Mods + Join", self._load_mods_and_join),
            ("Unsubscribe Server Mods", self._unsubscribe_mods),
            ("Toggle Favorite", lambda s: self.on_fav(self.server, None)),
            ("Copy IP:Port", self._copy_ip),
            ("Server Properties", self._show_properties),
        ]:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", self._menu_action(popover, callback))
            vbox.append(btn)

        popover.set_child(vbox)
        popup_at_cursor(popover, self, x, y)

    def _menu_action(self, popover, callback):
        def handler(_btn):
            if callback in (self._copy_ip, self._show_properties):
                callback()
            else:
                callback(self.server)
            popover.popdown()
        return handler

    def _load_mods_only(self, server=None):
        self.on_load_mods(self.server)

    def _load_mods_and_join(self, server=None):
        self.on_connect(self.server)

    def _unsubscribe_mods(self, server=None):
        from ui.helpers import prompt_unsubscribe_server_mods
        prompt_unsubscribe_server_mods(self, self.server, self.set_status)

    def _copy_ip(self):
        ip = self.server.get("ip") or self.server.get("endpoint", {}).get("ip", "")
        port = self.server.get("port") or self.server.get("gamePort", 2302)
        copy_text(f"{ip}:{port}")

    def _show_properties(self):
        from ui.server_properties import show_server_properties
        show_server_properties(self, self.server)
