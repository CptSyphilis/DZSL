#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk
import threading, subprocess, time

from config import load_cfg, save_json, load_json, FAVS_FILE, RECENT_FILE
from css import CSS
from connect import Connector
from ui.servers import ServersView
from ui.favorites import ListView
from ui.add_server import AddServerView
from ui.mods import ModsView
from ui.settings import SettingsView

class DZSL(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.dzsl.app")
        self.connect("activate", self.on_activate)
        self.cfg = load_cfg()
        self.favorites = load_json(FAVS_FILE)

    def on_activate(self, app):
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_title("DZSL")
        self.win.set_default_size(1280, 780)
        self.win.set_decorated(True)
        self.win.set_resizable(True)
        self.win.maximize()

        # Set app icon
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "assets", "icon.png")
        if os.path.exists(icon_path):
            self.win.set_icon_name("dzsl")
            gtk_icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            gtk_icon_theme.add_search_path(os.path.join(script_dir, "assets"))
            Gtk.Window.set_default_icon_name("dzsl")

        css = Gtk.CssProvider()
        css.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.connector = Connector(self.cfg, self.win, self.set_status)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Native header bar
        header_bar = Adw.HeaderBar()
        header_bar.add_css_class("app-header")
        header_bar.set_show_end_title_buttons(True)

        tbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        t = Gtk.Label(label="DZSL"); t.add_css_class("app-title")
        s = Gtk.Label(label="DAYZ SERVER LIST FOR LINUX"); s.add_css_class("app-sub")
        tbox.append(t); tbox.append(s)
        header_bar.set_title_widget(tbox)

        root.append(header_bar)

        # Body
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        body.set_vexpand(True)

        # Sidebar
        sb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sb.add_css_class("sidebar")

        self.nav_btns = {}

        def nav_lbl(txt):
            l = Gtk.Label(label=txt); l.add_css_class("nav-section"); l.set_halign(Gtk.Align.START); sb.append(l)

        def nav_btn(key, label):
            b = Gtk.Button(label=label); b.add_css_class("nav-btn")
            b.connect("clicked", lambda _: self.show_view(key))
            self.nav_btns[key] = b; sb.append(b)

        nav_lbl("LIBRARY")
        nav_btn("favorites", "Favorites")
        nav_btn("recent",    "Recent")
        nav_lbl("BROWSE")
        nav_btn("servers",   "All Servers")
        nav_btn("add",       "+ Add Server")
        nav_lbl("MANAGE")
        nav_btn("mods",      "Mods")
        nav_btn("settings",  "Settings")

        body.append(sb)

        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.panel.set_hexpand(True)
        body.append(self.panel)
        root.append(body)

        # Status bar
        sbar = Gtk.Box(); sbar.add_css_class("statusbar")
        self.status_lbl = Gtk.Label(label="Ready")
        self.status_lbl.add_css_class("status-txt"); self.status_lbl.set_halign(Gtk.Align.START)
        sbar.append(self.status_lbl); root.append(sbar)

        self.win.set_content(root)
        self.win.present()
        self.show_view("favorites")
        threading.Thread(target=self._startup_steam_check, daemon=True).start()

    def set_status(self, msg):
        GLib.idle_add(self.status_lbl.set_text, msg)

    def clear_panel(self):
        c = self.panel.get_first_child()
        while c:
            n = c.get_next_sibling()
            self.panel.remove(c)
            c = n

    def show_view(self, view):
        self.clear_panel()
        for k, b in self.nav_btns.items():
            if k == view:
                b.add_css_class("active")
            else:
                b.remove_css_class("active")

        if view == "favorites":
            ListView(self.panel, self.favorites, "No saved servers yet.\nUse Browse or Add Server.", self.favorites, self.connector.connect, self.toggle_fav, self.connector.load_mods).build()
        elif view == "recent":
            ListView(self.panel, load_json(RECENT_FILE), "No recently joined servers.", self.favorites, self.connector.connect, self.toggle_fav, self.connector.load_mods).build()
        elif view == "servers":
            ServersView(self.panel, self.cfg, self.favorites, self.connector.connect, self.toggle_fav, self.set_status, self.connector.load_mods).build()
        elif view == "add":
            AddServerView(self.panel, self.favorites, self.set_status).build()
        elif view == "mods":
            ModsView(self.panel, self.cfg, self.set_status).build()
        elif view == "settings":
            SettingsView(self.panel, self.cfg, self.set_status, lambda: self.show_view("settings")).build()

    def toggle_fav(self, server, btn=None):
        ip   = server.get("ip") or server.get("endpoint", {}).get("ip")
        port = server.get("port") or server.get("gamePort") or server.get("gameport")

        # Find existing favorite (more reliable)
        idx = None
        for i, f in enumerate(self.favorites):
            f_ip   = f.get("ip") or f.get("endpoint", {}).get("ip")
            f_port = f.get("port") or f.get("gamePort") or f.get("gameport")
            if f_ip == ip and f_port == port:
                idx = i
                break

        if idx is not None:
            # Remove
            self.favorites.pop(idx)
            if btn:
                btn.set_label("SAVE")
            self.set_status(f"Removed {server.get('name', ip)}")
        else:
            # Add
            self.favorites.append(server)
            if btn:
                btn.set_label("SAVED")
            self.set_status(f"Saved {server.get('name', ip)}")

        save_json(FAVS_FILE, self.favorites)

    def _startup_steam_check(self):
        is_running = subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0
        if is_running:
            self.set_status("Steam is running OK")
        else:
            GLib.idle_add(self._prompt_steam)

    def _prompt_steam(self):
        d = Adw.MessageDialog(transient_for=self.win)
        d.set_heading("Steam is not running")
        d.set_body("DZSL needs Steam to launch DayZ. Start Steam now?")
        d.add_response("cancel", "Not now")
        d.add_response("start", "Start Steam")
        d.set_response_appearance("start", Adw.ResponseAppearance.SUGGESTED)
        def on_r(_, r):
            if r == "start":
                self.set_status("Starting Steam…")
                subprocess.Popen(["steam"])
                def wait():
                    for _ in range(20):
                        time.sleep(2)
                        if subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0:
                            self.set_status("Steam is running OK"); return
                    self.set_status("Steam may still be loading…")
                threading.Thread(target=wait, daemon=True).start()
            else:
                self.set_status("Steam not running — connect may fail")
        d.connect("response", on_r); d.present()

if __name__ == "__main__":
    DZSL().run()