import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from config import load_json, save_json


class ModpacksView:
    def __init__(self, panel, cfg, set_status, install_mods_cb=None):
        self.panel = panel
        self.cfg = cfg
        self.set_status = set_status
        self.install_mods_cb = install_mods_cb
        self.packs = []

    def build(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_vexpand(True)
        outer.add_css_class("settings-group")

        title = Gtk.Label(label="MODPACKS")
        title.add_css_class("settings-title")
        title.set_halign(Gtk.Align.START)
        outer.append(title)

        placeholder = Gtk.Label(label="Modpack management is not implemented yet.")
        placeholder.add_css_class("empty")
        placeholder.set_halign(Gtk.Align.START)
        outer.append(placeholder)

        self.panel.append(outer)

    def load_packs(self):
        raise NotImplementedError("Load saved modpacks from disk")

    def save_packs(self):
        raise NotImplementedError("Persist modpacks to disk")

    def create_pack(self, name, mod_ids):
        raise NotImplementedError("Create a named pack from a set of Workshop mod IDs")

    def delete_pack(self, name):
        raise NotImplementedError("Remove a saved pack")

    def apply_pack(self, name):
        raise NotImplementedError("Subscribe/install every mod in the pack")

    def export_pack(self, name, path):
        raise NotImplementedError("Write a pack to a shareable file")

    def import_pack(self, path):
        raise NotImplementedError("Read a pack from a shared file")
