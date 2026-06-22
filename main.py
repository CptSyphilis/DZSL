#!/usr/bin/env python3
import os
import sys

def _wayland_session():
    return (
        os.environ.get("XDG_SESSION_TYPE") == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
    )

def _configure_display():
    if os.environ.get("DZSL_USE_WAYLAND") == "1":
        return
    # On any Wayland desktop, force X11 (via XWayland). Overrides DE defaults like
    # GDK_BACKEND=wayland,x11 and avoids compositor disconnects on COSMIC, GNOME, KDE, etc.
    if _wayland_session() or os.environ.get("DZSL_USE_X11") == "1":
        os.environ["GDK_BACKEND"] = "x11"

_configure_display()

if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
    print("DZSL: no display found. Run from a graphical terminal on your desktop.", file=sys.stderr)
    sys.exit(1)

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk
import threading, subprocess, time, os

from config import load_cfg, save_json, load_json, FAVS_FILE, RECENT_FILE, is_steam_running
from css import CSS
from connect import Connector, launch_steam
from ui.servers import ServersView
from ui.favorites import ListView
from ui.add_server import AddServerView
from ui.mods import ModsView
from ui.settings import SettingsView
from ui.helpers import clear_box
from applog import setup_logging, get_logger

setup_logging()
log = get_logger("main")

class DZSL(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.dzsl.app")
        self.connect("activate", self.on_activate)
        self.cfg = load_cfg()
        self.favorites = load_json(FAVS_FILE)
        self.current_view = "servers"

    def on_activate(self, app):
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_title("DZSL")
        self.win.set_default_size(1280, 780)
        self.win.set_decorated(True)
        self.win.set_resizable(True)
        self.win.maximize()

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

        header_bar = Adw.HeaderBar()
        header_bar.add_css_class("app-header")
        header_bar.set_show_end_title_buttons(True)

        title = Gtk.Label(label="DZSL")
        title.add_css_class("app-title")
        header_bar.set_title_widget(title)

        self.header_btns = {}
        end_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        for key, label in [
            ("favorites", "favorites"),
            ("recent", "recent"),
            ("mods", "mods"),
            ("add", "add server"),
            ("settings", "settings"),
        ]:
            b = Gtk.Button(label=label)
            b.add_css_class("header-link")
            b.connect("clicked", lambda _, k=key: self.show_view(k))
            self.header_btns[key] = b
            end_box.append(b)
        header_bar.pack_end(end_box)

        home_btn = Gtk.Button(label="servers")
        home_btn.add_css_class("header-link")
        home_btn.connect("clicked", lambda _: self.show_view("servers"))
        self.header_btns["servers"] = home_btn
        header_bar.pack_start(home_btn)

        root.append(header_bar)

        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.panel.set_vexpand(True)
        root.append(self.panel)

        sbar = Gtk.Box()
        sbar.add_css_class("statusbar")
        self.status_lbl = Gtk.Label(label="Ready")
        self.status_lbl.add_css_class("status-txt")
        self.status_lbl.set_halign(Gtk.Align.START)
        sbar.append(self.status_lbl)
        root.append(sbar)

        self.win.set_content(root)
        self.win.present()

        self._steam_ready = False
        self._start_steam_enforcement()

    def _idle_statuses(self):
        return {"Ready", "Ready — start Steam to launch DayZ"}

    def _check_steam_running_async(self, callback):
        """Run is_steam_running() (several subprocess calls) off the GTK main
        thread so it can't stall the UI — fork/exec gets slow under CPU load,
        which is exactly when DayZ is also running."""
        def worker():
            running = is_steam_running()
            GLib.idle_add(callback, running)
        threading.Thread(target=worker, daemon=True).start()

    def _update_steam_status(self):
        self._check_steam_running_async(
            lambda running: self.set_status(
                "Ready" if running else "Ready — start Steam to launch DayZ"
            )
        )

    def _poll_steam_status(self):
        current = self.status_lbl.get_text()
        if current in self._idle_statuses():
            self._update_steam_status()
        return True

    def _start_steam_enforcement(self):
        """On app launch, ALWAYS check if Steam is running. Block the app until it is."""
        self._check_steam_running_async(self._on_initial_steam_check)

    def _on_initial_steam_check(self, running):
        if running:
            self._steam_ready = True
            self.set_status("Ready")
            self.show_view(self.current_view)
            GLib.timeout_add_seconds(5, self._poll_steam_status)
            return

        # Steam not running — do not let app "work"
        self.set_status("Steam is required to use DZSL. Starting Steam...")
        launch_steam()
        self._show_steam_wait_screen()
        self._recheck_source = GLib.timeout_add_seconds(2, self._recheck_tick)

    def _recheck_tick(self):
        self._check_steam_running_async(self._on_recheck_result)
        return True

    def _on_recheck_result(self, running):
        if running:
            self._steam_ready = True
            self.set_status("Ready")
            self._hide_steam_wait_screen()
            self.show_view(self.current_view)
            if getattr(self, "_recheck_source", None):
                GLib.source_remove(self._recheck_source)
                self._recheck_source = None
            GLib.timeout_add_seconds(5, self._poll_steam_status)
        else:
            self.set_status("Waiting for Steam to start...")

        GLib.timeout_add_seconds(2, _recheck)

    def _show_steam_wait_screen(self):
        self.clear_panel()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        vbox.set_valign(Gtk.Align.CENTER)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_margin_top(80)
        vbox.set_margin_bottom(80)

        title = Gtk.Label(label="Steam Required")
        title.add_css_class("app-title")
        vbox.append(title)

        msg = Gtk.Label(
            label="DZSL cannot be used unless Steam is running.\n"
                  "Steam has been launched automatically.\n"
                  "Please wait for Steam to start, or start it manually."
        )
        msg.add_css_class("empty")
        msg.set_justify(Gtk.Justification.CENTER)
        vbox.append(msg)

        spinner = Gtk.Spinner()
        spinner.start()
        vbox.append(spinner)

        launch_btn = Gtk.Button(label="Launch Steam")
        launch_btn.connect("clicked", lambda _: launch_steam())
        vbox.append(launch_btn)

        check_btn = Gtk.Button(label="Check Again")
        check_btn.connect("clicked", lambda _: self._manual_steam_check())
        vbox.append(check_btn)

        self.panel.append(vbox)

        # Disable header navigation while waiting for Steam
        for b in self.header_btns.values():
            b.set_sensitive(False)

    def _hide_steam_wait_screen(self):
        for b in self.header_btns.values():
            b.set_sensitive(True)
        self.clear_panel()

    def _manual_steam_check(self):
        if is_steam_running():
            self._steam_ready = True
            self.set_status("Ready")
            self._hide_steam_wait_screen()
            self.show_view(self.current_view)
        else:
            self.set_status("Steam still not detected — launching...")
            launch_steam()

    def set_status(self, msg):
        GLib.idle_add(self.status_lbl.set_text, msg)

    def clear_panel(self):
        clear_box(self.panel)

    def show_view(self, view):
        if not getattr(self, "_steam_ready", False) and not is_steam_running():
            self._show_steam_wait_screen()
            return
        log.info("View switched to %s", view)
        self.current_view = view
        self.clear_panel()

        if view == "favorites":
            ListView(self.panel, self.favorites, "No saved servers yet.\nUse the server browser or Add Server.", self.favorites, self.connector.connect, self.toggle_fav, self.connector.load_mods, self.set_status).build()
        elif view == "recent":
            ListView(self.panel, load_json(RECENT_FILE), "No recently joined servers.", self.favorites, self.connector.connect, self.toggle_fav, self.connector.load_mods, self.set_status).build()
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

        idx = None
        for i, f in enumerate(self.favorites):
            f_ip   = f.get("ip") or f.get("endpoint", {}).get("ip")
            f_port = f.get("port") or f.get("gamePort") or f.get("gameport")
            if f_ip == ip and f_port == port:
                idx = i
                break

        if idx is not None:
            self.favorites.pop(idx)
            if btn:
                btn.set_label("☆")
                btn.remove_css_class("fav-star")
                btn.add_css_class("fav-star-empty")
            self.set_status(f"Removed {server.get('name', ip)}")
        else:
            self.favorites.append(server)
            if btn:
                btn.set_label("★")
                btn.remove_css_class("fav-star-empty")
                btn.add_css_class("fav-star")
            self.set_status(f"Saved {server.get('name', ip)}")

        save_json(FAVS_FILE, self.favorites)

if __name__ == "__main__":
    DZSL().run()
