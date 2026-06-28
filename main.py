import atexit
import os
import signal
import sys

def _wayland_session():
    return (
        os.environ.get("XDG_SESSION_TYPE") == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
    )

def _configure_display():
    if os.environ.get("DZSL_USE_WAYLAND") == "1":
        return
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

from config import load_cfg, save_cfg, save_json, load_json, FAVS_FILE, RECENT_FILE, is_steam_running, find_corrupt_mods, VERSION
from css import CSS
from connect import Connector
from ui.subscribe import launch_steam
from ui.servers import ServersView
from ui.favorites import ListView
from ui.add_server import AddServerView
from ui.mods import ModsView
from ui.settings import SettingsView
from ui.welcome import WelcomeView
from ui.helpers import clear_box
from applog import setup_logging, get_logger

setup_logging()
log = get_logger("main")

_app_instance = None

def _kill_downloads():
    try:
        if _app_instance is not None:
            _app_instance.connector.downloads.kill_all_active()
    except Exception:
        pass

atexit.register(_kill_downloads)

def _on_terminating_signal(signum, _frame):
    log.info("Received signal %s — stopping active downloads", signum)
    _kill_downloads()
    sys.exit(0)

signal.signal(signal.SIGTERM, _on_terminating_signal)
signal.signal(signal.SIGINT, _on_terminating_signal)


class DZSL(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.dzsl.app")
        self.connect("activate", self.on_activate)
        self.cfg = load_cfg()
        self.favorites = load_json(FAVS_FILE)
        self.current_view = "welcome"

    def on_activate(self, app):
        global _app_instance
        _app_instance = self
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_title("DZSL")
        w = self.cfg.get("window_width", 1280)
        h = self.cfg.get("window_height", 780)
        self.win.set_default_size(w, h)
        self.win.set_decorated(True)
        self.win.set_resizable(True)
        if self.cfg.get("window_maximized", True):
            self.win.maximize()
        self.win.connect("close-request", self._on_close_request)

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

        self.connector = Connector(self.cfg, self.win, self.set_status, self.set_downloading)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        header_bar = Adw.HeaderBar()
        header_bar.add_css_class("app-header")
        header_bar.set_show_end_title_buttons(True)

        title = Gtk.Label(label="DZSL")
        title.add_css_class("app-title")
        header_bar.set_title_widget(title)

        self.header_btns = {}
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        for key, label in [
            ("servers", "servers"),
            ("favorites", "favorites"),
            ("recent", "recent"),
            ("mods", "mods"),
            ("settings", "settings"),
        ]:
            b = Gtk.Button(label=label)
            b.add_css_class("header-link")
            b.connect("clicked", lambda _, k=key: self._show_top_view(k))
            self.header_btns[key] = b
            nav_box.append(b)

        header_bar.pack_end(nav_box)

        self.back_btn = Gtk.Button()
        self.back_btn.set_icon_name("go-previous-symbolic")
        self.back_btn.add_css_class("header-back-btn")
        self.back_btn.set_tooltip_text("Back")
        self.back_btn.connect("clicked", lambda _: self.show_view("welcome"))
        self.back_btn.set_visible(False)
        header_bar.pack_start(self.back_btn)

        root.append(header_bar)

        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.panel.set_vexpand(True)
        root.append(self.panel)

        sbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        sbar.add_css_class("statusbar")

        self.status_lbl = Gtk.Label(label="Ready")
        self.status_lbl.add_css_class("status-txt")
        self.status_lbl.set_halign(Gtk.Align.START)
        self.status_lbl.set_hexpand(True)
        sbar.append(self.status_lbl)

        self.dl_info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.dl_info_box.add_css_class("statusbar-dl")
        self.dl_info_box.set_visible(False)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.add_css_class("statusbar-sep")
        self.dl_info_box.append(sep)

        self.dl_bar = Gtk.ProgressBar()
        self.dl_bar.add_css_class("statusbar-dl-bar")
        self.dl_bar.set_size_request(120, -1)
        self.dl_bar.set_valign(Gtk.Align.CENTER)
        self.dl_info_box.append(self.dl_bar)

        self.dl_speed_lbl = Gtk.Label()
        self.dl_speed_lbl.add_css_class("status-dl-speed")
        self.dl_info_box.append(self.dl_speed_lbl)

        self.dl_phase_lbl = Gtk.Label()
        self.dl_phase_lbl.add_css_class("status-txt")
        self.dl_phase_lbl.set_max_width_chars(30)
        self.dl_phase_lbl.set_ellipsize(3)
        self.dl_info_box.append(self.dl_phase_lbl)

        self.dl_size_lbl = Gtk.Label()
        self.dl_size_lbl.add_css_class("status-txt")
        self.dl_info_box.append(self.dl_size_lbl)

        self.dl_pct_lbl = Gtk.Label()
        self.dl_pct_lbl.add_css_class("status-dl-pct")
        self.dl_info_box.append(self.dl_pct_lbl)

        self.dl_arrow_btn = Gtk.Button(label="▲")
        self.dl_arrow_btn.add_css_class("statusbar-dl-arrow")
        self.dl_arrow_btn.connect("clicked", self._toggle_download_popover)
        self.dl_info_box.append(self.dl_arrow_btn)

        sbar.append(self.dl_info_box)
        root.append(sbar)

        self.win.set_content(root)
        self.win.connect("realize", self._on_window_realize)
        self.win.present()

        self._steam_ready = False
        self._start_steam_enforcement()

    def _on_window_realize(self, win):
        surface = win.get_surface()
        if surface:
            surface.connect("notify::state", self._on_window_state_changed)

    def _on_window_state_changed(self, surface, _pspec):
        minimized = bool(surface.get_state() & Gdk.ToplevelState.MINIMIZED)
        if minimized:
            self._was_minimized = True
        elif getattr(self, "_was_minimized", False):
            self._was_minimized = False
            GLib.idle_add(self._fixup_size_after_restore)

    def _fixup_size_after_restore(self):
        w, h = self.win.get_width(), self.win.get_height()
        if w and h:
            self.win.set_default_size(w - 1, h)
            GLib.idle_add(lambda: self.win.set_default_size(w, h))
        return False

    def _idle_statuses(self):
        return {"Ready", "Ready — start Steam to launch DayZ"}

    def _check_steam_running_async(self, callback):
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
            threading.Thread(target=self._scan_corrupt_mods, daemon=True).start()
            return

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
            threading.Thread(target=self._scan_corrupt_mods, daemon=True).start()
        else:
            self.set_status("Waiting for Steam to start...")

    def _scan_corrupt_mods(self):
        import shutil
        corrupt = find_corrupt_mods(self.cfg)
        if not corrupt:
            return
        for path in corrupt:
            log.warning("Removing corrupt mod directory: %s", path)
            try:
                shutil.rmtree(path)
            except OSError as e:
                log.error("Could not remove %s: %s", path, e)
        GLib.idle_add(self.set_status, f"Cleaned up {len(corrupt)} corrupt mod folder(s) on startup")

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

    def _show_top_view(self, view):
        self.show_view("welcome" if self.current_view == view else view)

    def show_view(self, view):
        if not getattr(self, "_steam_ready", False) and not is_steam_running():
            self._show_steam_wait_screen()
            return
        log.info("View switched to %s", view)
        self.current_view = view
        self.back_btn.set_visible(view != "welcome")
        self.clear_panel()
        for k, b in self.header_btns.items():
            if k == view:
                b.add_css_class("active")
            else:
                b.remove_css_class("active")

        if view == "welcome":
            self._build_welcome()
        elif view == "favorites":
            ListView(self.panel, self.favorites, "No saved servers yet.", self.favorites, self.connector.connect, self.toggle_fav, self.connector.load_mods, self.set_status,
                     add_server_cb=lambda: self._open_add_server_dialog()).build()
        elif view == "recent":
            ListView(self.panel, load_json(RECENT_FILE), "No recently joined servers.", self.favorites, self.connector.connect, self.toggle_fav, self.connector.load_mods, self.set_status).build()
        elif view == "servers":
            ServersView(self.panel, self.cfg, self.favorites, self.connector.connect, self.toggle_fav, self.set_status, self.connector.load_mods).build()
        elif view == "mods":
            ModsView(self.panel, self.cfg, self.set_status, self.set_downloading).build()
        elif view == "settings":
            SettingsView(
                self.panel,
                self.cfg,
                self.set_status,
                lambda: self.show_view("settings"),
                self.set_downloading,
                lambda: self.show_view("favorites"),
            ).build()

    def _open_add_server_dialog(self):
        dlg = Adw.Dialog()
        dlg.set_title("Add Server")
        dlg.set_content_width(420)
        dlg.set_content_height(380)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        AddServerView(box, self.favorites, self.set_status).build()
        dlg.set_child(box)
        dlg.present(self.win)

    def _on_close_request(self, win):
        _kill_downloads()
        maximized = win.is_maximized()
        self.cfg["window_maximized"] = maximized
        if not maximized:
            self.cfg["window_width"]  = win.get_width()
            self.cfg["window_height"] = win.get_height()
        save_cfg(self.cfg)
        return False

    def set_downloading(self, active, progress=None):
        def update():
            old = getattr(self, "_active_progress", None)
            if old is not None and old is not progress:
                old.popover.popdown()
                if old.popover.get_parent():
                    old.popover.unparent()
            self._active_progress = progress
            self._dl_poll_active = active
            if active:
                progress.popover.set_parent(self.dl_arrow_btn)
                progress.popover.popup()
                GLib.timeout_add(500, self._poll_dl_status)
            else:
                self.dl_info_box.set_visible(False)
        GLib.idle_add(update)

    def _poll_dl_status(self):
        if not getattr(self, "_dl_poll_active", False):
            return False
        p = getattr(self, "_active_progress", None)
        if not p or p._closed:
            self.dl_info_box.set_visible(False)
            return False
        speed = p.speed_label.get_text()
        frac  = getattr(p, "current_fraction", 0.0)
        mod_name = getattr(p, "current_mod_name", "")
        size_txt = getattr(p, "current_size_text", "")
        self.dl_bar.set_fraction(frac)
        self.dl_speed_lbl.set_text(f"↓ {speed}" if speed and speed != "—" else "")
        self.dl_speed_lbl.set_visible(bool(speed and speed != "—"))
        self.dl_phase_lbl.set_text(mod_name or "Downloading…")
        self.dl_size_lbl.set_text(size_txt)
        self.dl_pct_lbl.set_text(f"{int(frac * 100)}%" if mod_name else "")
        self.dl_info_box.set_visible(True)
        return True

    def _toggle_download_popover(self, *_):
        p = getattr(self, "_active_progress", None)
        if not p or p._closed:
            return
        if p.popover.get_visible():
            p.popover.popdown()
        else:
            p.popover.popup()

    def _build_welcome(self):
        WelcomeView(
            self.panel,
            self.show_view,
            self.connector.connect,
            self.favorites,
        ).build()

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
