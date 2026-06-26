import os
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib, Gdk, Adw
import requests, threading
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False
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
from applog import get_logger

log = get_logger("servers")

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
API_URL = os.getenv("API_URL", "https://dayzsalauncher.com/api/v1/launcher/servers/dayz")

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

# Load persisted filters from previous session
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
        self._search_filter_debounce = None
        self._expand_tracker = [None]  # shared accordion state for ServerRow widgets

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
        act_col.set_size_request(72, -1)  # play (44) + info (28) buttons in each row
        col_hdr.append(act_col)
        right.append(col_hdr)

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

        # Restore saved filter values
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

        self.search.connect("changed", lambda *a: self._schedule_search_filter())
        self.ip_search.connect("changed", lambda *a: self._schedule_search_filter())
        self.f_map.connect("notify::selected", self._on_map_selected)
        self.f_version.connect("notify::selected", lambda *a: self._save_and_filter())
        self.f_sort.connect("notify::selected", self._on_sort_selected)

        self._update_sort_header_labels()

        if self.all_servers:
            self._update_map_filter()
            self.apply_filters()
        else:
            self.fetch()

    def _on_map_selected(self, *_args):
        if self._suppress_map_notify:
            _filter_state["map"] = self.f_map.get_selected()
            return
        self._clear_map_prefix()
        self._schedule_map_filter()

    def _schedule_map_filter(self, delay_ms=150):
        if self._map_filter_debounce:
            GLib.source_remove(self._map_filter_debounce)
        self._map_filter_debounce = GLib.timeout_add(delay_ms, self._commit_map_filter)

    def _schedule_search_filter(self, delay_ms=300):
        if self._search_filter_debounce:
            GLib.source_remove(self._search_filter_debounce)
        self._search_filter_debounce = GLib.timeout_add(delay_ms, self._commit_search_filter)

    def _commit_search_filter(self):
        self._search_filter_debounce = None
        self._save_and_filter()
        return False

    def _commit_map_filter(self):
        self._map_filter_debounce = None
        _filter_state["map"] = self.f_map.get_selected()
        self.apply_filters()
        return False

    def _select_map_index(self, idx):
        changed = idx != self.f_map.get_selected()
        _filter_state["map"] = idx
        if not changed:
            return
        self._suppress_map_notify = True
        self.f_map.set_selected(idx)
        self._suppress_map_notify = False
        self._schedule_map_filter()

    def _map_matches(self):
        labels = _filter_state.get("maps", [])
        prefix = self._map_prefix.lower()
        return [
            i for i, label in enumerate(labels)
            if i > 0 and not is_map_header_label(label)
            and label.split(" (")[0].lower().startswith(prefix)
        ]

    def _apply_map_prefix(self, cycle=False):
        matches = self._map_matches()
        if not matches:
            return
        if cycle:
            self._map_cycle_index = (self._map_cycle_index + 1) % len(matches)
        else:
            self._map_cycle_index = 0
        self._select_map_index(matches[self._map_cycle_index])

    def _clear_map_prefix(self):
        self._map_prefix = ""
        self._map_cycle_index = 0

    def _setup_map_typeahead(self, widget):
        ctrl = Gtk.EventControllerKey.new()
        ctrl.connect("key-pressed", self._on_map_typeahead)
        widget.add_controller(ctrl)

    def _in_filter_panel(self, widget):
        w = widget
        while w:
            if w == self.fp:
                return True
            w = w.get_parent()
        return False

    def _in_server_list(self, widget):
        w = widget
        while w:
            if w in (self.srv_box, self.scroll):
                return True
            w = w.get_parent()
        return False

    def _map_typeahead_active(self, focus):
        if not focus:
            return self.f_map.has_focus()
        if focus in (self.search, self.ip_search) or isinstance(focus, Gtk.Entry):
            return False
        if self._in_server_list(focus):
            return False
        if self.f_map.has_focus() or self._in_filter_panel(focus):
            return True
        w = focus
        while w:
            if isinstance(w, Gtk.Popover) and w.get_parent() == self.f_map:
                return True
            w = w.get_parent()
        return False

    def _on_map_typeahead(self, _ctrl, keyval, _keycode, state):
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SUPER_MASK):
            return Gdk.EVENT_PROPAGATE
        root = self.panel.get_root()
        focus = root.get_focus() if root else None
        if not self._map_typeahead_active(focus):
            return Gdk.EVENT_PROPAGATE
        keyname = Gdk.keyval_name(keyval)
        if keyname == "BackSpace":
            self._map_prefix = self._map_prefix[:-1]
            if not self._map_prefix:
                self._map_cycle_index = 0
                return Gdk.EVENT_PROPAGATE
            self._apply_map_prefix(cycle=False)
            return Gdk.EVENT_STOP
        if keyname == "Escape":
            self._clear_map_prefix()
            return Gdk.EVENT_STOP
        code = Gdk.keyval_to_unicode(keyval)
        if not code:
            return Gdk.EVENT_PROPAGATE
        ch = chr(code).lower()
        if not ch.isalpha():
            return Gdk.EVENT_PROPAGATE
        if len(self._map_prefix) == 1 and ch == self._map_prefix:
            self._apply_map_prefix(cycle=True)
        else:
            self._map_prefix = (self._map_prefix + ch) if self._map_prefix else ch
            self._apply_map_prefix(cycle=False)
        return Gdk.EVENT_STOP

    def _on_sort_selected(self, *_args):
        if getattr(self, "_suppress_sort_notify", False):
            return
        sort_modes = [mode for mode, _ in SORT_OPTIONS]
        idx = self.f_sort.get_selected()
        if 0 <= idx < len(sort_modes):
            self._set_sort_mode(sort_modes[idx])

    def _set_sort_mode(self, mode):
        self.sort_mode = mode
        _filter_state["sort_mode"] = mode
        self.sort_key, self.sort_rev = parse_sort_mode(mode)
        _filter_state["sort_key"] = self.sort_key
        _filter_state["sort_rev"] = self.sort_rev
        self._update_sort_header_labels()
        self.apply_filters()

    def _update_sort_header_labels(self):
        if not hasattr(self, "col_btns"):
            return
        labels = {
            "name": "NAME", "time": "TIME", "played": "PLAYED",
            "map": "MAP", "players": "PLAYERS", "ping": "PING",
        }
        for key, btn in self.col_btns.items():
            text = labels.get(key, key.upper())
            if key == self.sort_key:
                text += " ▼" if self.sort_rev else " ▲"
            btn.set_label(text)

    def _sort_by(self, key):
        if self.sort_key == key:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_key = key
            self.sort_rev = True
        _filter_state["sort_key"] = self.sort_key
        _filter_state["sort_rev"] = self.sort_rev
        self.sort_mode = sort_mode_for_key(self.sort_key, self.sort_rev)
        _filter_state["sort_mode"] = self.sort_mode
        sort_modes = [mode for mode, _ in SORT_OPTIONS]
        if hasattr(self, "f_sort") and self.sort_mode in sort_modes:
            self._suppress_sort_notify = True
            self.f_sort.set_selected(sort_modes.index(self.sort_mode))
            self._suppress_sort_notify = False
        self._update_sort_header_labels()
        self.apply_filters()

    def _reset_filters(self, b=None):
        _filter_state["saved_map_id"] = ""
        self._clear_map_prefix()
        self.search.set_text("")
        self.ip_search.set_text("")
        self.f_map.set_selected(0)
        self.f_version.set_selected(0)
        self.sort_mode = "players_desc"
        _filter_state["sort_mode"] = self.sort_mode
        self.sort_key, self.sort_rev = parse_sort_mode(self.sort_mode)
        if hasattr(self, "f_sort"):
            self._suppress_sort_notify = True
            self.f_sort.set_selected(0)
            self._suppress_sort_notify = False
        for cb in self.chk.values():
            cb.set_active(False)
        self._update_sort_header_labels()
        self._save_and_filter()

    def _save_and_filter(self):
        _filter_state["search"] = self.search.get_text()
        _filter_state["ip_search"] = self.ip_search.get_text()
        _filter_state["map"] = self.f_map.get_selected()
        _filter_state["version"] = self.f_version.get_selected()
        _filter_state["checks"] = {k: v.get_active() for k, v in self.chk.items()}

        # Save the actual map ID (much more reliable)
        map_idx = self.f_map.get_selected()
        if map_idx < len(_filter_state.get("map_ids", [])):
            _filter_state["saved_map_id"] = _filter_state["map_ids"][map_idx]
        else:
            _filter_state["saved_map_id"] = ""

        self.apply_filters()

        # Save to disk
        try:
            save_json(FILTERS_FILE, {
                "search": _filter_state.get("search", ""),
                "ip_search": _filter_state.get("ip_search", ""),
                "map": _filter_state.get("map", 0),
                "saved_map_id": _filter_state.get("saved_map_id", ""),
                "version": _filter_state.get("version", 0),
                "checks": _filter_state.get("checks", {}),
                "sort_mode": _filter_state.get("sort_mode", "players_desc"),
            })
        except Exception:
            pass

    def _update_version_filter(self):
        versions = sorted({s.get("version", "")[:4] for s in self.all_servers if s.get("version")}, reverse=True)
        _filter_state["versions"] = ["Any"] + versions
        if hasattr(self, "f_version"):
            sel = min(self.f_version.get_selected(), len(_filter_state["versions"]) - 1)
            self.f_version.set_model(Gtk.StringList.new(_filter_state["versions"]))
            self.f_version.set_selected(sel)

    def _update_map_filter(self):
        official, community = build_map_filter_options(self.all_servers)
        labels, ids = build_map_dropdown(official, community)
        _filter_state["maps"] = labels
        _filter_state["map_ids"] = ids

        if hasattr(self, "f_map"):
            self.f_map.set_model(Gtk.StringList.new(labels))

            saved_id = _filter_state.get("saved_map_id")
            if saved_id and saved_id in ids:
                idx = ids.index(saved_id)
                self.f_map.set_selected(idx)
                _filter_state["map"] = idx
            else:
                self.f_map.set_selected(0)   # default to "Any"

    def fetch(self):
        if self._fetching or getattr(self, "_refresh_cooldown", False):
            return
        self._fetching = True
        GLib.idle_add(self._set_refresh_enabled, False)
        self.set_status("Fetching server list...")
        threading.Thread(target=self._fetch_thread, daemon=True).start()

    def _set_refresh_enabled(self, enabled):
        if getattr(self, "refresh_btn", None):
            self.refresh_btn.set_sensitive(enabled)

    def _fetch_done(self, error_msg=None):
        self._fetching = False
        if error_msg:
            self.set_status(error_msg)
        self._refresh_cooldown = True
        GLib.timeout_add_seconds(3, self._end_refresh_cooldown)

    def _end_refresh_cooldown(self):
        self._refresh_cooldown = False
        self._set_refresh_enabled(True)
        return False

    def _fetch_thread(self):
        try:
            r = requests.get(API_URL, headers={"User-Agent": "DZSL/1.0"}, timeout=120)
            data = r.json()
            self.all_servers = data if isinstance(data, list) else data.get("result", data.get("servers", data.get("data", [])))
            _filter_state["servers"] = self.all_servers
            log.info("Fetched %d servers", len(self.all_servers))
            GLib.idle_add(self._update_version_filter)
            GLib.idle_add(self._update_map_filter)
            GLib.idle_add(self.apply_filters)
            GLib.idle_add(self._fetch_done)
        except Exception as e:
            log.error("Failed to fetch server list: %s", e)
            GLib.idle_add(self._fetch_done, f"Failed to load servers: {e}")

    def apply_filters(self):
        q = self.search.get_text().lower() if hasattr(self, "search") else ""
        iq = self.ip_search.get_text().strip() if hasattr(self, "ip_search") else ""
        mi = self.f_map.get_selected()
        vi = self.f_version.get_selected() if hasattr(self, "f_version") else 0
        fav_ips = {server_key(f) for f in self.favorites}
        played_lookup = recent_map()
        played_ips = set(played_lookup.keys())
        versions = _filter_state.get("versions", ["Any"])
        out = []
        for s in self.all_servers:
            nm = s.get("name", "").lower()
            mp = s.get("map", "").lower()
            pl = s.get("players", 0)
            mod = bool(s.get("mods")) or s.get("modded", False)
            fpp = s.get("firstPersonOnly") or s.get("firstperson", False)
            pw = s.get("password") or s.get("hasPassword", False)
            ip = s.get("ip") or s.get("endpoint", {}).get("ip", "")
            port = s.get("port") or s.get("gamePort") or s.get("endpoint", {}).get("port", 0)
            key = (ip, port)
            is_fav = key in fav_ips
            if q and q not in nm and q not in mp:
                continue
            if iq and iq not in ip:
                continue
            if mi > 0:
                map_ids = _filter_state.get("map_ids", [])
                if mi < len(map_ids):
                    mid = map_ids[mi]
                    if is_map_filter_active(mid) and mp != mid:
                        continue
            if vi > 0 and vi < len(versions):
                if not s.get("version", "").startswith(versions[vi]):
                    continue
            if self.chk["favonly"].get_active() and not is_fav:
                continue
            if self.chk["noplayed"].get_active() and key in played_ips:
                continue
            if self.chk["nopass"].get_active() and pw:
                continue
            if self.chk["nomodded"].get_active() and mod:
                continue
            if self.chk["firstperson"].get_active() and not fpp:
                continue
            if self.chk["thirdperson"].get_active() and fpp:
                continue
            if self.chk["online"].get_active() and pl == 0:
                continue
            out.append(s)

        self.sort_key, self.sort_rev = parse_sort_mode(self.sort_mode)

        def sort_val(s):
            if self.sort_key == "name":
                return s.get("name", "").lower()
            if self.sort_key == "map":
                return normalize_map_name(s.get("map")).lower()
            if self.sort_key == "players":
                return s.get("players", 0)
            if self.sort_key == "ping":
                return s.get("ping") if s.get("ping") is not None else 9999
            if self.sort_key == "time":
                return s.get("time") or ""
            if self.sort_key == "played":
                return played_lookup.get(server_key(s), 0)
            if self.sort_key == "version":
                return s.get("version") or ""
            return 0

        out.sort(key=sort_val, reverse=self.sort_rev)
        visible = out[:500]
        clear_box(self.srv_box)
        self._expand_tracker[0] = None  # rows are being recreated, drop stale reference
        if not visible:
            el = Gtk.Label(label="No servers match your filters.")
            el.add_css_class("empty")
            el.set_margin_top(60)
            self.srv_box.append(el)
        else:
            for s in visible:
                ip = s.get("ip") or s.get("endpoint", {}).get("ip", "")
                port = s.get("port") or s.get("gamePort") or s.get("endpoint", {}).get("port", 0)
                self.srv_box.append(ServerRow(
                    s, self.connect_cb, self.fav_cb, (ip, port) in fav_ips,
                    self.load_mods_cb, self.set_status, played_lookup=played_lookup,
                    expand_tracker=self._expand_tracker))
        self.set_status(f"Showing {len(visible):,} of {len(self.all_servers):,} servers")
        self._start_ping(visible[:80])

    def _start_ping(self, servers):
        self._ping_generation += 1
        generation = self._ping_generation
        threading.Thread(
            target=self._ping_batch,
            args=(servers, generation),
            daemon=True,
        ).start()

    def _ping_batch(self, servers, generation):
        ping_servers(servers)
        if generation == self._ping_generation:
            GLib.idle_add(self._refresh_pings)

    def _refresh_pings(self):
        row = self.srv_box.get_first_child()
        while row:
            if hasattr(row, "update_ping"):
                row.update_ping()
            row = row.get_next_sibling()