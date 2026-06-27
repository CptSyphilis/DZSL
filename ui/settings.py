import gi, shutil
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
from config import DEFAULT_CFG, save_cfg
from ui.helpers import forward_steam_uri, unsubscribe_mod_ids
from ui.workshop_actions import WorkshopActionRunner
import threading

class SettingsView:
    def __init__(self, panel, cfg, set_status, reload_cb, set_downloading=None):
        self.panel      = panel
        self.cfg        = cfg
        self.set_status = set_status
        self.reload_cb  = reload_cb
        self.set_downloading = set_downloading or (lambda *_: None)
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
                    from config import detect_steam_root
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
        field_row(paths, "Steam Library Root",                        "steam_root",    "/mnt/Storage1tb/SteamLibrary")
        field_row(paths, "CLI Launcher Path",                         "launcher_path", "bin/dayz-launcher.sh")
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

        backend_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        backend_row.set_valign(Gtk.Align.CENTER)
        bvbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        bvbox.set_hexpand(True)
        blbl = Gtk.Label(label="Download backend")
        blbl.add_css_class("settings-field-label"); blbl.set_halign(Gtk.Align.START)
        bvbox.append(blbl)
        bnote = Gtk.Label(label="auto = DepotDownloader if available, else Steam")
        bnote.add_css_class("settings-note"); bnote.set_halign(Gtk.Align.START)
        bvbox.append(bnote)
        backend_row.append(bvbox)
        _backend_opts = ["auto", "depot", "steam"]
        backend_store = Gtk.StringList.new(_backend_opts)
        backend_dd = Gtk.DropDown.new(backend_store, None)
        cur = self.cfg.get("download_backend", "auto")
        backend_dd.set_selected(_backend_opts.index(cur) if cur in _backend_opts else 0)
        backend_dd.connect("notify::selected", lambda w, _: self.cfg.update({"download_backend": _backend_opts[w.get_selected()]}))
        backend_row.append(backend_dd)
        dl.append(backend_row)

        def spin_row(body, label, key, lo, hi, step, note=None, sensitive=True):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.set_valign(Gtk.Align.CENTER)
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vbox.set_hexpand(True)
            lbl = Gtk.Label(label=label)
            lbl.add_css_class("settings-field-label")
            lbl.set_halign(Gtk.Align.START)
            vbox.append(lbl)
            if note:
                n = Gtk.Label(label=note)
                n.add_css_class("settings-note")
                n.set_halign(Gtk.Align.START)
                vbox.append(n)
            row.append(vbox)
            spin = Gtk.SpinButton.new_with_range(lo, hi, step)
            spin.set_value(self.cfg.get(key, lo))
            spin.set_sensitive(sensitive)
            spin.set_width_chars(6)
            spin.connect("value-changed", lambda w, k=key: self.cfg.update({k: int(w.get_value())}))
            row.append(spin)
            body.append(row)

        trickle_ok = bool(shutil.which("trickle"))
        spin_row(dl, "Max concurrent chunks", "download_max_chunks", 1, 8, 1)
        spin_row(dl, "Speed limit (KB/s)",    "download_speed_kbps", 0, 100000, 500,
                 note=None if trickle_ok else "install trickle to enable",
                 sensitive=trickle_ok)

        # ── WORKSHOP ACTIONS ──
        ws = card("WORKSHOP ACTIONS")

        vb = Gtk.Button(label="VERIFY / REPAIR WORKSHOP MODS")
        vb.add_css_class("btn-ghost")
        vb.set_halign(Gtk.Align.START)
        vb.connect("clicked", lambda b: self.workshop.verify_installed_mods())
        ws.append(vb)

        ub = Gtk.Button(label="UNSUBSCRIBE FROM ALL WORKSHOP MODS")
        ub.add_css_class("btn-danger")
        ub.set_halign(Gtk.Align.START)
        ub.connect("clicked", lambda b: self._unsub_all())
        ws.append(ub)

        # ── SAVE / RESET ──
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        sb = Gtk.Button(label="Save Settings")
        sb.add_css_class("btn-connect")
        sb.connect("clicked", lambda b: [save_cfg(self.cfg), self.set_status("Settings saved.")])
        btn_row.append(sb)
        rb = Gtk.Button(label="Reset to Defaults")
        rb.add_css_class("btn-ghost")
        rb.connect("clicked", lambda b: [self.cfg.update(DEFAULT_CFG), save_cfg(self.cfg), self.reload_cb(), self.set_status("Settings reset.")])
        btn_row.append(rb)
        outer.append(btn_row)

        scroll.set_child(outer)
        self.panel.append(scroll)

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
        from config import get_installed_mods
        mods = get_installed_mods(self.cfg)
        if not mods:
            self.set_status("No workshop mods found. Check Steam Library Root in Settings.")
            return
        self.set_status(f"Unsubscribing from {len(mods)} mods…")
        def do():
            unsubscribe_mod_ids([m["id"] for m in mods], self.cfg)
            GLib.idle_add(self.set_status, f"Unsubscribed from {len(mods)} mods")
        threading.Thread(target=do, daemon=True).start()
