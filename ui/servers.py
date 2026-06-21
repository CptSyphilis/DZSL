import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib, Gdk, Adw
import requests, threading
from config import load_json, save_json, FILTERS_FILE
from ui.server_row import copy_text, popup_at_cursor, dismiss_popover, ServerRow
from ui.helpers import clear_box
from ui.helpers import (
    recent_map, normalize_map_name, server_key,
    build_map_filter_options, build_map_dropdown,
    is_map_filter_active, is_map_header_label, SORT_OPTIONS, parse_sort_mode,
    sort_mode_for_key,
)
from ui.ping import ping_servers

API_URL = "https://dayzsalauncher.com/api/v1/launcher/servers/dayz"

# Persist filter state between view switches
_filter_state = {
    "search": "",
    "ip_search": "",
    "map": 0,
    "version": 0,
    "checks": {},
    "sort_key": "players",
    "sort_rev": True,
    "servers": [],
    "versions": ["Any"],
    "maps": ["Any"],
    "map_ids": [""],
    "sort_mode": "players_desc",
}

# Load saved filters from disk on startup
try:
    saved = load_json(FILTERS_FILE)
    if isinstance(saved, dict):
        _filter_state.update(saved)
except Exception:
    pass


class ServersView:
    def __init__(self, panel, cfg, favorites, connect_cb, fav_cb, set_status, load_mods_cb=None):
        self.panel = panel
        self.cfg = cfg
        self.favorites = favorites
        self.connect_cb = connect_cb
        self.fav_cb = fav_cb
        self.set_status = set_status
        self.load_mods_cb = load_mods_cb
        self.all_servers = _filter_state["servers"]
        self.sort_key = _filter_state["sort_key"]
        self.sort_rev = _filter_state["sort_rev"]
        self.sort_mode = _filter_state.get("sort_mode", "players_desc")
        self.sort_key, self.sort_rev = parse_sort_mode(self.sort_mode)
        self._ping_generation = 0
        self._fetching = False
        self._map_prefix = ""
        self._map_cycle_index = 0
        self._suppress_map_notify = False
        self._suppress_sort_notify = False
        self._map_filter_debounce = None

    def build(self):
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        root.set_vexpand(True)

        # ── Left filter panel ────────────────────────────────────────────────
        fp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fp.add_css_class("filter-panel")
        fp.set_size_request(230, -1)
        self.fp = fp

        title = Gtk.Label(label="Filters")
        title.add_css_class("filter-title")
        title.set_halign(Gtk.Align.START)
        fp.append(title)

        self.search = Gtk.Entry()
        self.search.set_placeholder_text("Filter by name...")
        self.search.add_css_class("search-box")
        fp.append(self.search)

        self.ip_search = Gtk.Entry()
        self.ip_search.set_placeholder_text("Filter by IP...")
        self.ip_search.add_css_class("search-box")
        fp.append(self.ip_search)

        map_lbl = Gtk.Label(label="Map")
        map_lbl.add_css_class("filter-label")
        map_lbl.set_halign(Gtk.Align.START)
        fp.append(map_lbl)

        self.f_map = Gtk.DropDown.new_from_strings(_filter_state.get("maps", ["Any"]))
        fp.append(self.f_map)

        ver_lbl = Gtk.Label(label="Version")
        ver_lbl.add_css_class("filter-label")
        ver_lbl.set_halign(Gtk.Align.START)
        fp.append(ver_lbl)

        self.f_version = Gtk.DropDown.new_from_strings(_filter_state["versions"])
        fp.append(self.f_version)

        sort_lbl = Gtk.Label(label="Sort by")
        sort_lbl.add_css_class("filter-label")
        sort_lbl.set_halign(Gtk.Align.START)
        fp.append(sort_lbl)

        sort_labels = [label for _, label in SORT_OPTIONS]
        self.f_sort = Gtk.DropDown.new_from_strings(sort_labels)
        sort_modes = [mode for mode, _ in SORT_OPTIONS]
        if self.sort_mode in sort_modes:
            self.f_sort.set_selected(sort_modes.index(self.sort_mode))
        fp.append(self.f_sort)

        self.chk = {}
        for key, lbl in [
            ("favonly", "Show favourites only"),
            ("noplayed", "Not played on"),
            ("nopass", "Not password protected"),
            ("nomodded", "Not modded only"),
            ("firstperson", "FPP (First Person Perspective)"),
            ("thirdperson", "TPP (Third Person Perspective)"),
            ("online", "Is online"),
        ]:
            cb = Gtk.CheckButton(label=lbl)
            cb.add_css_class("filter-check")
            cb.connect("toggled", lambda *a: self._save_and_filter())
            self.chk[key] = cb
            fp.append(cb)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.refresh_btn = Gtk.Button(label="REFRESH")
        self.refresh_btn.add_css_class("btn-reset")
        self.refresh_btn.connect("clicked", lambda _: self.fetch())
        btn_row.append(self.refresh_btn)

        reset_btn = Gtk.Button(label="RESET")
        reset_btn.add_css_class("btn-reset")
        reset_btn.connect("clicked", self._reset_filters)
        btn_row.append(reset_btn)
        fp.append(btn_row)

        root.append(fp)

        # ── Right: header + table ────────────────────────────────────────────
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right.set_hexpand(True)

        # Column headers
        col_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        col_hdr.add_css_class("col-header")

        def col_btn(label, key, width=-1):
            b = Gtk.Button(label=label)
            b.add_css_class("col-btn")
            if width > 0:
                b.set_size_request(width, -1)
            b.connect("clicked", lambda _: self._sort_by(key))
            return b

        self.col_btns = {}
        fav_col = Gtk.Label(label="FAV")
        fav_col.add_css_class("col-label")
        fav_col.set_size_request(36, -1)
        col_hdr.append(fav_col)

        name_b = col_btn("NAME", "name")
        name_b.set_hexpand(True)
        col_hdr.append(name_b)
        self.col_btns["name"] = name_b

        col_hdr.append(col_btn("TIME", "time", 72))
        col_hdr.append(col_btn("PLAYED", "played", 90))
        col_hdr.append(col_btn("MAP", "map", 100))
        col_hdr.append(col_btn("PLAYERS", "players", 72))
        col_hdr.append(col_btn("PING", "ping", 52))

        act_col = Gtk.Label(label="")
        act_col.set_size_request(44, -1)
        col_hdr.append(act_col)
        right.append(col_hdr)

        # Server list
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.srv_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        loading = Gtk.Label(label="Loading servers...")
        loading.add_css_class("empty")
        loading.set_margin_top(60)
        self.srv_box.append(loading)
        scroll.set_child(self.srv_box)
        right.append(scroll)
        self.scroll = scroll

        root.append(right)
        self.panel.append(root)

        self._setup_map_typeahead(root)

        # Restore previous filter state
        if _filter_state.get("search"):
            self.search.set_text(_filter_state["search"])
        if _filter_state.get("ip_search"):
            self.ip_search.set_text(_filter_state["ip_search"])
        if _filter_state.get("map"):
            self.f_map.set_selected(_filter_state["map"])
        if _filter_state.get("version"):
            self.f_version.set_selected(min(_filter_state["version"], len(_filter_state["versions"]) - 1))

        sort_modes = [mode for mode, _ in SORT_OPTIONS]
        if hasattr(self, "f_sort") and self.sort_mode in sort_modes:
            self.f_sort.set_selected(sort_modes.index(self.sort_mode))

        for key, val in _filter_state.get("checks", {}).items():
            if key in self.chk:
                self.chk[key].set_active(val)

        self.search.connect("changed", lambda *a: self._save_and_filter())
        self.ip_search.connect("changed", lambda *a: self._save_and_filter())
        self.f_map.connect("notify::selected", self._on_map_selected)
        self.f_version.connect("notify::selected", lambda *a: self._save_and_filter())
        self.f_sort.connect("notify::selected", self._on_sort_selected)

        self._update_sort_header_labels()

        if self.all_servers:
            self._update_map_filter()
            self.apply_filters()
        else:
            self.fetch()

    # ... (all other methods stay exactly the same until _save_and_filter)

    def _save_and_filter(self):
        _filter_state["search"] = self.search.get_text()
        _filter_state["ip_search"] = self.ip_search.get_text()
        _filter_state["map"] = self.f_map.get_selected()
        _filter_state["version"] = self.f_version.get_selected()
        _filter_state["checks"] = {k: v.get_active() for k, v in self.chk.items()}

        self.apply_filters()

        # Save filters to disk so they persist after restart
        try:
            save_json(FILTERS_FILE, {
                "search": _filter_state.get("search", ""),
                "ip_search": _filter_state.get("ip_search", ""),
                "map": _filter_state.get("map", 0),
                "version": _filter_state.get("version", 0),
                "checks": _filter_state.get("checks", {}),
                "sort_mode": _filter_state.get("sort_mode", "players_desc"),
            })
        except Exception:
            pass

    # All remaining methods (_on_map_selected, apply_filters, fetch, etc.) stay unchanged