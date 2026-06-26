import gi, shutil
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import requests, threading, subprocess, os, time
from config import get_installed_mods, workshop_dirs
from ui.helpers import clear_box, forward_steam_uri

TOOLS = [
    ("830640",      "DayZ Tools",           "Official Bohemia modding tools. Required for creating mods."),
    ("1240340",     "DayZ Exp Tools",        "Experimental DayZ Tools with latest features."),
    ("1559212036",  "CF Framework",          "Community Framework — base dependency for many mods."),
    ("1434340862",  "VPP Admin Tools",       "Server admin tools — teleport, spawn, manage players."),
    ("2400487916",  "DayZ Editor",           "In-game map editor for building custom scenarios."),
    ("1538608369",  "BuilderItems",          "Large construction item pack for DayZ servers."),
    ("1564026768",  "Community Online Tools","Server management tools for admins."),
    ("2545327648",  "Dabs Framework",        "Framework required by many popular mods."),
]

class ModsView:
    def __init__(self, panel, cfg, set_status):
        self.panel      = panel
        self.cfg        = cfg
        self.set_status = set_status

    def _steam_action(self, uri, status_msg):
        if forward_steam_uri(uri):
            self.set_status(status_msg)
        else:
            self.set_status("Could not open Steam — start Steam and try again.")

    def _unsub_mod(self, mid, name, btn, path, on_done=None):
        def do():
            shutil.rmtree(path, ignore_errors=True)
            GLib.idle_add(self.set_status, f"Removed {name}")
            if on_done:
                GLib.idle_add(on_done)
        threading.Thread(target=do, daemon=True).start()

    def build(self):
        tbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tbar.add_css_class("toolbar")
        self.tabs = {}
        for key, lbl in [("installed", "Installed Mods"), ("tools", "Tools"), ("creators", "Mod Creators")]:
            b = Gtk.Button(label=lbl); b.add_css_class("subtab")
            b.connect("clicked", lambda _, k=key: self._show_tab(k))
            self.tabs[key] = b; tbar.append(b)
        self.panel.append(tbar)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content.set_vexpand(True)
        self.panel.append(self.content)
        self._show_tab("installed")

    def _show_tab(self, tab):
        for k, b in self.tabs.items():
            if k == tab: b.add_css_class("active")
            else: b.remove_css_class("active")
        clear_box(self.content)
        {"installed": self._installed, "tools": self._tools, "creators": self._creators}[tab]()

    def _installed(self):
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8); tb.add_css_class("toolbar")
        se = Gtk.Entry(); se.set_placeholder_text("Search mods…"); se.add_css_class("search-box"); se.set_hexpand(True); tb.append(se)
        ub = Gtk.Button(label="Check Updates"); ub.add_css_class("toolbar-btn"); ub.add_css_class("accent"); tb.append(ub)
        self.content.append(tb)

        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.inst_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        def populate(q=""):
            clear_box(self.inst_box)
            mods = get_installed_mods(self.cfg)
            if q: mods = [m for m in mods if q.lower() in m["name"].lower() or q in m["id"]]
            if not mods:
                el = Gtk.Label(label="No mods installed."); el.add_css_class("empty"); el.set_margin_top(60); self.inst_box.append(el); return
            for m in mods:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); row.add_css_class("mod-row")
                inf = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2); inf.set_hexpand(True)
                nl = Gtk.Label(label=m["name"]); nl.add_css_class("mod-name"); nl.set_halign(Gtk.Align.START); nl.set_ellipsize(3); inf.append(nl)
                il = Gtk.Label(label=f"ID: {m['id']}  ·  {m['path']}"); il.add_css_class("mod-id"); il.set_halign(Gtk.Align.START); inf.append(il)
                row.append(inf)
                bb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                wb = Gtk.Button(label="Workshop"); wb.add_css_class("btn-ghost")
                wb.connect("clicked", lambda _, mid=m["id"]: forward_steam_uri(f"steam://url/CommunityFilePage/{mid}"))
                bb.append(wb)
                upd = Gtk.Button(label="Update"); upd.add_css_class("btn-ghost")
                upd.connect("clicked", lambda _, mid=m["id"], nm=m["name"]: self._steam_action(f"steam://installworkshop/221100/{mid}", f"Updating {nm}…"))
                bb.append(upd)
                db = Gtk.Button(label="Unsubscribe"); db.add_css_class("btn-danger")
                db.connect("clicked", lambda _, mid=m["id"], nm=m["name"], p=m["path"], btn=db: self._unsub_mod(mid, nm, btn, p, populate))
                bb.append(db); row.append(bb); self.inst_box.append(row)

        def check_updates(b):
            mods = get_installed_mods(self.cfg)
            if not mods:
                self.set_status("No mods installed.")
                return
            ub.set_label("Checking…"); ub.set_sensitive(False)
            self.set_status(f"Checking {len(mods)} mods for updates…")
            def _check():
                outdated = []
                error = None
                try:
                    ids = [m["id"] for m in mods]
                    pd = {"itemcount": len(ids)}
                    for i, mid in enumerate(ids): pd[f"publishedfileids[{i}]"] = mid
                    details = requests.post(
                        "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                        data=pd, timeout=15,
                    ).json().get("response", {}).get("publishedfiledetails", [])
                    for d in details:
                        mid = str(d.get("publishedfileid", ""))
                        rt = d.get("time_updated", 0)
                        path = next(
                            (os.path.join(wd, mid) for wd in workshop_dirs(self.cfg) if os.path.isdir(os.path.join(wd, mid))),
                            "",
                        )
                        lt = int(os.path.getmtime(path)) if path else 0
                        if rt > lt:
                            outdated.append(mid)
                except Exception as e:
                    error = str(e)
                GLib.idle_add(ub.set_label, "Check Updates")
                GLib.idle_add(ub.set_sensitive, True)
                if error:
                    GLib.idle_add(self.set_status, f"Update check failed: {error}")
                elif not outdated:
                    GLib.idle_add(self.set_status, f"All {len(mods)} mods are up to date")
                else:
                    for mid in outdated:
                        for wd in workshop_dirs(self.cfg):
                            p = os.path.join(wd, mid)
                            if os.path.isdir(p):
                                shutil.rmtree(p, ignore_errors=True)
                        forward_steam_uri(f"steam://installworkshop/221100/{mid}")
                        time.sleep(0.3)
                    GLib.idle_add(self.set_status, f"Updating {len(outdated)} outdated mod(s) via Steam")
            threading.Thread(target=_check, daemon=True).start()

        populate()
        se.connect("changed", lambda e: populate(e.get_text()))
        ub.connect("clicked", check_updates)
        scroll.set_child(self.inst_box); self.content.append(scroll)

    def _tools(self):
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        lbl = Gtk.Label(label="TOOLS & POPULAR MODS"); lbl.add_css_class("settings-title"); lbl.set_halign(Gtk.Align.START); box.append(lbl)
        for tid, name, desc in TOOLS:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12); row.add_css_class("mod-row")
            inf = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2); inf.set_hexpand(True)
            nl = Gtk.Label(label=name); nl.add_css_class("mod-name"); nl.set_halign(Gtk.Align.START); inf.append(nl)
            dl = Gtk.Label(label=desc); dl.add_css_class("mod-id"); dl.set_halign(Gtk.Align.START); dl.set_wrap(True); inf.append(dl)
            row.append(inf)
            bb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            ib = Gtk.Button(label="Install"); ib.add_css_class("btn-connect")
            ib.connect("clicked", lambda _, t=tid, nm=name: self._steam_action(f"steam://subscribe/{t}", f"Installing {nm}…"))
            wb = Gtk.Button(label="Workshop"); wb.add_css_class("btn-ghost")
            wb.connect("clicked", lambda _, t=tid: forward_steam_uri(f"steam://url/CommunityFilePage/{t}"))
            bb.append(ib); bb.append(wb); row.append(bb); box.append(row)
        scroll.set_child(box); self.content.append(scroll)

    def _creators(self):
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        loading = Gtk.Label(label="Loading creator info…"); loading.add_css_class("empty"); loading.set_margin_top(60); box.append(loading)
        scroll.set_child(box); self.content.append(scroll)

        def fetch():
            mods = get_installed_mods(self.cfg); creators = {}
            try:
                ids = [m["id"] for m in mods]; pd = {"itemcount": len(ids)}
                for i, mid in enumerate(ids): pd[f"publishedfileids[{i}]"] = mid
                for d in requests.post("https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/", data=pd, timeout=15).json().get("response", {}).get("publishedfiledetails", []):
                    cid = d.get("creator", ""); mn = d.get("title", d.get("publishedfileid", ""))
                    if cid: creators.setdefault(cid, []).append(mn)
            except: pass

            def show():
                clear_box(box)
                if not creators:
                    el = Gtk.Label(label="No creator info found."); el.add_css_class("empty"); el.set_margin_top(60); box.append(el); return
                for cid, mnames in creators.items():
                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12); row.add_css_class("mod-row")
                    inf = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2); inf.set_hexpand(True)
                    cl = Gtk.Label(label=f"Creator {cid}"); cl.add_css_class("mod-name"); cl.set_halign(Gtk.Align.START); inf.append(cl)
                    ml = Gtk.Label(label=", ".join(mnames[:4]) + ("…" if len(mnames) > 4 else "")); ml.add_css_class("mod-id"); ml.set_halign(Gtk.Align.START); inf.append(ml)
                    row.append(inf)
                    pb = Gtk.Button(label="Profile"); pb.add_css_class("btn-ghost")
                    pb.connect("clicked", lambda _, c=cid: forward_steam_uri(f"steam://url/SteamIDPage/{c}"))
                    row.append(pb); box.append(row)
            GLib.idle_add(show)

        threading.Thread(target=fetch, daemon=True).start()
