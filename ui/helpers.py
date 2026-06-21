import os
import subprocess
import threading
import time
from config import load_json, load_cfg, mod_subscribed, is_steam_running, RECENT_FILE

def transient_window(widget):
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    w = widget
    while w:
        if isinstance(w, Gtk.Window):
            return w
        w = w.get_parent()
    app = Gtk.Application.get_default()
    if app:
        return app.get_active_window()
    return None


def clear_box(box):
    """Remove all children from a Gtk container using the first_child / sibling walk."""
    c = box.get_first_child()
    while c:
        n = c.get_next_sibling()
        box.remove(c)
        c = n


def server_key(server):
    ip = server.get("ip") or server.get("endpoint", {}).get("ip")
    port = server.get("port") or server.get("gamePort") or server.get("gameport") or server.get("endpoint", {}).get("port")
    return ip, port

def recent_map():
    out = {}
    for entry in load_json(RECENT_FILE):
        ip, port = server_key(entry)
        if ip:
            out[(ip, port)] = entry.get("joined_at")
    return out

def format_played(ts):
    if not ts:
        return ""
    try:
        delta = max(0, time.time() - float(ts))
    except (TypeError, ValueError):
        return ""
    if delta < 3600:
        return "just now"
    if delta < 86400:
        h = int(delta / 3600)
        return f"{h} hour{'s' if h != 1 else ''} ago"
    days = int(delta / 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"

def format_server_time(server):
    t = server.get("time")
    if not t:
        return "—"
    accel = server.get("timeAcceleration")
    suffix = f" ({accel})" if accel else ""
    return f"{t}{suffix}"

def server_tags(server):
    tags = []
    mods = server.get("mods") or []
    if mods:
        tags.append(f"{len(mods)} mods")
    ver = server.get("version", "")
    if ver:
        tags.append(f"v{ver.split('.')[0]}.{ver.split('.')[1]}" if "." in ver else f"v{ver}")
    if server.get("firstPersonOnly") or server.get("firstperson"):
        tags.append("1PP")
    if not server.get("battlEye", server.get("battleye", True)):
        tags.append("No BE")
    return tags

def format_server_subtitle(server):
    ip = server.get("ip") or server.get("endpoint", {}).get("ip", "?")
    port = server.get("port") or server.get("gamePort") or server.get("endpoint", {}).get("port", 2302)
    return f"{ip}:{port}"

_MAP_NAMES = {
    "chernarusplus": "Chernarus",
    "chernarusplusgloom": "Chernarus Gloom",
    "chernarus2035": "Chernarus 2035",
    "chernarus": "Chernarus",
    "namalsk": "Namalsk",
    "enoch": "Livonia",
    "livonia": "Livonia",
    "deerisle": "Deer Isle",
    "takistan": "Takistan",
    "takistanplus": "Takistan",
    "esseker": "Esseker",
    "banov": "Banov",
    "banovfrost": "Banov Frost",
    "sakhal": "Sakhal",
    "bitterroot": "Bitterroot",
    "pripyat": "Pripyat",
    "nhchernobyl": "NH Chernobyl",
    "alteria": "Alteria",
    "deadfall": "Deadfall",
    "exclusionzone": "Exclusion Zone",
    "exclusionzoneplus": "Exclusion Zone+",
    "lux": "Lux",
    "hashima": "Hashima",
    "chiemsee": "Chiemsee",
    "pnw": "PNW",
    "greencounty": "Green County",
    "melkart": "Melkart",
    "melkart_v2": "Melkart V2",
    "eternal": "Eternal",
    "novikostok": "Novikostok",
    "siberia": "Siberia",
    "nyheim": "Nyheim",
    "raman": "Raman",
    "thezone": "The Zone",
    "avalon": "Avalon",
    "rostow": "Rostow",
    "sahrani": "Sahrani",
    "anastara": "Anastara",
    "yiprit": "Yiprit",
    "stuartisland": "Stuart Island",
    "arsteinen": "Arsteinen",
    "arsteinen_snow": "Arsteinen Snow",
    "swansisland": "Swans Island",
    "barrington": "Barrington",
    "valning": "Valning",
    "eden": "Eden",
    "channel": "Channel",
    "onforin": "Onforin",
    "newyork": "New York",
    "sanfranciscobayarea": "San Francisco Bay",
    "bearisland": "Bear Island",
    "newisland": "New Island",
    "sarov": "Sarov",
    "iceshaft": "Ice Shaft",
    "badg_nyheim": "Badg Nyheim",
    "fenix_emptiness": "Fenix Emptiness",
    "nachtigallmap": "Nachtigall",
}

def map_display_name(m):
    raw = (m or "?").strip()
    if not raw or raw == "?":
        return "?"
    key = raw.lower().replace(" ", "").replace("_", "")
    if key in _MAP_NAMES:
        return _MAP_NAMES[key]
    for token, name in sorted(_MAP_NAMES.items(), key=lambda x: -len(x[0])):
        if token in key:
            return name
    cleaned = raw.replace("_", " ").replace("-", " ")
    return cleaned.title()

def normalize_map_name(m):
    return map_display_name(m)

MAP_HEADER_OFFICIAL = "__header_official__"
MAP_HEADER_COMMUNITY = "__header_community__"

OFFICIAL_MAP_IDS = {
    "chernarusplus",
    "chernarus",
    "enoch",
    "livonia",
    "sakhal",
}

def _map_key(raw):
    return (raw or "").strip().lower().replace(" ", "").replace("_", "")

def is_official_map(map_id):
    return _map_key(map_id) in OFFICIAL_MAP_IDS

def is_map_filter_active(map_id):
    return bool(map_id) and not str(map_id).startswith("__header_")

def is_map_header_label(label):
    return (label or "").startswith("──")

SORT_OPTIONS = [
    ("players_desc", "Players (high → low)"),
    ("players_asc", "Players (low → high)"),
    ("name_asc", "Name (A → Z)"),
    ("name_desc", "Name (Z → A)"),
    ("map_asc", "Map (A → Z)"),
    ("ping_asc", "Ping (best first)"),
    ("ping_desc", "Ping (worst first)"),
    ("time_asc", "In-game time"),
    ("played_desc", "Recently played"),
    ("version_desc", "Version (newest)"),
]

def parse_sort_mode(mode):
    modes = {
        "players_desc": ("players", True),
        "players_asc": ("players", False),
        "name_asc": ("name", False),
        "name_desc": ("name", True),
        "map_asc": ("map", False),
        "ping_asc": ("ping", False),
        "ping_desc": ("ping", True),
        "time_asc": ("time", False),
        "played_desc": ("played", True),
        "version_desc": ("version", True),
    }
    return modes.get(mode, ("players", True))

def sort_mode_for_key(key, reverse):
    for mode, (sort_key, sort_rev) in {
        m: parse_sort_mode(m) for m, _ in SORT_OPTIONS
    }.items():
        if sort_key == key and sort_rev == reverse:
            return mode
    return "players_desc"

def build_map_filter_options(servers):
    counts = {}
    for s in servers or []:
        mid = (s.get("map") or "").strip().lower()
        if mid:
            counts[mid] = counts.get(mid, 0) + 1

    official = []
    community = []
    for mid, count in counts.items():
        opt = {"id": mid, "label": map_display_name(mid), "count": count}
        (official if is_official_map(mid) else community).append(opt)

    official.sort(key=lambda o: (-o["count"], o["label"].lower()))
    community.sort(key=lambda o: (-o["count"], o["label"].lower()))
    return official, community

def build_map_dropdown(official, community):
    labels = ["Any"]
    ids = [""]
    if official:
        labels.append("── Official maps ──")
        ids.append(MAP_HEADER_OFFICIAL)
        for o in official:
            labels.append(f"{o['label']} ({o['count']:,})")
            ids.append(o["id"])
    if community:
        labels.append("── Community maps ──")
        ids.append(MAP_HEADER_COMMUNITY)
        for o in community:
            labels.append(f"{o['label']} ({o['count']:,})")
            ids.append(o["id"])
    return labels, ids

def mod_ids_from_server(server):
    ids = []
    seen = set()
    for m in filter_server_mods(server.get("mods") or []):
        mid = str(m.get("steamWorkshopId") or m.get("id") or "").strip()
        if mid and mid not in seen:
            seen.add(mid)
            ids.append(mid)
    return ids

def subscribed_mod_ids_from_server(server, cfg=None):
    cfg = cfg or load_cfg()
    return [mid for mid in mod_ids_from_server(server) if mod_subscribed(cfg, mid)]

def forward_steam_uri(uri):
    remote = os.path.expanduser(
        "~/.steam/root/ubuntu12_32/steam-runtime/amd64/usr/bin/steam-runtime-steam-remote"
    )
    handlers = []
    handlers.append(["steam", uri])
    steam_bin = os.path.expanduser("~/.steam/root/ubuntu12_32/steam")
    if os.path.isfile(steam_bin):
        handlers.append([steam_bin, uri])
    if os.path.isfile(remote):
        handlers.append([remote, uri])
    handlers.append(["flatpak", "run", "--branch=stable", "--arch=x86_64", "--command=steam", "com.valvesoftware.Steam", uri])
    for cmd in handlers:
        if not cmd:
            continue
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"[DZSL] steam uri -> {' '.join(cmd[:1])}: {uri}", flush=True)
            return True
        except OSError:
            continue
    return False

def unsubscribe_mod_ids(mod_ids):
    for mid in mod_ids:
        forward_steam_uri(f"steam://unsubscribe/{mid}")
        time.sleep(0.35)

def prompt_unsubscribe_server_mods(parent, server, set_status=None):
    import gi
    gi.require_version("Adw", "1")
    from gi.repository import Adw, GLib

    cfg = load_cfg()
    all_ids = mod_ids_from_server(server)
    if not all_ids:
        if set_status:
            set_status("No workshop mods listed for this server.")
        return

    ids = subscribed_mod_ids_from_server(server, cfg)
    if not ids:
        if set_status:
            set_status("You are not subscribed to any of this server's mods.")
        return

    name = server.get("name", "This server")
    steam_up = is_steam_running()

    win = transient_window(parent)
    if not win:
        if set_status:
            set_status("Could not open dialog — window not ready.")
        return

    d = Adw.MessageDialog(transient_for=win)
    d.set_heading("Unsubscribe server mods?")
    body = f"Unsubscribe from {len(ids)} subscribed workshop mod(s) for:\n{name}"
    if len(ids) < len(all_ids):
        body += f"\n\n({len(all_ids) - len(ids)} other server mod(s) are not subscribed.)"
    if steam_up:
        body += "\n\nRequires Steam to be running and logged in."
    else:
        body += "\n\nSteam is not running — start Steam first, then try again."
    d.set_body(body)
    d.add_response("cancel", "Cancel")
    if steam_up:
        d.add_response("unsub", "Unsubscribe")
        d.set_response_appearance("unsub", Adw.ResponseAppearance.DESTRUCTIVE)
    d.set_default_response("cancel")
    d.set_close_response("cancel")

    def on_response(dialog, response):
        dialog.destroy()
        if response != "unsub":
            return
        if not is_steam_running():
            if set_status:
                set_status("Steam is not running — start Steam and try again.")
            return
        if set_status:
            set_status(f"Unsubscribing from {len(ids)} mod(s)…")

        def work():
            unsubscribe_mod_ids(ids)
            if set_status:
                GLib.idle_add(set_status, f"Unsubscribed from {len(ids)} mod(s) for {name}")

        threading.Thread(target=work, daemon=True).start()

    d.connect("response", on_response)
    d.present()

def filter_server_mods(mods):
    out = []
    for m in mods or []:
        name = (m.get("name") or "").strip()
        mid = m.get("steamWorkshopId") or m.get("id")
        low = name.lower()
        if low in ("battleeye on", "battleeye off", "battleye on", "battleye off"):
            continue
        if not name and not mid:
            continue
        out.append(m)
    return out
