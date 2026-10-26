import sys
from dzsl.bootstrap import configure_display
from dzsl.fonts import load_bundled_fonts

if not configure_display():
    raise SystemExit(1)

load_bundled_fonts()

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Graphene', '1.0')
from gi.repository import Gtk, Adw, GLib, Gdk, Gio, Graphene
import threading, subprocess, time

from dzsl.core.config import load_cfg, save_cfg, save_json, load_json, FAVS_FILE, RECENT_FILE, VERSION
from dzsl.core.constants import APPLICATION_ID
from dzsl.core.logging import setup_logging, get_logger
from dzsl.core.uri import parse_connect_uri
from dzsl.lifecycle import cancel_active_downloads
from dzsl.paths import ASSETS_DIR
from dzsl.services.connector import Connector
from dzsl.runtime import is_flatpak
from dzsl.services.updates import app_update_available, download_app_update, install_app_update_and_restart, outdated_mods, update_failed
from dzsl.steam.login import steam_login_account
from dzsl.ui.add_server import AddServerView
from dzsl.ui.add_server import _lookup
from dzsl.ui.branding import wordmark
from dzsl.ui.favorites import ListView
from dzsl.ui.helpers import clear_box
from dzsl.ui.mods import ModsView
from dzsl.ui.owner import OwnerView
from dzsl.ui.servers import ServersView
from dzsl.ui.settings import SettingsView
from dzsl.ui.splash import SplashWindow
from dzsl.ui.styles import CSS
from dzsl.ui.subscribe import launch_steam
from dzsl.ui.welcome import WelcomeView

setup_logging()
log = get_logger("main")
UPDATE_CHECK_SECONDS = 3600

class DZSL(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APPLICATION_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.connect("activate", self.on_activate)
        self.connect("command-line", self.on_command_line)
        self.cfg = load_cfg()
        self.favorites = load_json(FAVS_FILE)
        self.current_view = "welcome"
        self._pending_connect = None
        self._steam_ready = False
        self._steam_account = None

    def on_command_line(self, _app, command_line):
        for raw_arg in command_line.get_arguments()[1:]:
            arg = raw_arg.decode() if isinstance(raw_arg, bytes) else str(raw_arg)
            if not arg.lower().startswith("dzsl:"):
                continue
            try:
                self._pending_connect = parse_connect_uri(arg)
            except ValueError as exc:
                command_line.printerr(f"DZSL: {exc}\n")
                return 2
            break

        self.activate()
        return 0

    def on_activate(self, app):
        if getattr(self, "win", None):
            self.win.present()
            self._dispatch_pending_connect()
            return

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

        icon_path = ASSETS_DIR / "icon.png"
        if icon_path.exists():
            self.win.set_icon_name(APPLICATION_ID)
            gtk_icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            gtk_icon_theme.add_search_path(str(ASSETS_DIR))
            Gtk.Window.set_default_icon_name(APPLICATION_ID)

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

        header_bar.set_title_widget(wordmark(40))

        self.header_btns = {}
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        for key, label in [
            ("servers", "servers"),
            ("favorites", "favorites"),
            ("recent", "recent"),
            ("mods", "mods"),
            ("owner", "my server"),
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

        self.update_banner = Adw.Banner()
        self.update_banner.set_button_label("Update now")
        self.update_banner.connect("button-clicked", self._on_update_banner_clicked)
        root.append(self.update_banner)

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
        self._show_steam_wait_screen()
        self._set_navigation_enabled(False)

        self.splash = SplashWindow(self)
        self.splash.present()
        threading.Thread(target=self._splash_checks, daemon=True).start()

    def _splash_checks(self):
        started = time.monotonic()
        self.splash.set_step("Checking for DZSL updates…")
        update = None
        try:
            update = app_update_available()
        except Exception as exc:
            log.warning("DZSL update check failed: %s", exc)
        failed = is_flatpak() and update_failed()
        if update and is_flatpak() and not failed:
            if update["force"]:
                self._apply_update()
                return
            GLib.idle_add(
                self.splash.ask_update, update["version"],
                lambda: threading.Thread(target=self._apply_update, daemon=True).start(),
                lambda: threading.Thread(target=self._splash_rest, args=(started, update, False), daemon=True).start(),
            )
            return
        self._splash_rest(started, update, failed)

    def _apply_update(self):
        try:
            bundle = download_app_update(lambda f: self.splash.set_step(f"Downloading update… {int(f * 100)}%"))
        except Exception as exc:
            log.warning("DZSL update download failed: %s", exc)
            self._splash_rest(time.monotonic(), None, True)
            return
        self.splash.set_step("Installing update — DZSL will restart")
        install_app_update_and_restart(bundle)
        GLib.idle_add(self.quit)

    def _splash_rest(self, started, update, failed):
        self.splash.set_step("Checking Steam sign-in…")
        account = steam_login_account()

        self.splash.set_step("Checking for mod updates…")
        stale = []
        try:
            stale = outdated_mods(self.cfg)
        except Exception as exc:
            log.warning("Mod update check failed: %s", exc)

        remaining = 5 - (time.monotonic() - started)
        if remaining > 0:
            self.splash.set_step("Ready")
            time.sleep(remaining)
        GLib.idle_add(self._splash_done, account, stale, update, failed)

    def _splash_done(self, account, stale, update, failed):
        self.splash.destroy()
        self.splash = None
        self.win.present()
        self._on_initial_steam_check(account)
        if failed:
            self.set_status("DZSL update failed — download it from dayzlinux.com")
        elif update:
            self._offer_update(update)
        GLib.timeout_add_seconds(UPDATE_CHECK_SECONDS, self._update_check_tick)
        if stale:
            self._show_mod_update_dialog(stale)
        return False

    def _update_check_tick(self):
        if not self.update_banner.get_revealed():
            threading.Thread(target=self._background_update_check, daemon=True).start()
        return True

    def _background_update_check(self):
        try:
            update = app_update_available()
        except Exception as exc:
            log.warning("DZSL update check failed: %s", exc)
            return
        if update:
            GLib.idle_add(self._offer_update, update)

    def _manual_update_check(self, done):
        def worker():
            try:
                update = app_update_available()
            except Exception as exc:
                log.warning("DZSL update check failed: %s", exc)
                GLib.idle_add(done, "Couldn't check for updates. Check your connection.")
                return
            GLib.idle_add(finish, update)

        def finish(update):
            if update:
                self._offer_update(update)
                done(f"DZSL {update['version']} is available (you have v{VERSION})")
            else:
                done(f"You're up to date (v{VERSION})")
            return False

        threading.Thread(target=worker, daemon=True).start()

    def _offer_update(self, update):
        if not is_flatpak():
            self.set_status(f"DZSL {update['version']} is available (you have {VERSION})")
            return False
        self.update_banner.set_title(f"DZSL {update['version']} is ready")
        self.update_banner.set_button_label("Update now")
        self.update_banner.set_sensitive(True)
        self.update_banner.set_revealed(True)
        return False

    def _on_update_banner_clicked(self, banner):
        if getattr(self.connector, "_busy", False):
            banner.set_title("Finish connecting to the server first, then update")
            return
        banner.set_sensitive(False)
        banner.set_title("Downloading update…")
        threading.Thread(target=self._banner_update, daemon=True).start()

    def _banner_update(self):
        def progress(f):
            GLib.idle_add(self.update_banner.set_title, f"Downloading update… {int(f * 100)}%")
        try:
            bundle = download_app_update(progress)
        except Exception as exc:
            log.warning("DZSL update download failed: %s", exc)
            GLib.idle_add(self._banner_update_failed)
            return
        GLib.idle_add(self.update_banner.set_title, "Installing update — DZSL will restart")
        try:
            install_app_update_and_restart(bundle)
        except OSError as exc:
            log.warning("DZSL update install failed: %s", exc)
            GLib.idle_add(self._banner_update_failed)
            return
        GLib.idle_add(self.quit)

    def _banner_update_failed(self):
        self.update_banner.set_title("Update failed")
        self.update_banner.set_button_label("Try again")
        self.update_banner.set_sensitive(True)
        return False

    def _show_mod_update_dialog(self, stale):
        names = "\n".join(f"• {m['name']}" for m in stale[:12])
        if len(stale) > 12:
            names += f"\n… and {len(stale) - 12} more"
        dlg = Adw.MessageDialog(
            transient_for=self.win,
            heading=f"{len(stale)} mod{'s need' if len(stale) != 1 else ' needs'} updating",
            body=f"Newer Workshop versions exist for:\n\n{names}",
        )
        dlg.add_response("later", "Later")
        dlg.add_response("mods", "Open Mods")
        dlg.set_response_appearance("mods", Adw.ResponseAppearance.SUGGESTED)
        dlg.connect("response", self._on_mod_update_response)
        dlg.present()

    def _on_mod_update_response(self, _dlg, response):
        if response == "mods":
            self.show_view("mods")

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

    def _check_steam_login_async(self, callback):
        def worker():
            account = steam_login_account()
            GLib.idle_add(callback, account)
        threading.Thread(target=worker, daemon=True).start()

    def _update_steam_status(self):
        self._check_steam_login_async(
            self._on_steam_status
        )

    def _on_steam_status(self, account):
        if account:
            self._steam_ready = True
            self._steam_account = account
            self.set_status(f"Signed in to Steam as {account.display_name}")
            return
        self._steam_ready = False
        self._steam_account = None
        self._set_navigation_enabled(False)
        self._show_steam_wait_screen()
        self.set_status("Sign in to Steam to use DZSL.")
        if not getattr(self, "_recheck_source", None):
            launch_steam()
            self._recheck_source = GLib.timeout_add_seconds(2, self._recheck_tick)

    def _poll_steam_status(self):
        current = self.status_lbl.get_text()
        if current in self._idle_statuses() or current.startswith("Signed in to Steam as "):
            self._update_steam_status()
        return True

    def _on_initial_steam_check(self, account):
        if account:
            self._finish_steam_login(account)
            return

        self.set_status("Sign in to Steam to use DZSL.")
        launch_steam()
        self._show_steam_wait_screen()
        self._recheck_source = GLib.timeout_add_seconds(2, self._recheck_tick)

    def _recheck_tick(self):
        self._check_steam_login_async(self._on_recheck_result)
        return True

    def _on_recheck_result(self, account):
        if account:
            self._finish_steam_login(account)
        else:
            self.set_status("Waiting for Steam sign-in...")

    def _finish_steam_login(self, account):
        self._steam_ready = True
        self._steam_account = account
        self.set_status(f"Signed in to Steam as {account.display_name}")
        self._set_navigation_enabled(True)
        self._hide_steam_wait_screen()
        self.show_view(self.current_view)
        self._dispatch_pending_connect()
        if getattr(self, "_recheck_source", None):
            GLib.source_remove(self._recheck_source)
            self._recheck_source = None
        if not getattr(self, "_steam_poll_source", None):
            self._steam_poll_source = GLib.timeout_add_seconds(5, self._poll_steam_status)

    def _set_navigation_enabled(self, enabled):
        for button in getattr(self, "header_btns", {}).values():
            button.set_sensitive(enabled)
        if getattr(self, "back_btn", None):
            self.back_btn.set_sensitive(enabled)

    def _show_steam_wait_screen(self):
        self.clear_panel()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        vbox.set_valign(Gtk.Align.CENTER)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_margin_top(80)
        vbox.set_margin_bottom(80)

        title = Gtk.Label(label="Sign in to Steam")
        title.add_css_class("app-title")
        vbox.append(title)

        msg = Gtk.Label(
            label="DZSL requires an active Steam account.\n"
                  "Sign in through the Steam client, then return here.\n"
                  "The launcher will unlock automatically."
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

    def _hide_steam_wait_screen(self):
        self.clear_panel()

    def _manual_steam_check(self):
        self.set_status("Checking Steam sign-in...")
        self._check_steam_login_async(self._on_manual_steam_check)

    def _on_manual_steam_check(self, account):
        if account:
            self._finish_steam_login(account)
            return
        self.set_status("Steam is not signed in yet.")
        launch_steam()

    def _dispatch_pending_connect(self):
        if not self._pending_connect or not getattr(self, "_steam_ready", False):
            return
        if getattr(self.connector, "_busy", False):
            self.set_status("A connect operation is already running — link queued.")
            GLib.timeout_add_seconds(2, self._retry_pending_connect)
            return

        host, port = self._pending_connect
        self._pending_connect = None
        self.set_status(f"Loading server {host}:{port} from website…")
        threading.Thread(
            target=self._resolve_linked_server,
            args=(host, port),
            daemon=True,
        ).start()

    def _retry_pending_connect(self):
        self._dispatch_pending_connect()
        return bool(self._pending_connect)

    def _resolve_linked_server(self, host, port):
        server = {
            "ip": host,
            "port": port,
            "gamePort": port,
            "name": f"{host}:{port}",
            "mods": [],
        }
        try:
            server.update(_lookup(host, port))
        except (OSError, RuntimeError, ValueError) as exc:
            log.warning("Could not resolve website server link %s:%s: %s", host, port, exc)

        server["ip"] = host
        server.setdefault("port", port)
        server.setdefault("gamePort", port)
        server.setdefault("name", f"{host}:{port}")
        server.setdefault("mods", [])
        GLib.idle_add(self._connect_linked_server, server)

    def _connect_linked_server(self, server):
        if not self._steam_ready:
            self._show_steam_wait_screen()
            return False
        self.win.present()
        self.connector.connect(server)
        return False

    def set_status(self, msg):
        GLib.idle_add(self.status_lbl.set_text, msg)

    def clear_panel(self):
        clear_box(self.panel)

    def _show_top_view(self, view):
        self.show_view("welcome" if self.current_view == view else view)

    def show_view(self, view):
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
        elif view == "owner":
            OwnerView(self.panel, self.set_status, win=self.win, steam_account=self._steam_account).build()
        elif view == "settings":
            SettingsView(
                self.panel,
                self.cfg,
                self.set_status,
                lambda: self.show_view("settings"),
                self.set_downloading,
                lambda: self.show_view("favorites"),
                self._manual_update_check,
            ).build()

    def _open_add_server_dialog(self):
        dlg = Adw.Dialog()
        dlg.set_title("Add Server")
        dlg.set_content_width(420)
        dlg.set_content_height(380)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        def added():
            dlg.close()
            if self.current_view == "favorites":
                self.show_view("favorites")
        AddServerView(box, self.favorites, self.set_status, on_added=added).build()
        dlg.set_child(box)
        closing = [False]
        def watch(host):
            gesture = Gtk.GestureClick()
            gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            def on_press(g, _n, x, y):
                ok, bounds = box.compute_bounds(host)
                if ok and not bounds.contains_point(Graphene.Point().init(x, y)):
                    g.set_state(Gtk.EventSequenceState.CLAIMED)
                    if not closing[0]:
                        closing[0] = True
                        dlg.close()
            gesture.connect("pressed", on_press)
            host.add_controller(gesture)
            return gesture
        win_gesture = watch(self.win)
        watch(dlg)
        dlg.connect("closed", lambda _d: self.win.remove_controller(win_gesture))
        dlg.present(self.win)

    def _on_close_request(self, win):
        cancel_active_downloads(self)
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

def main():
    try:
        return DZSL().run(sys.argv)
    except KeyboardInterrupt:
        return 130
