import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import requests, threading
from ui.server_row import ServerRow

API_URL = "https://dayzsalauncher.com/api/v1/launcher/servers/dayz"
MAP_KEYS = ["", "chernarus", "namalsk", "livonia", "deer isle", "takistan", "esseker", "banov", "enoch"]

class ServersView:
    def __init__(self, panel, cfg, favorites, connect_cb, fav_cb, set_status):
        self.panel       = panel
        self.cfg         = cfg
        self.favorites   = favorites
        self.connect_cb  = connect_cb
        self.fav_cb      = fav_cb
        self.set_status  = set_status
        self.all_servers = []
        self.sort_key    = "players"
        self.sort_rev    = True

    def build(self):
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        root.set_vexpand(True)

        # ── Left filter panel ────────────────────────────────────────────────
        fp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fp.add_css_class("filter-panel")
        fp.set_size_request(200, -1)

        def flbl(t):
            l = Gtk.Label(label=t); l.add_css_class("filter-label"); l.set_halign(Gtk.Align.START); return l

        fp.append(flbl("SEARCH"))
        self.search = Gtk.Entry(); self.search.set_placeholder_text("Server name...")
        self.search.add_css_class("search-box"); fp.append(self.search)

        fp.append(flbl("MAP"))
        self.f_map = Gtk.DropDown.new_from_strings(["Any", "Chernarus", "Namalsk", "Livonia", "Deer Isle", "Takistan", "Esseker", "Banov", "Enoch", "Other"])
        fp.append(self.f_map)

        fp.append(flbl("MAX PLAYERS"))
        self.f_maxp = Gtk.DropDown.new_from_strings(["Any", "≤ 10", "≤ 20", "≤ 40", "≤ 60", "60+"])
        fp.append(self.f_maxp)

        fp.append(flbl("FILTERS"))
        self.chk = {}
        for key, lbl in [
            ("favonly",    "Favourites only"),
            ("hasplayers", "Has players"),
            ("nopass",     "No password"),
            ("modded",     "Modded only"),
            ("vanilla",    "Vanilla only"),
            ("online",     "Online only"),
            ("firstperson","First person"),
            ("thirdperson","Third person"),
            ("battleye",   "BattlEye ON"),
            ("no_be",      "BattlEye OFF"),
        ]:
            cb = Gtk.CheckButton(label=lbl); cb.add_css_class("filter-check")
            cb.connect("toggled", lambda *a: self.apply_filters())
            self.chk[key] = cb; fp.append(cb)

        # Reset / Refresh
        sep = Gtk.Separator(); sep.set_margin_top(8); sep.set_margin_bottom(4); fp.append(sep)
        reset_btn = Gtk.Button(label="RESET"); reset_btn.add_css_class("btn-ghost")
        reset_btn.connect("clicked", self._reset_filters); fp.append(reset_btn)
        refresh_btn = Gtk.Button(label="REFRESH"); refresh_btn.add_css_class("toolbar-btn"); refresh_btn.add_css_class("accent")
        refresh_btn.connect("clicked", lambda b: self.fetch()); fp.append(refresh_btn)

        root.append(fp)

        # ── Right: header + table ────────────────────────────────────────────
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right.set_hexpand(True)

        # Column headers
        col_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        col_hdr.add_css_class("col-header")

        def col_btn(label, key, width=-1):
            b = Gtk.Button(label=label); b.add_css_class("col-btn")
            if width > 0: b.set_size_request(width, -1)
            b.connect("clicked", lambda _: self._sort_by(key)); return b

        self.col_btns = {}
        fav_col = Gtk.Label(label="FAV"); fav_col.add_css_class("col-label"); fav_col.set_size_request(40, -1); col_hdr.append(fav_col)
        name_b = col_btn("NAME  ↕", "name"); name_b.set_hexpand(True); col_hdr.append(name_b); self.col_btns["name"] = name_b
        col_hdr.append(col_btn("MAP  ↕",     "map",     120))
        col_hdr.append(col_btn("PLAYERS  ↕", "players", 90))
        col_hdr.append(col_btn("PING  ↕",    "ping",    70))
        col_hdr.append(col_btn("MODS  ↕",    "mods",    60))
        act_col = Gtk.Label(label=""); act_col.set_size_request(80, -1); col_hdr.append(act_col)
        right.append(col_hdr)

        # Server list
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.srv_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        loading = Gtk.Label(label="Loading servers..."); loading.add_css_class("empty"); loading.set_margin_top(60)
        self.srv_box.append(loading)
        scroll.set_child(self.srv_box); right.append(scroll)
        root.append(right)
        self.panel.append(root)

        self.search.connect("changed", lambda *a: self.apply_filters())
        self.f_map.connect("notify::selected", lambda *a: self.apply_filters())
        self.f_maxp.connect("notify::selected", lambda *a: self.apply_filters())
        self.fetch()

    def _sort_by(self, key):
        if self.sort_key == key: self.sort_rev = not self.sort_rev
        else: self.sort_key = key; self.sort_rev = True
        self.apply_filters()

    def _reset_filters(self, b=None):
        self.search.set_text("")
        self.f_map.set_selected(0)
        self.f_maxp.set_selected(0)
        for cb in self.chk.values(): cb.set_active(False)

    def fetch(self):
        self.set_status("Fetching server list...")
        threading.Thread(target=self._fetch_thread, daemon=True).start()

    def _fetch_thread(self):
        try:
            r = requests.get(API_URL, headers={"User-Agent": "DZSL/1.0"}, timeout=20)
            data = r.json()
            self.all_servers = data if isinstance(data, list) else data.get("result", data.get("servers", data.get("data", [])))
            total_players = sum(s.get("players", 0) for s in self.all_servers)
            self.set_status(f"{len(self.all_servers):,} servers  ·  {total_players:,} players online")
            GLib.idle_add(self.apply_filters)
        except Exception as e:
            self.set_status(f"Failed to load servers: {e}")

    def apply_filters(self):
        q   = self.search.get_text().lower() if hasattr(self, "search") else ""
        mi  = self.f_map.get_selected()
        mxi = self.f_maxp.get_selected()
        fav_ips = {(f.get("ip"), f.get("port")) for f in self.favorites}

        out = []
        for s in self.all_servers:
            nm  = s.get("name", "").lower()
            mp  = s.get("map", "").lower()
            pl  = s.get("players", 0)
            mxp = s.get("maxPlayers", s.get("maxplayers", 1)) or 1
            mod = bool(s.get("mods")) or s.get("modded", False)
            fp  = s.get("firstPersonOnly") or s.get("firstperson", False)
            pw  = s.get("password") or s.get("hasPassword", False)
            be  = s.get("battlEye", s.get("battleye", True))
            ip  = s.get("ip") or s.get("endpoint", {}).get("ip", "")
            port = s.get("port") or s.get("gamePort") or s.get("endpoint", {}).get("port", 0)
            is_fav = (ip, port) in fav_ips

            if q and q not in nm and q not in mp: continue
            if mi > 0:
                if mi < len(MAP_KEYS):
                    if MAP_KEYS[mi] not in mp: continue
                else:
                    if any(k in mp for k in MAP_KEYS[1:]): continue
            if mxi == 1 and mxp > 10:  continue
            if mxi == 2 and mxp > 20:  continue
            if mxi == 3 and mxp > 40:  continue
            if mxi == 4 and mxp > 60:  continue
            if mxi == 5 and mxp <= 60: continue

            if self.chk["favonly"].get_active()    and not is_fav: continue
            if self.chk["hasplayers"].get_active() and pl == 0:    continue
            if self.chk["nopass"].get_active()     and pw:         continue
            if self.chk["modded"].get_active()     and not mod:    continue
            if self.chk["vanilla"].get_active()    and mod:        continue
            if self.chk["online"].get_active()     and pl == 0:    continue
            if self.chk["firstperson"].get_active()  and not fp:   continue
            if self.chk["thirdperson"].get_active()  and fp:       continue
            if self.chk["battleye"].get_active()   and not be:     continue
            if self.chk["no_be"].get_active()      and be:         continue

            out.append(s)

        # Sort
        def sort_val(s):
            if self.sort_key == "name":    return s.get("name", "").lower()
            if self.sort_key == "map":     return s.get("map", "").lower()
            if self.sort_key == "players": return s.get("players", 0)
            if self.sort_key == "ping":    return s.get("ping") or 9999
            if self.sort_key == "mods":    return len(s.get("mods", []))
            return 0
        out.sort(key=sort_val, reverse=self.sort_rev)

        # Populate
        c = self.srv_box.get_first_child()
        while c: n = c.get_next_sibling(); self.srv_box.remove(c); c = n

        if not out:
            el = Gtk.Label(label="No servers match your filters."); el.add_css_class("empty"); el.set_margin_top(60); self.srv_box.append(el)
        else:
            fav_set = {(f.get("ip"), f.get("port")) for f in self.favorites}
            for s in out[:500]:
                ip   = s.get("ip") or s.get("endpoint", {}).get("ip", "")
                port = s.get("port") or s.get("gamePort") or s.get("endpoint", {}).get("port", 0)
                self.srv_box.append(TableRow(s, self.connect_cb, self.fav_cb, (ip, port) in fav_set))

        self.set_status(f"Showing {min(len(out), 500):,} of {len(self.all_servers):,} servers")


class TableRow(Gtk.Box):
    def __init__(self, s, on_connect, on_fav, is_fav):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add_css_class("table-row")

        ip   = s.get("ip") or s.get("endpoint", {}).get("ip", "")
        port = s.get("port") or s.get("gamePort") or s.get("endpoint", {}).get("port", "")
        mods = s.get("mods", [])
        mod  = bool(mods) or s.get("modded", False)
        fp   = s.get("firstPersonOnly") or s.get("firstperson", False)
        pw   = s.get("password") or s.get("hasPassword", False)
        be   = s.get("battlEye", s.get("battleye", True))
        pl   = s.get("players", 0)
        mxp  = s.get("maxPlayers", s.get("maxplayers", 0))
        ping = s.get("ping")

        # Fav star
        fb = Gtk.Button(label="*" if is_fav else "o")
        fb.add_css_class("fav-star" if is_fav else "fav-star-empty")
        fb.set_size_request(40, -1)
        fb.connect("clicked", lambda b: on_fav(s, b))
        self.append(fb)

        # Name + details
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.set_hexpand(True)
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nl = Gtk.Label(label=s.get("name", "Unknown")); nl.add_css_class("srv-name")
        nl.set_halign(Gtk.Align.START); nl.set_ellipsize(3); top.append(nl)
        if pw:
            lock = Gtk.Label(label="🔒"); lock.add_css_class("tag"); lock.add_css_class("tag-pass"); top.append(lock)
        if not be:
            nobe = Gtk.Label(label="NO BE"); nobe.add_css_class("tag"); nobe.add_css_class("tag-van"); top.append(nobe)
        info.append(top)
        if mods:
            mod_names = ", ".join(m.get("name", "") for m in mods[:4])
            if len(mods) > 4: mod_names += f" +{len(mods)-4} more"
            ml = Gtk.Label(label=mod_names); ml.add_css_class("srv-detail")
            ml.set_halign(Gtk.Align.START); ml.set_ellipsize(3); info.append(ml)
        else:
            dl = Gtk.Label(label=f"{ip}:{port}"); dl.add_css_class("srv-detail"); dl.set_halign(Gtk.Align.START); info.append(dl)
        self.append(info)

        # Map
        map_lbl = Gtk.Label(label=s.get("map", "?"))
        map_lbl.add_css_class("srv-detail"); map_lbl.set_size_request(120, -1); map_lbl.set_halign(Gtk.Align.CENTER)
        self.append(map_lbl)

        # Players
        fp_tag = " 1PP" if fp else ""
        pl_lbl = Gtk.Label(label=f"{pl}/{mxp}{fp_tag}")
        pl_lbl.add_css_class("srv-players"); pl_lbl.set_size_request(90, -1); pl_lbl.set_halign(Gtk.Align.CENTER)
        self.append(pl_lbl)

        # Ping
        ping_txt = f"{ping}" if ping else "—"
        if ping and ping < 80:   ping_cls = "ping-good"
        elif ping and ping < 150: ping_cls = "ping-ok"
        else: ping_cls = "ping-bad"
        ping_lbl = Gtk.Label(label=ping_txt); ping_lbl.add_css_class(ping_cls)
        ping_lbl.set_size_request(70, -1); ping_lbl.set_halign(Gtk.Align.CENTER)
        self.append(ping_lbl)

        # Mod count
        mc_lbl = Gtk.Label(label=str(len(mods)) if mods else "—")
        mc_lbl.add_css_class("srv-detail"); mc_lbl.set_size_request(60, -1); mc_lbl.set_halign(Gtk.Align.CENTER)
        self.append(mc_lbl)

        # Connect button
        cb = Gtk.Button(label="JOIN"); cb.add_css_class("btn-connect")
        cb.set_size_request(80, -1)
        cb.connect("clicked", lambda b: on_connect(s))
        self.append(cb)
