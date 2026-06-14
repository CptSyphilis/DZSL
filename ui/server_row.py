import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

def ping_cls(p):
    if p is None: return "ping-bad"
    if p < 80:  return "ping-good"
    if p < 150: return "ping-ok"
    return "ping-bad"

class ServerRow(Gtk.Box):
    def __init__(self, s, on_connect, on_fav, is_fav):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.add_css_class("server-row")

        # Info
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        info.set_hexpand(True)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nl = Gtk.Label(label=s.get("name", "Unknown"))
        nl.add_css_class("srv-name"); nl.set_halign(Gtk.Align.START); nl.set_ellipsize(3)
        top.append(nl)

        is_modded = bool(s.get("mods")) or s.get("modded", False)
        if is_modded:
            t = Gtk.Label(label="MODDED"); t.add_css_class("tag"); t.add_css_class("tag-mod"); top.append(t)
        else:
            t = Gtk.Label(label="VANILLA"); t.add_css_class("tag"); t.add_css_class("tag-van"); top.append(t)
        if s.get("firstPersonOnly") or s.get("firstperson"):
            t2 = Gtk.Label(label="1PP"); t2.add_css_class("tag"); t2.add_css_class("tag-1pp"); top.append(t2)
        if s.get("password") or s.get("hasPassword"):
            t3 = Gtk.Label(label="🔒"); t3.add_css_class("tag"); t3.add_css_class("tag-pass"); top.append(t3)
        if not s.get("battlEye", s.get("battleye", True)):
            t4 = Gtk.Label(label="NO BE"); t4.add_css_class("tag"); t4.add_css_class("tag-van"); top.append(t4)
        info.append(top)

        ip   = s.get("ip") or s.get("endpoint", {}).get("ip", "")
        port = s.get("port") or s.get("gamePort") or s.get("endpoint", {}).get("port", "")
        det  = Gtk.Label(label=f"{s.get('map', '?')}  ·  {ip}:{port}")
        det.add_css_class("srv-detail"); det.set_halign(Gtk.Align.START)
        info.append(det)
        self.append(info)

        # Stats
        stats = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        stats.set_halign(Gtk.Align.END); stats.set_valign(Gtk.Align.CENTER)

        maxp = s.get("maxPlayers", s.get("maxplayers", 0))
        pl   = Gtk.Label(label=f"{s.get('players', 0)}/{maxp}")
        pl.add_css_class("srv-players"); stats.append(pl)

        ping = s.get("ping")
        mods_count = len(s.get("mods", []))
        pgl  = Gtk.Label(label=f"{ping}ms" if ping else (f"{mods_count} mods" if mods_count else "vanilla"))
        pgl.add_css_class(ping_cls(ping) if ping else "srv-detail")
        stats.append(pgl)
        self.append(stats)

        # Buttons
        btns = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        btns.set_valign(Gtk.Align.CENTER)
        cb = Gtk.Button(label="CONNECT"); cb.add_css_class("btn-connect")
        cb.connect("clicked", lambda b: on_connect(s)); btns.append(cb)
        fb = Gtk.Button(label="SAVED" if is_fav else "SAVE")
        fb.add_css_class("btn-ghost")
        fb.connect("clicked", lambda b: on_fav(s, fb)); btns.append(fb)
        self.append(btns)
