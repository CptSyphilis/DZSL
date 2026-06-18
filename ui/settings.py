import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from config import DEFAULT_CFG, save_cfg
from ui.helpers import forward_steam_uri
import subprocess, threading

class SettingsView:
    def __init__(self, panel, cfg, set_status, reload_cb):
        self.panel      = panel
        self.cfg        = cfg
        self.set_status = set_status
        self.reload_cb  = reload_cb

    def build(self):
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        def section(title):
            l = Gtk.Label(label=title); l.add_css_class("settings-title"); l.set_halign(Gtk.Align.START); outer.append(l)

        def path_row(label, key, placeholder=""):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4); box.add_css_class("settings-group")
            lbl = Gtk.Label(label=label); lbl.add_css_class("settings-label"); lbl.set_halign(Gtk.Align.START); box.append(lbl)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            e = Gtk.Entry(); e.set_placeholder_text(placeholder); e.add_css_class("settings-input")
            e.set_text(self.cfg.get(key, "") or ""); e.set_hexpand(True)
            e.connect("changed", lambda w, k=key: self.cfg.update({k: w.get_text()}))
            row.append(e)
            browse = Gtk.Button(label="BROWSE"); browse.add_css_class("btn-ghost")
            browse.connect("clicked", lambda b, entry=e, k=key: self._browse(entry, k))
            row.append(browse)
            if key == "steam_root":
                det = Gtk.Button(label="AUTO-DETECT"); det.add_css_class("btn-ghost")
                def do_detect(*_):
                    from config import detect_steam_root
                    newp = detect_steam_root()
                    e.set_text(newp)
                    self.cfg[key] = newp
                    self.set_status("Steam library auto-detected.")
                det.connect("clicked", do_detect)
                row.append(det)
            box.append(row); outer.append(box)

        def text_row(label, key, placeholder=""):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4); box.add_css_class("settings-group")
            lbl = Gtk.Label(label=label); lbl.add_css_class("settings-label"); lbl.set_halign(Gtk.Align.START); box.append(lbl)
            e = Gtk.Entry(); e.set_placeholder_text(placeholder); e.add_css_class("settings-input")
            e.set_text(self.cfg.get(key, "") or "")
            e.connect("changed", lambda w, k=key: self.cfg.update({k: w.get_text()}))
            box.append(e); outer.append(box)

        section("PATHS")
        path_row("Steam Library Root",  "steam_root",    "/mnt/Storage1tb/SteamLibrary")
        path_row("CLI Launcher Path",   "launcher_path", "bin/dayz-launcher.sh")
        path_row("Custom Mods Folder (blank = auto)", "mods_dir", "leave blank for auto-detect")

        section("LAUNCH OPTIONS")
        chk_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16); chk_box.add_css_class("settings-group")
        for key, lbl in [("no_splash","No Splash"),("no_pause","No Pause"),("no_benchmark","No Benchmark"),("window_mode","Window Mode"),("script_debug","Script Debug"),("skip_battleye","Skip BattlEye"),("close_on_launch","Close app after launching server")]:
            cb = Gtk.CheckButton(label=lbl); cb.add_css_class("filter-check")
            cb.set_active(self.cfg.get(key, False))
            cb.connect("toggled", lambda w, k=key: self.cfg.update({k: w.get_active()}))
            chk_box.append(cb)
        outer.append(chk_box)

        text_row("In-game Name",          "profile_name", "Your DayZ character name")
        text_row("Additional Parameters", "extra_args",   "-noPause -world=empty")
        text_row("Additional Mods",       "extra_mods",   "mod1;mod2")

        section("WORKSHOP ACTIONS")
        abox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); abox.add_css_class("settings-group")
        vb = Gtk.Button(label="VERIFY ALL STEAM WORKSHOP MODS"); vb.add_css_class("btn-ghost")
        vb.connect("clicked", lambda b: [subprocess.Popen(["steam", "steam://validate/221100"]), self.set_status("Verifying DayZ via Steam...")])
        abox.append(vb)
        ub = Gtk.Button(label="UNSUBSCRIBE FROM ALL STEAM WORKSHOP MODS"); ub.add_css_class("btn-danger")
        ub.connect("clicked", lambda b: self._unsub_all())
        abox.append(ub)
        outer.append(abox)

        sbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8); sbox.set_margin_start(16); sbox.set_margin_top(8); sbox.set_margin_bottom(16)
        sb = Gtk.Button(label="Save Settings"); sb.add_css_class("btn-connect")
        sb.connect("clicked", lambda b: [save_cfg(self.cfg), self.set_status("Settings saved.")])
        sbox.append(sb)
        rb = Gtk.Button(label="Reset to Defaults"); rb.add_css_class("btn-ghost")
        rb.connect("clicked", lambda b: [self.cfg.update(DEFAULT_CFG), save_cfg(self.cfg), self.reload_cb(), self.set_status("Settings reset.")])
        sbox.append(rb)
        outer.append(sbox)
        scroll.set_child(outer); self.panel.append(scroll)

    def _browse(self, entry, key):
        dialog = Gtk.FileDialog()
        dialog.select_folder(self.panel.get_root(), None, lambda d, r: self._folder_chosen(d, r, entry, key))

    def _folder_chosen(self, dialog, result, entry, key):
        try:
            folder = dialog.select_folder_finish(result)
            if folder: path = folder.get_path(); entry.set_text(path); self.cfg[key] = path
        except: pass

    def _unsub_all(self):
        from config import get_installed_mods
        import time
        mods = get_installed_mods(self.cfg)
        self.set_status(f"Unsubscribing from {len(mods)} mods...")
        def do():
            for m in mods: subprocess.Popen(["steam", f"steam://unsubscribe/{m['id']}"]); time.sleep(0.3)
            self.set_status("Unsubscribed from all mods")
        threading.Thread(target=do, daemon=True).start()
