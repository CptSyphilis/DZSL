import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


class ServerPromoteView:
    def __init__(self, panel, cfg, set_status):
        self.panel = panel
        self.cfg = cfg
        self.set_status = set_status

    def build(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_vexpand(True)
        outer.add_css_class("settings-group")

        title = Gtk.Label(label="PROMOTE SERVER")
        title.add_css_class("settings-title")
        title.set_halign(Gtk.Align.START)
        outer.append(title)

        placeholder = Gtk.Label(label="Server promotion is not implemented yet.")
        placeholder.add_css_class("empty")
        placeholder.set_halign(Gtk.Align.START)
        outer.append(placeholder)

        self.panel.append(outer)

    def submit_listing(self, server):
        raise NotImplementedError("Submit a server to the public listing")

    def bump_listing(self, server):
        raise NotImplementedError("Bump an existing listing for visibility")

    def listing_status(self, server):
        raise NotImplementedError("Fetch current promotion/listing status")
