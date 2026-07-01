import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib
from dzsl.core.config import DEFAULT_CFG, save_cfg, workshop_dir
from dzsl.ui.helpers import forward_steam_uri, unsubscribe_mod_ids
from dzsl.ui.workshop_actions import WorkshopActionRunner
import threading

class SettingsView:
    def __init__(self, panel, cfg, set_status, reload_cb, set_downloading=None, saved_cb=None):
        self.panel      = panel
        self.cfg        = cfg
        self.set_status = set_status
        self.reload_cb  = reload_cb
        self.set_downloading = set_downloading or (lambda *_: None)
        self.saved_cb = saved_cb or (lambda: None)
        self.workshop = WorkshopActionRunner(cfg, set_status, self.set_downloading)

    def build(self):
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(24)
        outer.set_margin_bottom(24)
        outer.set_margin_start(40)
        outer.set_margin_end(40)

        def card(title):
            wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            wrapper.add_css_class("settings-card")
            wrapper.set_margin_bottom(20)

            hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            hdr.add_css_class("settings-card-header")
            lbl = Gtk.Label(label=title)
            lbl.add_css_class("settings-card-title")
            lbl.set_halign(Gtk.Align.START)
            hdr.append(lbl)
            wrapper.append(hdr)

            body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            body.add_css_class("settings-card-body")
            wrapper.append(body)
            outer.append(wrapper)
            return body

        def field_row(body, label, key, placeholder=""):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            lbl = Gtk.Label(label=label)
            lbl.add_css_class("settings-field-label")
            lbl.set_halign(Gtk.Align.START)
            box.append(lbl)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            e = Gtk.Entry()
            e.set_placeholder_text(placeholder)
            e.add_css_class("settings-input")
            e.set_text(self.cfg.get(key, "") or "")
            e.set_hexpand(True)
            e.connect("changed", lambda w, k=key: self.cfg.update({k: w.get_text()}))
            row.append(e)

            browse = Gtk.Button(label="BROWSE")
            browse.add_css_class("btn-ghost")
            browse.connect("clicked", lambda b, entry=e, k=key: self._browse(entry, k))
            row.append(browse)

            if key == "steam_root":
                det = Gtk.Button(label="AUTO-DETECT")
                det.add_css_class("btn-ghost")
                def do_detect(*_):
                    from dzsl.core.config import detect_steam_root
                    newp = detect_steam_root()
                    e.set_text(newp)
                    self.cfg[key] = newp
                    self.set_status("Steam library auto-detected.")
                det.connect("clicked", do_detect)
                row.append(det)

            box.append(row)
            body.append(box)
            return e

        def text_field(body, label, key, placeholder=""):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            lbl = Gtk.Label(label=label)
            lbl.add_css_class("settings-field-label")
            lbl.set_halign(Gtk.Align.START)
            box.append(lbl)
            e = Gtk.Entry()
            e.set_placeholder_text(placeholder)
            e.add_css_class("settings-input")
            e.set_text(self.cfg.get(key, "") or "")
            e.connect("changed", lambda w, k=key: self.cfg.update({k: w.get_text()}))
            box.append(e)
            body.append(box)

        # ── PATHS ──
        paths = card("PATHS")
        field_row(paths, "Steam Library Root",                        "steam_root",    "")
        field_row(paths, "Custom Mods Folder (blank = auto-detect)", "mods_dir",      "")

        # ── LAUNCH OPTIONS ──
        launch = card("LAUNCH OPTIONS")

        checks = [
            ("no_splash",       "No Splash"),
            ("no_pause",        "No Pause"),
            ("no_benchmark",    "No Benchmark"),
            ("window_mode",     "Window Mode"),
            ("script_debug",    "Script Debug"),
            ("skip_battleye",   "Skip BattlEye"),
            ("close_on_launch", "Hide DZSL when launching"),
        ]
        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(32)
        cols = 3
        for i, (key, lbl) in enumerate(checks):
            cb = Gtk.CheckButton(label=lbl)
            cb.add_css_class("settings-check")
            cb.set_active(self.cfg.get(key, False))
            cb.connect("toggled", lambda w, k=key: self.cfg.update({k: w.get_active()}))
            grid.attach(cb, i % cols, i // cols, 1, 1)
        launch.append(grid)

        text_field(launch, "In-game Name",          "profile_name", "Your DayZ character name")
        text_field(launch, "Additional Parameters", "extra_args",   "-noPause -world=empty")
        text_field(launch, "Additional Mods",       "extra_mods",   "mod1;mod2")

        # ── DOWNLOAD ──
        dl = card("DOWNLOAD")

        storage_note = Gtk.Label(
            label=(
                "Downloads and updates are managed by Steam Workshop\n"
                f"Download location: {workshop_dir(self.cfg)}"
            )
        )
        storage_note.add_css_class("settings-note")
        storage_note.set_halign(Gtk.Align.START)
        storage_note.set_wrap(True)
        storage_note.set_selectable(True)
        dl.append(storage_note)

        # ── WORKSHOP ACTIONS ──
        ws = card("WORKSHOP ACTIONS")

        vb = Gtk.Button(label="VERIFY / REPAIR WORKSHOP MODS")
        vb.add_css_class("btn-connect")
        vb.set_halign(Gtk.Align.START)
        vb.connect("clicked", self._confirm_verify_all)
        ws.append(vb)

        ub = Gtk.Button(label="UNSUBSCRIBE FROM ALL WORKSHOP MODS")
        ub.add_css_class("btn-danger")
        ub.set_halign(Gtk.Align.START)
        ub.connect("clicked", self._confirm_unsubscribe_all)
        ws.append(ub)

        # ── SAVE / RESET ──
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        sb = Gtk.Button(label="Save Settings")
        sb.add_css_class("btn-success")
        sb.connect("clicked", self._save_settings)
        btn_row.append(sb)
        rb = Gtk.Button(label="Reset to Defaults")
        rb.add_css_class("btn-ghost")
        rb.connect("clicked", self._confirm_reset)
        btn_row.append(rb)
        outer.append(btn_row)

        scroll.set_child(outer)
        self.panel.append(scroll)

    def _save_settings(self, *_):
        save_cfg(self.cfg)
        self.set_status("Settings saved.")
        self.saved_cb()

    def _confirm(self, heading, body, action_label, callback, destructive=False):
        dialog = Adw.MessageDialog(transient_for=self.panel.get_root())
        dialog.set_heading(heading)
        dialog.set_body(body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("confirm", action_label)
        if destructive:
            dialog.set_response_appearance("confirm", Adw.ResponseAppearance.DESTRUCTIVE)
        else:
            dialog.set_response_appearance("confirm", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(message, response):
            message.destroy()
            if response == "confirm":
                callback()

        dialog.connect("response", on_response)
        dialog.present()

    def _confirm_verify_all(self, *_):
        from dzsl.core.config import get_installed_mods

        count = len(get_installed_mods(self.cfg))
        if not count:
            self.set_status("No Workshop mods found. Check Steam Library Root in Settings.")
            return
        self._confirm(
            "Verify and repair all Workshop mods?",
            f"This checks {count} installed mods and asks Steam to redownload any invalid content. It can take a long time.",
            "Verify All",
            self.workshop.verify_installed_mods,
        )

    def _confirm_unsubscribe_all(self, *_):
        from dzsl.core.config import get_installed_mods

        count = len(get_installed_mods(self.cfg))
        if not count:
            self.set_status("No Workshop mods found. Check Steam Library Root in Settings.")
            return
        self._confirm(
            "Remove all Workshop mods?",
            f"This removes local files for all {count} installed mods. Servers will need to download them again.",
            "Remove All",
            self._unsub_all,
            destructive=True,
        )

    def _confirm_reset(self, *_):
        self._confirm(
            "Reset all settings?",
            "This replaces your current paths, launch options, and download settings with defaults.",
            "Reset Settings",
            self._reset_settings,
            destructive=True,
        )

    def _reset_settings(self):
        self.cfg.update(DEFAULT_CFG)
        save_cfg(self.cfg)
        self.reload_cb()
        self.set_status("Settings reset.")

    def _browse(self, entry, key):
        dialog = Gtk.FileDialog()
        dialog.select_folder(self.panel.get_root(), None,
                             lambda d, r: self._folder_chosen(d, r, entry, key))

    def _folder_chosen(self, dialog, result, entry, key):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                entry.set_text(path)
                self.cfg[key] = path
        except Exception:
            pass

    def _steam_action(self, uri, status_msg):
        if forward_steam_uri(uri):
            self.set_status(status_msg)
        else:
            self.set_status("Could not open Steam — start Steam and try again.")

    def _unsub_all(self):
        from dzsl.core.config import get_installed_mods
        from dzsl.lifecycle import cancel_active_downloads
        mods = get_installed_mods(self.cfg)
        if not mods:
            self.set_status("No workshop mods found. Check Steam Library Root in Settings.")
            return
        self.set_status(f"Unsubscribing from {len(mods)} mods…")
        root = self.panel.get_root()
        app = root.get_application() if root else None
        if app:
            cancel_active_downloads(app)
        def do():
            removed, error = unsubscribe_mod_ids([m["id"] for m in mods], self.cfg)
            if error:
                GLib.idle_add(self.set_status, f"Steam unsubscribe failed: {error}")
            else:
                GLib.idle_add(self.set_status, f"Unsubscribed from {len(removed)} mods")
        threading.Thread(target=do, daemon=True).start()
