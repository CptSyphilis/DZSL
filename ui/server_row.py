import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gdk, GLib, Adw, Graphene

def copy_text(text):
    Gdk.Display.get_default().get_clipboard().set(
        Gdk.ContentProvider.new_for_value(text))

def dismiss_popover(popover):
    if not popover:
        return
    popover.popdown()
    popover.unparent()

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
    def __init__(self, server, on_connect, on_fav, is_fav=True, on_load_mods=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add_css_class("table-row")
        self.server = server
        self.on_connect = on_connect
        self.on_fav = on_fav
        self.on_load_mods = on_load_mods or (lambda s: None)

        ip = server.get("ip") or server.get("endpoint", {}).get("ip", "")
        port = server.get("port") or server.get("gamePort") or 2302
        mods = server.get("mods", [])
        fp = server.get("firstPersonOnly") or server.get("firstperson", False)
        pw = server.get("password") or server.get("hasPassword", False)
        be = server.get("battlEye", server.get("battleye", True))
        pl = server.get("players", 0)
        mxp = server.get("maxPlayers", server.get("maxplayers", 0))
        ping = server.get("ping")

        # Fav star
        fb = Gtk.Button(label="*" if is_fav else "o")
        fb.add_css_class("fav-star" if is_fav else "fav-star-empty")
        fb.set_size_request(40, -1)
        fb.connect("clicked", lambda b: on_fav(server, b))
        self.append(fb)

        # Name + details
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.set_hexpand(True)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nl = Gtk.Label(label=server.get("name", "Unknown"))
        nl.add_css_class("srv-name")
        nl.set_halign(Gtk.Align.START)
        nl.set_ellipsize(3)
        top.append(nl)

        if pw:
            lock = Gtk.Label(label="[LOCK]")
            lock.add_css_class("tag")
            lock.add_css_class("tag-pass")
            top.append(lock)
        if not be:
            nobe = Gtk.Label(label="NO BE")
            nobe.add_css_class("tag")
            nobe.add_css_class("tag-van")
            top.append(nobe)

        info.append(top)

        bottom = Gtk.Label(label=f"{ip}:{port}" + (f" | {len(mods)} mods" if mods else ""))
        bottom.add_css_class("srv-detail")
        bottom.set_halign(Gtk.Align.START)
        info.append(bottom)
        self.append(info)

        # Map, Players, Ping, Join
        map_lbl = Gtk.Label(label=server.get("map", "?"))
        map_lbl.add_css_class("srv-detail")
        map_lbl.set_size_request(120, -1)
        map_lbl.set_halign(Gtk.Align.CENTER)
        self.append(map_lbl)

        fp_tag = " 1PP" if fp else ""
        pl_lbl = Gtk.Label(label=f"{pl}/{mxp}{fp_tag}")
        pl_lbl.add_css_class("srv-players")
        pl_lbl.set_size_request(90, -1)
        pl_lbl.set_halign(Gtk.Align.CENTER)
        self.append(pl_lbl)

        ping_txt = f"{ping}" if ping else "-"
        ping_cls = "ping-good" if (ping and ping < 80) else "ping-ok" if (ping and ping < 150) else "ping-bad"
        ping_lbl = Gtk.Label(label=ping_txt)
        ping_lbl.add_css_class(ping_cls)
        ping_lbl.set_size_request(70, -1)
        ping_lbl.set_halign(Gtk.Align.CENTER)
        self.append(ping_lbl)

        cb = Gtk.Button(label="JOIN")
        cb.add_css_class("btn-connect")
        cb.set_size_request(80, -1)
        cb.connect("clicked", lambda b: on_connect(server))
        self.append(cb)

        # Right-click
        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)
        gesture.connect("pressed", self._on_right_click)
        self.add_controller(gesture)

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

    def _copy_ip(self):
        ip = self.server.get("ip") or self.server.get("endpoint", {}).get("ip", "")
        port = self.server.get("port") or self.server.get("gamePort", 2302)
        copy_text(f"{ip}:{port}")

    def _show_properties(self):
        s = self.server
        ip = s.get("ip") or s.get("endpoint", {}).get("ip", "?")
        port = s.get("port") or s.get("gamePort") or 2302
        mods = s.get("mods", [])
        mod_lines = "\n".join(
            f"  • {m.get('name', m.get('steamWorkshopId', '?'))}" for m in mods[:20]
        )
        if len(mods) > 20:
            mod_lines += f"\n  … and {len(mods) - 20} more"
        fp = "Yes" if s.get("firstPersonOnly") or s.get("firstperson") else "No"
        pw = "Yes" if s.get("password") or s.get("hasPassword") else "No"
        be = "On" if s.get("battlEye", s.get("battleye", True)) else "Off"
        info = (
            f"Name: {s.get('name', 'Unknown')}\n"
            f"Address: {ip}:{port}\n"
            f"Players: {s.get('players', 0)} / {s.get('maxPlayers', s.get('maxplayers', 0))}\n"
            f"Map: {s.get('map', 'Unknown')}\n"
            f"First Person Only: {fp}\n"
            f"Password: {pw}\n"
            f"BattlEye: {be}\n"
            f"Mods ({len(mods)}):\n{mod_lines or '  (none)'}"
        )
        d = Adw.MessageDialog(transient_for=self.get_root())
        d.set_heading("Server Properties")
        d.set_body(info)
        d.add_response("close", "Close")
        d.connect("response", lambda dlg, _: dlg.destroy())
        d.present()