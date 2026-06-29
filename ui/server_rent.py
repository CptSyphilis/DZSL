import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


class ServerRentView:
    def __init__(self, panel, cfg, set_status):
        self.panel = panel
        self.cfg = cfg
        self.set_status = set_status

    def build(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_vexpand(True)
        outer.add_css_class("settings-group")

        title = Gtk.Label(label="RENT SERVER")
        title.add_css_class("settings-title")
        title.set_halign(Gtk.Align.START)
        outer.append(title)

        placeholder = Gtk.Label(label="Server renting is not implemented yet.")
        placeholder.add_css_class("empty")
        placeholder.set_halign(Gtk.Align.START)
        outer.append(placeholder)

        self.panel.append(outer)

    def list_offers(self):
        raise NotImplementedError("Fetch available rental plans from the provider backend")

    def order_server(self, plan):
        raise NotImplementedError("Place a rental order with the provider backend")

    def manage_server(self, server_id):
        raise NotImplementedError("Open management controls for a rented server")

    def cancel_server(self, server_id):
        raise NotImplementedError("Cancel an active rental")
