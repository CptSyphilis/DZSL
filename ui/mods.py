import datetime
import os
import shutil
import subprocess
import sys
import threading

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gdk, Gio, Graphene, Gtk, GLib
import requests

from config import get_installed_mods, mod_subscribed, workshop_dirs
from steam_workshop import validate_mod_folder
from ui.helpers import clear_box, forward_steam_uri
from ui.workshop_actions import WorkshopActionRunner

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


def _unparent_popover(popover):
    if popover and popover.get_parent():
        popover.unparent()
    return False


def dismiss_popover(popover):
    if not popover:
        return
    popover.popdown()
    GLib.idle_add(_unparent_popover, popover)


def popup_at_cursor(popover, widget, x, y):
    anchor = widget.get_parent()
    while anchor and not isinstance(anchor, Gtk.ScrolledWindow):
        anchor = anchor.get_parent()
    anchor = anchor or widget.get_root()
    source = Graphene.Point()
    source.x, source.y = x, y
    ok, target = widget.compute_point(anchor, source)
    rect = Gdk.Rectangle()
    rect.x = int(target.x if ok else x)
    rect.y = int(target.y if ok else y)
    rect.width = rect.height = 1
    popover.set_parent(anchor)
    popover.set_has_arrow(False)
    popover.set_pointing_to(rect)
    popover.popup()


def _format_size(value):
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def _format_timestamp(value):
    try:
        return datetime.datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d %H:%M")
    except (OSError, TypeError, ValueError):
        return "Unknown"


class InstalledModRow(Gtk.Box):
    def __init__(self, owner, mod, refresh_cb):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.owner = owner
        self.mod = mod
        self.refresh_cb = refresh_cb
        self.expanded = False
        self.workshop_details = None
        self.add_css_class("mod-row")
        self.add_css_class("mod-record")

        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main.add_css_class("mod-record-main")
        self.status_dot = Gtk.Label(label="●")
        self.status_dot.add_css_class("mod-status")
        main.append(self.status_dot)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.set_hexpand(True)
        name = Gtk.Label(label=mod["name"])
        name.add_css_class("mod-name")
        name.set_halign(Gtk.Align.START)
        name.set_ellipsize(3)
        info.append(name)
        ident = Gtk.Label(label=f"ID: {mod['id']}  ·  {mod['path']}")
        ident.add_css_class("mod-id")
        ident.set_halign(Gtk.Align.START)
        ident.set_ellipsize(3)
        info.append(ident)
        main.append(info)

        verify = Gtk.Button(label="Verify")
        verify.add_css_class("btn-ghost")
        verify.connect("clicked", lambda *_: self.verify())
        main.append(verify)

        repair = Gtk.Button(label="Repair")
        repair.add_css_class("btn-ghost")
        repair.connect("clicked", lambda *_: self.repair())
        main.append(repair)

        self.chevron = Gtk.Label(label="›")
        self.chevron.add_css_class("mod-chevron")
        main.append(self.chevron)
        self.append(main)

        self.details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        self.details.add_css_class("mod-details")
        self.details.set_visible(False)
        self.fields = {}
        for label in ("Source", "Author", "Last update", "File size", "Status"):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            key = Gtk.Label(label=label.upper())
            key.add_css_class("mod-detail-key")
            key.set_width_chars(14)
            key.set_halign(Gtk.Align.START)
            value = Gtk.Label(label="Looking up Workshop metadata…")
            value.add_css_class("mod-detail-value")
            value.set_halign(Gtk.Align.START)
            value.set_selectable(True)
            value.set_wrap(True)
            row.append(key)
            row.append(value)
            self.details.append(row)
            self.fields[label] = value

        dep_key = Gtk.Label(label="DEPENDENCIES")
        dep_key.add_css_class("mod-detail-key")
        dep_key.set_halign(Gtk.Align.START)
        self.details.append(dep_key)
        self.dependencies = Gtk.Label(label="Looking up Workshop metadata…")
        self.dependencies.add_css_class("mod-detail-value")
        self.dependencies.set_halign(Gtk.Align.START)
        self.dependencies.set_wrap(True)
        self.dependencies.set_selectable(True)
        self.details.append(self.dependencies)
        self.append(self.details)

        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("pressed", self._on_left_click)
        self.add_controller(click)

        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self._on_right_click)
        self.add_controller(right_click)

        valid, reason = validate_mod_folder(mod["path"])
        self._set_state("warn" if valid else "bad", "Checking Workshop…" if valid else reason)

    def _set_state(self, state, text):
        for css_class in ("mod-status-good", "mod-status-warn", "mod-status-bad"):
            self.status_dot.remove_css_class(css_class)
        self.status_dot.add_css_class(f"mod-status-{state}")
        self.status_dot.set_tooltip_text(text)
        self.fields["Status"].set_text(text)

    def _on_left_click(self, _gesture, n_press, x, y):
        if n_press != 1:
            return
        target = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        widget = target
        while widget is not None:
            if isinstance(widget, Gtk.Button):
                return
            widget = widget.get_parent()
        self.toggle_expand()

    def toggle_expand(self, force_open=False):
        self.expanded = True if force_open else not self.expanded
        self.details.set_visible(self.expanded)
        self.chevron.set_text("⌄" if self.expanded else "›")
        if self.expanded:
            self.add_css_class("selected")
        else:
            self.remove_css_class("selected")

    def apply_workshop_details(self, detail, dependency_names=None, error=None):
        valid, reason = validate_mod_folder(self.mod["path"])
        if not detail:
            self.fields["Source"].set_text(f"Steam Workshop · {self.mod['id']}")
            self.fields["Author"].set_text("Unknown")
            self.fields["Last update"].set_text("Unknown")
            self.fields["File size"].set_text("Unknown")
            self.dependencies.set_text("Unavailable")
            self._set_state("bad" if not valid else "warn", reason if not valid else f"Ready locally · {error or 'Workshop lookup unavailable'}")
            return

        self.workshop_details = detail
        self.fields["Source"].set_text(f"Steam Workshop · {self.mod['id']}")
        creator = str(detail.get("creator") or "")
        self.fields["Author"].set_text(f"Steam user {creator}" if creator else "Unknown")
        self.fields["Last update"].set_text(_format_timestamp(detail.get("time_updated")))
        self.fields["File size"].set_text(_format_size(detail.get("file_size")))
        children = [str(child.get("publishedfileid") or "") for child in detail.get("children", [])]
        children = [child for child in children if child]
        names = dependency_names or {}
        self.dependencies.set_text(
            "\n".join(f"• {names.get(child, child)}  ({child})" for child in children)
            if children else "None reported by Steam Workshop"
        )
        subscribed = mod_subscribed(self.owner.cfg, self.mod["id"])
        if valid:
            state = "good" if subscribed else "warn"
            text = "Ready" if subscribed else "Ready locally · not subscribed"
        else:
            state, text = "bad", reason
        self._set_state(state, text)

    def verify(self):
        valid, reason = validate_mod_folder(self.mod["path"])
        if valid:
            self._set_state("good", "Verified · local PBO payload is readable")
            self.owner.set_status(f"Verified {self.mod['name']}")
        else:
            self._set_state("bad", reason)
            self.owner.set_status(f"Verification failed for {self.mod['name']}: {reason}")

    def repair(self):
        mid, name = self.mod["id"], self.mod["name"]
        self.owner.workshop.install_mods(
            [mid], {mid: name}, label=f"Repairing {name}", repair=True, redownload=True,
        )

    def update(self):
        mid, name = self.mod["id"], self.mod["name"]
        self.owner.workshop.install_mods(
            [mid], {mid: name}, label=f"Updating {name}", repair=True, redownload=True,
        )

    def open_web_page(self):
        forward_steam_uri(f"steam://url/CommunityFilePage/{self.mod['id']}")

    def open_folder(self):
        try:
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(self.mod["path"]).get_uri(), None)
            self.owner.set_status(f"Opened folder for {self.mod['name']}")
        except GLib.Error as exc:
            self.owner.set_status(f"Could not open mod folder: {exc.message}")

    def show_dependencies(self):
        self.toggle_expand(force_open=True)
        self.owner.set_status(f"Showing dependencies for {self.mod['name']}")

    def remove(self):
        self.owner._unsub_mod(self.mod, self.refresh_cb)

    def _on_right_click(self, _gesture, n_press, x, y):
        if n_press != 1:
            return
        dismiss_popover(getattr(self, "_popover", None))
        popover = Gtk.Popover.new()
        self._popover = popover
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        for label, callback in (
            ("Open web page", self.open_web_page),
            ("Open folder", self.open_folder),
            ("Show dependencies", self.show_dependencies),
            ("Update", self.update),
            ("Verify", self.verify),
            ("Repair", self.repair),
            ("Remove mod / Unsubscribe", self.remove),
        ):
            button = Gtk.Button(label=label)
            button.add_css_class("context-btn")
            button.connect("clicked", lambda _button, cb=callback: self._run_menu_action(popover, cb))
            box.append(button)
        popover.set_child(box)
        popup_at_cursor(popover, self, x, y)

    def _run_menu_action(self, popover, callback):
        popover.popdown()
        callback()

class ModsView:
    def __init__(self, panel, cfg, set_status, set_downloading=None):
        self.panel      = panel
        self.cfg        = cfg
        self.set_status = set_status
        self.set_downloading = set_downloading or (lambda *_: None)
        self.workshop = WorkshopActionRunner(cfg, set_status, self.set_downloading)
        self._details_cache = {}
        self._details_loading = set()
        self._mod_rows = {}

    def _steam_action(self, uri, status_msg):
        if forward_steam_uri(uri):
            self.set_status(status_msg)
        else:
            self.set_status("Could not open Steam — start Steam and try again.")

    def _unsub_mod(self, mod, on_done=None):
        def do():
            mid, name, path = mod["id"], mod["name"], mod["path"]
            helper = os.path.join(os.path.dirname(os.path.dirname(__file__)), "steam_api.py")
            unsubscribed = False
            try:
                result = subprocess.run(
                    [sys.executable, helper, "unsubscribe", mid],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                unsubscribed = result.returncode == 0
            except (OSError, subprocess.SubprocessError):
                pass
            shutil.rmtree(path, ignore_errors=True)
            message = f"Removed and unsubscribed {name}" if unsubscribed else f"Removed local files for {name}; Steam unsubscribe failed"
            GLib.idle_add(self.set_status, message)
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
        install_id = Gtk.Entry()
        install_id.set_placeholder_text("Workshop ID")
        install_id.add_css_class("search-box")
        install_id.set_width_chars(14)
        tb.append(install_id)
        ib = Gtk.Button(label="Install ID")
        ib.add_css_class("toolbar-btn")
        ib.connect("clicked", lambda _: self._install_workshop_id(install_id))
        tb.append(ib)
        ub = Gtk.Button(label="Check Updates"); ub.add_css_class("toolbar-btn"); ub.add_css_class("accent"); tb.append(ub)
        self.content.append(tb)

        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.inst_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        def populate(q=None):
            q = se.get_text() if q is None else q
            clear_box(self.inst_box)
            self._mod_rows = {}
            mods = get_installed_mods(self.cfg)
            if q: mods = [m for m in mods if q.lower() in m["name"].lower() or q in m["id"]]
            if not mods:
                el = Gtk.Label(label="No mods installed."); el.add_css_class("empty"); el.set_margin_top(60); self.inst_box.append(el); return
            for m in mods:
                row = InstalledModRow(self, m, populate)
                self._mod_rows[m["id"]] = row
                self.inst_box.append(row)
                cached = self._details_cache.get(m["id"])
                if cached:
                    row.apply_workshop_details(*cached)
            self._request_workshop_details([m["id"] for m in mods])

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
                        data=pd, timeout=120,
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
                    names = {m["id"]: m["name"] for m in mods}
                    GLib.idle_add(
                        self.workshop.install_mods,
                        outdated,
                        names,
                        f"Updating {len(outdated)} outdated mod(s)",
                        True,
                        True,
                    )
            threading.Thread(target=_check, daemon=True).start()

        populate()
        se.connect("changed", lambda e: populate(e.get_text()))
        ub.connect("clicked", check_updates)
        scroll.set_child(self.inst_box); self.content.append(scroll)

    def _request_workshop_details(self, mod_ids):
        ids = [mid for mid in mod_ids if mid not in self._details_cache and mid not in self._details_loading]
        if not ids:
            return
        self._details_loading.update(ids)

        def request(items):
            payload = {"itemcount": len(items)}
            for index, mid in enumerate(items):
                payload[f"publishedfileids[{index}]"] = mid
            return requests.post(
                "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                data=payload,
                timeout=120,
            ).json().get("response", {}).get("publishedfiledetails", [])

        def fetch():
            try:
                details = request(ids)
                by_id = {str(item.get("publishedfileid")): item for item in details}
                dependency_ids = {
                    str(child.get("publishedfileid"))
                    for item in details
                    for child in item.get("children", [])
                    if child.get("publishedfileid")
                }
                dependency_names = {}
                if dependency_ids:
                    for item in request(sorted(dependency_ids)):
                        dependency_names[str(item.get("publishedfileid"))] = item.get("title") or str(item.get("publishedfileid"))
                result = {
                    mid: (by_id.get(mid), dependency_names, None if mid in by_id else "Workshop item was not returned")
                    for mid in ids
                }
            except Exception as exc:
                result = {mid: (None, {}, str(exc)) for mid in ids}
            GLib.idle_add(self._apply_workshop_details, ids, result)

        threading.Thread(target=fetch, daemon=True).start()

    def _apply_workshop_details(self, ids, result):
        self._details_loading.difference_update(ids)
        self._details_cache.update(result)
        for mid in ids:
            row = self._mod_rows.get(mid)
            if row:
                row.apply_workshop_details(*result[mid])
        return False

    def _install_workshop_id(self, entry):
        mid = entry.get_text().strip()
        if not mid.isdigit():
            self.set_status("Enter a numeric Steam Workshop ID.")
            return
        entry.set_text("")
        self.workshop.install_mods([mid], {mid: mid}, label=f"Installing Workshop mod {mid}")

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
            ib.connect(
                "clicked",
                lambda _, t=tid, nm=name: self.workshop.install_mods(
                    [t],
                    {t: nm},
                    label=f"Installing {nm}",
                ),
            )
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
                for d in requests.post("https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/", data=pd, timeout=120).json().get("response", {}).get("publishedfiledetails", []):
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
