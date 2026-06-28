import datetime
import os
import shutil
import subprocess
import sys
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Graphene', '1.0')
from gi.repository import Gdk, Gio, Graphene, Gtk, GLib
import requests

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

from config import get_installed_mods, mod_subscribed, workshop_dirs
from steam_workshop import validate_mod_folder
from ui.helpers import clear_box, forward_steam_uri
from ui.workshop_actions import WorkshopActionRunner

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
STEAM_API_KEY = os.getenv("STEAM_API_KEY") or os.getenv("API_KEY", "")

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
    def __init__(self, owner, mod, refresh_cb, validation=None):
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
        self.select_check = Gtk.CheckButton()
        self.select_check.add_css_class("mod-select-check")
        self.select_check.set_visible(owner._selection_mode)
        self.select_check.set_active(mod["id"] in owner._selected_mod_ids)
        self.select_check.connect("toggled", self._on_selection_toggled)
        main.append(self.select_check)
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
        ident = Gtk.Label(label=f"Workshop {mod['id']}")
        ident.add_css_class("mod-id")
        ident.set_halign(Gtk.Align.START)
        ident.set_ellipsize(3)
        ident.set_tooltip_text(mod["path"])
        info.append(ident)
        main.append(info)

        self.status_label = Gtk.Label(label="CHECKING")
        self.status_label.add_css_class("mod-state-pill")
        main.append(self.status_label)

        actions = Gtk.MenuButton()
        actions.set_icon_name("view-more-symbolic")
        actions.add_css_class("mod-action-menu")
        actions.set_tooltip_text("Mod actions")
        actions.set_popover(self._build_actions_popover())
        main.append(actions)

        self.chevron = Gtk.Label(label="›")
        self.chevron.add_css_class("mod-chevron")
        main.append(self.chevron)
        self.append(main)

        self.details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.details.add_css_class("mod-details")
        self.details.set_visible(False)
        detail_grid = Gtk.Grid()
        detail_grid.add_css_class("mod-details-grid")
        detail_grid.set_column_spacing(32)
        detail_grid.set_row_spacing(12)
        detail_grid.set_column_homogeneous(True)
        self.fields = {}
        for index, label in enumerate(("Source", "Author", "Last update", "File size", "Status")):
            cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            cell.add_css_class("mod-detail-cell")
            cell.set_hexpand(True)
            key = Gtk.Label(label=label.upper())
            key.add_css_class("mod-detail-key")
            key.set_halign(Gtk.Align.START)
            value = Gtk.Label(label="Looking up Workshop metadata…")
            value.add_css_class("mod-detail-value")
            value.set_halign(Gtk.Align.START)
            value.set_valign(Gtk.Align.START)
            value.set_selectable(True)
            value.set_wrap(True)
            cell.append(key)
            cell.append(value)
            detail_grid.attach(cell, index % 3, index // 3, 1, 1)
            self.fields[label] = value
        self.details.append(detail_grid)

        dep_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        dep_box.add_css_class("mod-dependencies")
        dep_key = Gtk.Label(label="DEPENDENCIES")
        dep_key.add_css_class("mod-detail-key")
        dep_key.set_halign(Gtk.Align.START)
        dep_box.append(dep_key)
        self.dependencies = Gtk.Label(label="Looking up Workshop metadata…")
        self.dependencies.add_css_class("mod-detail-value")
        self.dependencies.set_halign(Gtk.Align.START)
        self.dependencies.set_wrap(True)
        self.dependencies.set_selectable(True)
        dep_box.append(self.dependencies)
        self.details.append(dep_box)
        self.append(self.details)

        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("pressed", self._on_left_click)
        self.add_controller(click)

        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self._on_right_click)
        self.add_controller(right_click)

        valid, reason = validation or validate_mod_folder(mod["path"])
        self._set_state("warn" if valid else "bad", "Checking Workshop…" if valid else reason)
        self._set_selected_visual(self.select_check.get_active())

    def _set_state(self, state, text):
        for css_class in ("mod-status-good", "mod-status-warn", "mod-status-bad", "mod-status-update"):
            self.status_dot.remove_css_class(css_class)
            self.status_label.remove_css_class(css_class)
        self.status_dot.add_css_class(f"mod-status-{state}")
        self.status_label.add_css_class(f"mod-status-{state}")
        self.status_dot.set_tooltip_text(text)
        self.status_label.set_tooltip_text(text)
        self.status_label.set_text({"good": "READY", "warn": "CHECKING", "bad": "ATTENTION", "update": "UPDATE"}[state])
        self.fields["Status"].set_text(text)

    def _on_left_click(self, _gesture, n_press, x, y):
        if n_press != 1:
            return
        target = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        widget = target
        while widget is not None:
            if isinstance(widget, (Gtk.Button, Gtk.CheckButton, Gtk.MenuButton)):
                return
            widget = widget.get_parent()
        if self.owner._selection_mode:
            self.select_check.set_active(not self.select_check.get_active())
            return
        self.toggle_expand()

    def _on_selection_toggled(self, check):
        selected = check.get_active()
        self._set_selected_visual(selected)
        self.owner._set_mod_selected(self.mod["id"], selected)

    def _set_selected_visual(self, selected):
        if selected:
            self.add_css_class("marked")
        else:
            self.remove_css_class("marked")

    def set_selection_mode(self, enabled):
        self.select_check.set_visible(enabled)

    def set_selected(self, selected):
        self.select_check.set_active(selected)
        self._set_selected_visual(selected)

    def toggle_expand(self, force_open=False):
        expanding = True if force_open else not self.expanded
        if expanding:
            previous = self.owner._expanded_row
            if previous is not None and previous is not self:
                previous._set_expanded(False)
            self.owner._expanded_row = self
        elif self.owner._expanded_row is self:
            self.owner._expanded_row = None
        self._set_expanded(expanding)

    def _set_expanded(self, expanded):
        self.expanded = expanded
        self.details.set_visible(self.expanded)
        self.chevron.set_text("⌄" if self.expanded else "›")
        if self.expanded:
            self.add_css_class("selected")
        else:
            self.remove_css_class("selected")

    def apply_workshop_details(self, detail, dependency_names=None, error=None):
        valid, reason = validate_mod_folder(self.mod["path"])
        if not detail:
            self.fields["Source"].set_text(self.mod["path"])
            self.fields["Author"].set_text("Unknown")
            self.fields["Last update"].set_text("Unknown")
            self.fields["File size"].set_text("Unknown")
            self.dependencies.set_text("Unavailable")
            self._set_state("bad" if not valid else "warn", reason if not valid else f"Ready locally · {error or 'Workshop lookup unavailable'}")
            return

        self.workshop_details = detail
        self.fields["Source"].set_text(self.mod["path"])
        creator = str(detail.get("creator") or "")
        creator_profile = detail.get("_creator_profile") or {}
        creator_name = creator_profile.get("personaname")
        self.fields["Author"].set_text(creator_name or ("Steam creator" if creator else "Unknown"))
        self.fields["Author"].set_tooltip_text(
            f"Steam ID {creator}" if creator else None
        )
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
        remote_updated = int(detail.get("time_updated", 0) or 0)
        try:
            local_updated = int(os.path.getmtime(self.mod["path"]))
        except OSError:
            local_updated = 0
        if valid and remote_updated > local_updated:
            state, text = "update", "Workshop update available"
        elif valid:
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

    def select_for_batch(self):
        self.owner._set_selection_mode(True)
        self.set_selected(True)

    def remove(self):
        self.owner._unsub_mod(self.mod, self.refresh_cb)

    def _on_right_click(self, _gesture, n_press, x, y):
        if n_press != 1:
            return
        dismiss_popover(getattr(self, "_popover", None))
        if self.owner._selection_mode and not self.select_check.get_active():
            self.set_selected(True)
        popover = self._build_actions_popover(selection_mode=self.owner._selection_mode)
        self._popover = popover

        popup_at_cursor(popover, self, x, y)

    def _build_actions_popover(self, selection_mode=False):
        popover = Gtk.Popover.new()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        if selection_mode:
            count = len(self.owner._selected_mod_ids)
            actions = (
                ("Deselect this mod", lambda: self.set_selected(False)),
                ("Select all", self.owner._select_all_mods),
                (f"Verify {count} selected", self.owner._verify_selected_mods),
                (f"Repair {count} selected", self.owner._repair_selected_mods),
                ("Done selecting", lambda: self.owner._set_selection_mode(False)),
            )
        else:
            actions = (
                ("Select", self.select_for_batch),
                ("Open web page", self.open_web_page),
                ("Open folder", self.open_folder),
                ("Show dependencies", self.show_dependencies),
                ("Update", self.update),
                ("Verify", self.verify),
                ("Repair", self.repair),
                ("Remove mod / Unsubscribe", self.remove),
            )
        for label, callback in actions:
            button = Gtk.Button(label=label)
            button.add_css_class("context-btn")
            button.connect("clicked", lambda _button, cb=callback: self._run_menu_action(popover, cb))
            box.append(button)
        popover.set_child(box)
        return popover

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
        self._creator_cache = {}
        self._expanded_row = None
        self._installed_rebuild = None
        self._installed_mod_map = {}
        self._outdated_ids = set()
        self._selection_mode = False
        self._selected_mod_ids = set()
        self._selection_bar = None
        self._selection_label = None
        self._select_button = None
        self._update_button = None

    def _fetch_creator_profiles(self, creator_ids):
        ids = [str(cid) for cid in creator_ids if cid]
        missing = [cid for cid in ids if cid not in self._creator_cache]
        if missing and STEAM_API_KEY:
            try:
                for start in range(0, len(missing), 100):
                    batch = missing[start:start + 100]
                    response = requests.get(
                        "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                        params={"key": STEAM_API_KEY, "steamids": ",".join(batch)},
                        timeout=30,
                    )
                    response.raise_for_status()
                    players = response.json().get("response", {}).get("players", [])
                    self._creator_cache.update(
                        {str(player.get("steamid")): player for player in players if player.get("steamid")}
                    )
                    for cid in batch:
                        self._creator_cache.setdefault(cid, {})
            except (requests.RequestException, ValueError) as exc:
                GLib.idle_add(self.set_status, f"Could not load Steam creator names: {exc}")
        return {cid: self._creator_cache.get(cid, {}) for cid in ids}

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
        self._installed_rebuild = None
        for k, b in self.tabs.items():
            if k == tab: b.add_css_class("active")
            else: b.remove_css_class("active")
        clear_box(self.content)
        {"installed": self._installed, "tools": self._tools, "creators": self._creators}[tab]()

    def _installed(self):
        overview = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        overview.add_css_class("mods-overview")
        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        heading.set_hexpand(True)
        title = Gtk.Label(label="WORKSHOP LOADOUT")
        title.add_css_class("mods-overview-title")
        title.set_halign(Gtk.Align.START)
        heading.append(title)
        source = Gtk.Label(label="Steam-managed content ready for DayZ")
        source.add_css_class("mods-overview-subtitle")
        source.set_halign(Gtk.Align.START)
        heading.append(source)
        overview.append(heading)

        def metric(label):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            box.add_css_class("mods-metric")
            value = Gtk.Label(label="0")
            value.add_css_class("mods-metric-value")
            caption = Gtk.Label(label=label)
            caption.add_css_class("mods-metric-label")
            box.append(value)
            box.append(caption)
            overview.append(box)
            return value

        installed_value = metric("INSTALLED")
        ready_value = metric("READY")
        attention_value = metric("ATTENTION")
        attention_value.add_css_class("mods-metric-attention")
        updates_value = metric("UPDATES")
        updates_value.add_css_class("mods-metric-update")
        self.content.append(overview)

        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tb.add_css_class("toolbar")
        tb.add_css_class("mods-toolbar")
        select_button = Gtk.Button(label="Select")
        select_button.add_css_class("toolbar-btn")
        select_button.connect("clicked", lambda *_: self._set_selection_mode(not self._selection_mode))
        tb.append(select_button)
        self._select_button = select_button
        se = Gtk.Entry(); se.set_placeholder_text("Search installed mods…"); se.add_css_class("search-box"); se.set_hexpand(True); tb.append(se)
        install_id = Gtk.Entry()
        install_id.set_placeholder_text("Paste Workshop ID")
        install_id.add_css_class("search-box")
        install_id.set_width_chars(18)
        tb.append(install_id)
        ib = Gtk.Button(label="Install")
        ib.add_css_class("toolbar-btn")
        ib.connect("clicked", lambda _: self._install_workshop_id(install_id))
        tb.append(ib)
        ub = Gtk.Button(label="Check updates"); ub.add_css_class("toolbar-btn"); ub.add_css_class("accent"); tb.append(ub)
        self._update_button = ub
        self.content.append(tb)

        selection_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        selection_bar.add_css_class("mod-selection-bar")
        selection_bar.set_visible(False)
        selection_label = Gtk.Label(label="0 selected")
        selection_label.add_css_class("mod-selection-count")
        selection_label.set_hexpand(True)
        selection_label.set_halign(Gtk.Align.START)
        selection_bar.append(selection_label)
        select_all = Gtk.Button(label="Select all")
        select_all.add_css_class("toolbar-btn")
        select_all.connect("clicked", lambda *_: self._select_all_mods())
        selection_bar.append(select_all)
        verify_selected = Gtk.Button(label="Verify")
        verify_selected.add_css_class("toolbar-btn")
        verify_selected.connect("clicked", lambda *_: self._verify_selected_mods())
        selection_bar.append(verify_selected)
        repair_selected = Gtk.Button(label="Repair")
        repair_selected.add_css_class("toolbar-btn")
        repair_selected.add_css_class("accent")
        repair_selected.connect("clicked", lambda *_: self._repair_selected_mods())
        selection_bar.append(repair_selected)
        done = Gtk.Button(label="Done")
        done.add_css_class("toolbar-btn")
        done.connect("clicked", lambda *_: self._set_selection_mode(False))
        selection_bar.append(done)
        self._selection_bar = selection_bar
        self._selection_label = selection_label
        self.content.append(selection_bar)

        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.inst_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        all_mods = []
        validations = {}
        loaded = False

        def populate(q=None, refresh=False):
            nonlocal all_mods, validations, loaded
            q = se.get_text() if q is None else q
            clear_box(self.inst_box)
            self._mod_rows = {}
            self._expanded_row = None
            if refresh or not loaded:
                all_mods = get_installed_mods(self.cfg)
                self._installed_mod_map = {m["id"]: m for m in all_mods}
                self._selected_mod_ids.intersection_update(self._installed_mod_map)
                validations = {m["id"]: validate_mod_folder(m["path"]) for m in all_mods}
                loaded = True
                ready = sum(1 for valid, _reason in validations.values() if valid)
                installed_value.set_text(str(len(all_mods)))
                ready_value.set_text(str(ready))
                attention_value.set_text(str(len(all_mods) - ready))
            mods = all_mods
            if q: mods = [m for m in mods if q.lower() in m["name"].lower() or q in m["id"]]
            if not mods:
                empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                empty.add_css_class("mods-empty")
                label = "No matching mods" if q else "No Workshop mods found"
                hint = "Try another name or Workshop ID." if q else "Paste a Workshop ID above to install your first mod."
                heading = Gtk.Label(label=label); heading.add_css_class("mods-empty-title")
                detail = Gtk.Label(label=hint); detail.add_css_class("mods-empty-detail")
                empty.append(heading); empty.append(detail); self.inst_box.append(empty); return
            self._outdated_ids = {
                m["id"] for m in all_mods
                if self._is_mod_outdated(m, self._details_cache.get(m["id"]))
            }
            updates_value.set_text(str(len(self._outdated_ids)))
            self._refresh_update_button_label()

            outdated = [m for m in mods if m["id"] in self._outdated_ids]
            current = [m for m in mods if m["id"] not in self._outdated_ids]

            def append_section(label, section_mods, update_section=False):
                if not section_mods:
                    return
                header = Gtk.Label(label=f"{label}  ·  {len(section_mods)}")
                header.add_css_class("mod-section-header")
                if update_section:
                    header.add_css_class("mod-section-update")
                header.set_halign(Gtk.Align.START)
                self.inst_box.append(header)
                for mod in section_mods:
                    row = InstalledModRow(self, mod, lambda: populate(refresh=True), validations.get(mod["id"]))
                    self._mod_rows[mod["id"]] = row
                    self.inst_box.append(row)
                    cached = self._details_cache.get(mod["id"])
                    if cached:
                        row.apply_workshop_details(*cached)

            append_section("UPDATES AVAILABLE", outdated, True)
            append_section("INSTALLED MODS", current)
            self._request_workshop_details([m["id"] for m in mods])

        def check_updates(b):
            selected_scope = self._selection_mode
            if selected_scope:
                if not self._selected_mod_ids:
                    self.set_status("Select at least one mod to check for updates.")
                    return
                mods = [
                    self._installed_mod_map[mid]
                    for mid in self._selected_mod_ids
                    if mid in self._installed_mod_map
                ]
            else:
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
                GLib.idle_add(self._refresh_update_button_label)
                GLib.idle_add(ub.set_sensitive, True)
                if error:
                    GLib.idle_add(self.set_status, f"Update check failed: {error}")
                elif not outdated:
                    scope = "selected mods" if selected_scope else "mods"
                    GLib.idle_add(self.set_status, f"All {len(mods)} {scope} are up to date")
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

        self._installed_rebuild = lambda: populate(se.get_text())
        populate(refresh=True)
        se.connect("changed", lambda e: populate(e.get_text()))
        ub.connect("clicked", check_updates)
        scroll.set_child(self.inst_box); self.content.append(scroll)

    def _set_selection_mode(self, enabled):
        self._selection_mode = enabled
        if self._selection_bar:
            self._selection_bar.set_visible(enabled)
        if self._select_button:
            self._select_button.set_label("Done" if enabled else "Select")
        if not enabled:
            self._selected_mod_ids.clear()
        for row in self._mod_rows.values():
            row.set_selection_mode(enabled)
            if not enabled:
                row.set_selected(False)
        self._update_selection_label()

    def _set_mod_selected(self, mod_id, selected):
        if selected:
            self._selected_mod_ids.add(str(mod_id))
        else:
            self._selected_mod_ids.discard(str(mod_id))
        self._update_selection_label()

    def _update_selection_label(self):
        if self._selection_label:
            count = len(self._selected_mod_ids)
            self._selection_label.set_text(f"{count} selected")
        self._refresh_update_button_label()

    def _refresh_update_button_label(self):
        if not self._update_button:
            return False
        if self._selection_mode:
            self._update_button.set_label(f"Check selected ({len(self._selected_mod_ids)})")
        elif self._outdated_ids:
            self._update_button.set_label(f"Update all ({len(self._outdated_ids)})")
        else:
            self._update_button.set_label("Check updates")
        return False

    def _select_all_mods(self):
        self._selected_mod_ids = set(self._installed_mod_map)
        for mid, row in self._mod_rows.items():
            row.set_selected(mid in self._selected_mod_ids)
        self._update_selection_label()

    def _verify_selected_mods(self):
        selected = [self._installed_mod_map[mid] for mid in self._selected_mod_ids if mid in self._installed_mod_map]
        if not selected:
            self.set_status("Select at least one mod to verify.")
            return
        failed = 0
        for mod in selected:
            valid, reason = validate_mod_folder(mod["path"])
            row = self._mod_rows.get(mod["id"])
            if row:
                if valid and mod["id"] in self._outdated_ids:
                    row._set_state("update", "Verified locally · Workshop update available")
                else:
                    row._set_state("good" if valid else "bad", "Verified · local PBO payload is readable" if valid else reason)
            failed += int(not valid)
        self.set_status(
            f"Verified {len(selected)} mods · {failed} need attention"
            if failed else f"Verified {len(selected)} mods · all ready"
        )

    def _repair_selected_mods(self):
        selected = [self._installed_mod_map[mid] for mid in self._selected_mod_ids if mid in self._installed_mod_map]
        if not selected:
            self.set_status("Select at least one mod to repair.")
            return
        ids = [mod["id"] for mod in selected]
        names = {mod["id"]: mod["name"] for mod in selected}
        self.workshop.install_mods(
            ids,
            names,
            label=f"Repairing {len(ids)} selected mod(s)",
            repair=True,
            redownload=True,
        )
        self._set_selection_mode(False)

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
                creator_profiles = self._fetch_creator_profiles(
                    {str(item.get("creator") or "") for item in details}
                )
                for item in details:
                    creator = str(item.get("creator") or "")
                    item["_creator_profile"] = creator_profiles.get(creator, {})
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
        previous_outdated = set(self._outdated_ids)
        current_outdated = {
            mid for mid, mod in self._installed_mod_map.items()
            if self._is_mod_outdated(mod, self._details_cache.get(mid))
        }
        if self._installed_rebuild and current_outdated != previous_outdated:
            self._outdated_ids = current_outdated
            self._installed_rebuild()
            return False
        for mid in ids:
            row = self._mod_rows.get(mid)
            if row:
                row.apply_workshop_details(*result[mid])
        return False

    @staticmethod
    def _is_mod_outdated(mod, cached):
        detail = cached[0] if cached else None
        if not detail:
            return False
        remote_updated = int(detail.get("time_updated", 0) or 0)
        try:
            local_updated = int(os.path.getmtime(mod["path"]))
        except OSError:
            return False
        return remote_updated > local_updated

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
        overview = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        overview.add_css_class("mods-overview")
        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        heading.set_hexpand(True)
        title = Gtk.Label(label="CREATOR INDEX")
        title.add_css_class("mods-overview-title")
        title.set_halign(Gtk.Align.START)
        heading.append(title)
        subtitle = Gtk.Label(label="The people behind your installed Workshop loadout")
        subtitle.add_css_class("mods-overview-subtitle")
        subtitle.set_halign(Gtk.Align.START)
        heading.append(subtitle)
        overview.append(heading)

        def metric(label):
            wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            wrapper.add_css_class("mods-metric")
            value = Gtk.Label(label="—")
            value.add_css_class("mods-metric-value")
            caption = Gtk.Label(label=label)
            caption.add_css_class("mods-metric-label")
            wrapper.append(value)
            wrapper.append(caption)
            overview.append(wrapper)
            return value

        creators_value = metric("CREATORS")
        mods_value = metric("MODS")
        self.content.append(overview)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.add_css_class("toolbar")
        toolbar.add_css_class("creator-toolbar")
        search = Gtk.Entry()
        search.set_placeholder_text("Search creators or their mods…")
        search.add_css_class("search-box")
        search.set_hexpand(True)
        toolbar.append(search)
        self.content.append(toolbar)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        loading = Gtk.Label(label="Loading Steam creator profiles…")
        loading.add_css_class("empty")
        loading.set_margin_top(60)
        box.append(loading)
        scroll.set_child(box)
        self.content.append(scroll)

        records = []
        active_expander = [None]

        def render(query=""):
            clear_box(box)
            active_expander[0] = None
            needle = query.strip().lower()
            visible = [
                record for record in records
                if not needle
                or needle in record["name"].lower()
                or any(needle in mod["name"].lower() or needle in mod["id"] for mod in record["mods"])
            ]
            if not visible:
                empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                empty.add_css_class("mods-empty")
                empty_title = Gtk.Label(label="No matching creators" if needle else "No creator information found")
                empty_title.add_css_class("mods-empty-title")
                empty_detail = Gtk.Label(label="Try a creator, mod name, or Workshop ID." if needle else "Steam did not return creator details for the installed mods.")
                empty_detail.add_css_class("mods-empty-detail")
                empty.append(empty_title)
                empty.append(empty_detail)
                box.append(empty)
                return

            for record in visible:
                row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                row.add_css_class("creator-record")
                main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                main.add_css_class("creator-record-main")

                monogram = Gtk.Label(label=(record["name"][:1] or "?").upper())
                monogram.add_css_class("creator-monogram")
                main.append(monogram)

                info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                info.set_hexpand(True)
                name = Gtk.Label(label=record["name"])
                name.add_css_class("creator-name")
                name.set_halign(Gtk.Align.START)
                name.set_tooltip_text(f"Steam ID {record['id']}")
                info.append(name)
                mod_count = len(record["mods"])
                meta = Gtk.Label(label=f"{mod_count} installed mod{'s' if mod_count != 1 else ''}")
                meta.add_css_class("creator-meta")
                meta.set_halign(Gtk.Align.START)
                info.append(meta)
                main.append(info)

                profile = Gtk.Button(label="Steam profile")
                profile.add_css_class("btn-steam")
                profile.connect("clicked", lambda _button, cid=record["id"]: forward_steam_uri(f"steam://url/SteamIDPage/{cid}"))
                main.append(profile)
                chevron = Gtk.Label(label="›")
                chevron.add_css_class("creator-chevron")
                main.append(chevron)
                row.append(main)

                details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                details.add_css_class("creator-details")
                details.set_visible(False)
                detail_label = Gtk.Label(label="INSTALLED WORKSHOP MODS")
                detail_label.add_css_class("mod-detail-key")
                detail_label.set_halign(Gtk.Align.START)
                details.append(detail_label)
                shelf = Gtk.FlowBox()
                shelf.add_css_class("creator-mod-shelf")
                shelf.set_selection_mode(Gtk.SelectionMode.NONE)
                shelf.set_min_children_per_line(1)
                shelf.set_max_children_per_line(4)
                for mod in record["mods"]:
                    mod_button = Gtk.Button(label=mod["name"])
                    mod_button.add_css_class("creator-mod-chip")
                    mod_button.set_tooltip_text(f"Workshop {mod['id']}")
                    mod_button.connect("clicked", lambda _button, mid=mod["id"]: forward_steam_uri(f"steam://url/CommunityFilePage/{mid}"))
                    shelf.append(mod_button)
                details.append(shelf)
                row.append(details)

                def set_expanded(expanded, target=row, panel=details, arrow=chevron):
                    panel.set_visible(expanded)
                    arrow.set_text("⌄" if expanded else "›")
                    if expanded:
                        target.add_css_class("expanded")
                    else:
                        target.remove_css_class("expanded")

                def on_row_click(_gesture, n_press, x, y, panel=details, expand=set_expanded, container=row):
                    if n_press != 1:
                        return
                    target = container.pick(x, y, Gtk.PickFlags.DEFAULT)
                    while target is not None:
                        if isinstance(target, Gtk.Button):
                            return
                        target = target.get_parent()
                    opening = not panel.get_visible()
                    if opening and active_expander[0] and active_expander[0] is not expand:
                        active_expander[0](False)
                    expand(opening)
                    active_expander[0] = expand if opening else None

                click = Gtk.GestureClick.new()
                click.set_button(1)
                click.connect("pressed", on_row_click)
                row.add_controller(click)
                box.append(row)

        search.connect("changed", lambda entry: render(entry.get_text()))

        def fetch():
            mods = get_installed_mods(self.cfg)
            creators = {}
            profiles = {}
            error = None
            try:
                ids = [mod["id"] for mod in mods]
                payload = {"itemcount": len(ids)}
                for index, mid in enumerate(ids):
                    payload[f"publishedfileids[{index}]"] = mid
                response = requests.post(
                    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                    data=payload,
                    timeout=120,
                )
                response.raise_for_status()
                details = response.json().get("response", {}).get("publishedfiledetails", [])
                for detail in details:
                    creator_id = str(detail.get("creator") or "")
                    mod_id = str(detail.get("publishedfileid") or "")
                    mod_name = detail.get("title") or mod_id
                    if creator_id:
                        creators.setdefault(creator_id, []).append({"id": mod_id, "name": mod_name})
                profiles = self._fetch_creator_profiles(creators)
            except (requests.RequestException, ValueError) as exc:
                error = str(exc)

            def show():
                if error:
                    self.set_status(f"Could not load mod creators: {error}")
                records.clear()
                records.extend(sorted(
                    (
                        {
                            "id": creator_id,
                            "name": profiles.get(creator_id, {}).get("personaname") or "Steam creator",
                            "mods": sorted(creator_mods, key=lambda mod: mod["name"].lower()),
                        }
                        for creator_id, creator_mods in creators.items()
                    ),
                    key=lambda record: record["name"].lower(),
                ))
                creators_value.set_text(str(len(records)))
                mods_value.set_text(str(sum(len(record["mods"]) for record in records)))
                render(search.get_text())
                return False

            GLib.idle_add(show)

        threading.Thread(target=fetch, daemon=True).start()
