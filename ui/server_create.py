import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


class ServerCreateView:
    def __init__(self, panel, cfg, set_status):
        self.panel = panel
        self.cfg = cfg
        self.set_status = set_status

    def build(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_vexpand(True)
        outer.add_css_class("settings-group")

        title = Gtk.Label(label="CREATE SERVER")
        title.add_css_class("settings-title")
        title.set_halign(Gtk.Align.START)
        outer.append(title)

        placeholder = Gtk.Label(label="Local server creation is not implemented yet.")
        placeholder.add_css_class("empty")
        placeholder.set_halign(Gtk.Align.START)
        outer.append(placeholder)

        self.panel.append(outer)

    def install_server(self):
        raise NotImplementedError("Install the DayZ dedicated server app (AppID 223350) via Steam")

    def generate_config(self, settings):
        raise NotImplementedError("Write serverDZ.cfg from the chosen settings")

    def attach_mods(self, mod_ids):
        raise NotImplementedError("Link installed Workshop mods into the server mod path")

    def start_server(self):
        raise NotImplementedError("Launch the dedicated server process")

    def stop_server(self):
        raise NotImplementedError("Stop the running dedicated server process")
