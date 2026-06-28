import os, json, re, subprocess

from steam_workshop import item_download_progress, item_ready, item_record, validate_mod_folder

CONFIG_FILE = os.path.expanduser("~/.config/dzsl/config.json")
FAVS_FILE   = os.path.expanduser("~/.config/dzsl/favorites.json")
RECENT_FILE = os.path.expanduser("~/.config/dzsl/recent.json")
FILTERS_FILE = os.path.expanduser("~/.config/dzsl/filters.json")

os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

def detect_steam_root():
    candidates = [
        os.path.expanduser("~/.local/share/Steam"),
        os.path.expanduser("~/.steam/steam"),
        os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam"),
        "/mnt/games/SteamLibrary",
        "/opt/steam",
        os.path.expanduser("~/Steam"),
    ]
    seen = set()
    libs = []
    for p in candidates:
        if p and p not in seen and os.path.isdir(p):
            seen.add(p)
            libs.append(p)
    # Discover more from common libraryfolders.vdf files
    vdf_locations = [
        os.path.expanduser("~/.local/share/Steam/steamapps/libraryfolders.vdf"),
        os.path.expanduser("~/.steam/steam/steamapps/libraryfolders.vdf"),
    ]
    for vdf in vdf_locations:
        if not os.path.isfile(vdf):
            continue
        try:
            text = open(vdf, errors="ignore").read()
            for m in re.finditer(r'"path"\s*"([^"]+)"', text):
                p = m.group(1).replace("\\\\", "/")
                if p and p not in seen and os.path.isdir(p):
                    seen.add(p)
                    libs.append(p)
        except Exception:
            pass
    for p in libs:
        if (os.path.isfile(os.path.join(p, "steamapps", "appmanifest_221100.acf"))
                and os.path.isdir(os.path.join(p, "steamapps", "common", "DayZ"))):
            return p
    for p in libs:
        if (os.path.isfile(os.path.join(p, "steamapps", "appmanifest_221100.acf"))
                or os.path.isdir(os.path.join(p, "steamapps", "common", "DayZ"))):
            return p
    for p in libs:
        if os.path.isdir(os.path.join(p, "steamapps")):
            return p
    return os.path.expanduser("~/.local/share/Steam")

def _detect_launcher():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "bin", "dayz-launcher.sh")

def resolve_launcher_path(configured=""):
    path = os.path.abspath(os.path.expanduser(configured or ""))
    if os.path.isfile(path):
        return path
    return _detect_launcher()

DEFAULT_CFG = {
    "steam_root":    detect_steam_root(),
    "launcher_path": _detect_launcher(),
    "mods_dir":      "",
    "profile_name":  "",
    "extra_args":    "",
    "extra_mods":    "",
    "no_splash":     True,
    "no_pause":      True,
    "no_benchmark":  False,
    "window_mode":   False,
    "script_debug":  False,
    "skip_battleye": False,
    "close_on_launch": True,
    "download_max_chunks": 1,
    "download_speed_kbps": 0,
    "download_backend": "steam",
    "download_parallel": 1,
    "window_width":  1280,
    "window_height": 780,
    "window_maximized": True,
}

def load_cfg():
    if os.path.exists(CONFIG_FILE):
        try:
            d = json.load(open(CONFIG_FILE))
            return {**DEFAULT_CFG, **d}
        except: pass
    return dict(DEFAULT_CFG)

def save_cfg(cfg):
    json.dump(cfg, open(CONFIG_FILE, "w"), indent=2)

def load_json(path):
    if os.path.exists(path):
        try: return json.load(open(path))
        except: pass
    return []

def save_json(path, data):
    json.dump(data, open(path, "w"), indent=2)

STEAM_PID_FILE = os.path.expanduser("~/.steam/steam.pid")
STEAM_CLIENT_BIN = os.path.expanduser("~/.steam/root/ubuntu12_32/steam")

def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False

def _process_cmdline(pid):
    try:
        return open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "ignore")
    except OSError:
        return ""

def _is_steam_client_process(pid):
    cmd = _process_cmdline(pid).lower()
    if not cmd or "steamcmd" in cmd:
        return False
    markers = (
        ".local/share/steam",
        "steam/ubuntu12",
        "/.steam/root",
    )
    return any(m in cmd for m in markers) or cmd.rstrip().endswith("/steam")

def is_steam_running():
    """True when the Steam client is running (not steamcmd or stale pid files)."""
    try:
        with open(STEAM_PID_FILE) as f:
            pid = int(f.read().strip())
        if pid > 0 and _pid_alive(pid) and _is_steam_client_process(pid):
            return True
    except (OSError, ValueError):
        pass

    if os.path.isfile(STEAM_CLIENT_BIN):
        result = subprocess.run(
            ["pgrep", "-f", STEAM_CLIENT_BIN],
            capture_output=True,
        )
        if result.returncode == 0:
            return True

    result = subprocess.run(["pgrep", "-x", "steam"], capture_output=True, text=True)
    if result.returncode == 0:
        for pid in result.stdout.split():
            if _is_steam_client_process(pid):
                return True

    try:
        res = subprocess.run(
            ["flatpak", "ps", "--columns=application"],
            capture_output=True, text=True, timeout=3
        )
        if "com.valvesoftware.Steam" in (res.stdout or ""):
            return True
    except Exception:
        pass
        
    try:
        res = subprocess.run(
            ["pgrep", "-f", "steam"],
            capture_output=True, text=True, timeout=3
        )
        if res.returncode == 0:
            for pid in res.stdout.strip().split():
                if pid and _is_steam_client_process(pid):
                    return True
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["pgrep", "-f", "com.valvesoftware.Steam|flatpak.*steam"],
            capture_output=True, text=True, timeout=3
        )
        if res.returncode == 0:
            for pid in res.stdout.strip().split():
                if pid and _is_steam_client_process(pid):
                    return True
    except Exception:
        pass

    return False

DAYZ_APPID = "221100"

def steam_library_root(path):
    path = os.path.abspath(os.path.expanduser(path or ""))
    if os.path.basename(path) == "steamapps":
        return os.path.dirname(path)
    return path

def _steam_library_paths(steam_root):
    paths = set()
    root = steam_library_root(steam_root)
    if root and os.path.isdir(root):
        paths.add(root)
    for vdf in (
        os.path.expanduser("~/.local/share/Steam/steamapps/libraryfolders.vdf"),
        os.path.join(root or "", "steamapps", "libraryfolders.vdf"),
    ):
        if not os.path.isfile(vdf):
            continue
        try:
            text = open(vdf, errors="ignore").read()
            for match in re.finditer(r'"path"\s*"([^"]+)"', text):
                p = match.group(1).replace("\\\\", "/")
                if os.path.isdir(p):
                    paths.add(p)
        except OSError:
            pass
    return sorted(paths)

def workshop_dir(cfg):
    if cfg.get("mods_dir"):
        return os.path.abspath(os.path.expanduser(cfg["mods_dir"]))
    root = steam_library_root(cfg.get("steam_root", ""))
    return os.path.join(root, "steamapps", "workshop", "content", DAYZ_APPID)

def workshop_dirs(cfg):
    if cfg.get("mods_dir"):
        return [os.path.abspath(os.path.expanduser(cfg["mods_dir"]))]
    dirs = []
    seen = set()
    for lib in _steam_library_paths(cfg.get("steam_root", "")):
        wd = os.path.join(lib, "steamapps", "workshop", "content", DAYZ_APPID)
        if wd not in seen and os.path.isdir(wd):
            dirs.append(wd)
            seen.add(wd)
    if not dirs:
        wd = workshop_dir(cfg)
        if wd not in seen:
            dirs.append(wd)
    return dirs

def workshop_acf_paths(cfg):
    paths = []
    seen = set()
    for lib in _steam_library_paths(cfg.get("steam_root", "")):
        path = os.path.join(lib, "steamapps", "workshop", f"appworkshop_{DAYZ_APPID}.acf")
        if path not in seen and os.path.isfile(path):
            paths.append(path)
            seen.add(path)
    return paths

def subscribed_mods(cfg):
    ids = set()
    for path in workshop_acf_paths(cfg):
        from steam_workshop import read_manifest

        details = read_manifest(path).get("WorkshopItemDetails", {})
        ids.update(mid for mid, record in details.items() if record.get("subscribedby"))
    return ids

def mod_subscribed(cfg, mod_id):
    return item_record(workshop_acf_paths(cfg), mod_id)["subscribed"]

def mod_download_progress(cfg, mod_id):
    return item_download_progress(workshop_acf_paths(cfg), mod_id)

WORKSHOP_LOG_CANDIDATES = [
    os.path.expanduser("~/.local/share/Steam/logs/workshop_log.txt"),
    os.path.expanduser("~/.steam/steam/logs/workshop_log.txt"),
    os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/Steam/logs/workshop_log.txt"),
]

def mod_subscribed_per_steam_log(mod_id):
    needle = f"Subscribed to item {mod_id}"
    for path in WORKSHOP_LOG_CANDIDATES:
        try:
            if needle in open(path, errors="ignore").read():
                return True
        except OSError:
            continue
    return False

def mod_installed(cfg, mod_id):
    mid = str(mod_id)
    manifests = workshop_acf_paths(cfg)
    if manifests:
        record = item_record(manifests, mid)
        if record.get("installed"):
            return item_ready(manifests, workshop_dirs(cfg), mid)
    for wd in workshop_dirs(cfg):
        path = os.path.join(wd, mid)
        if validate_mod_folder(path)[0]:
            return True
    return False

def find_corrupt_mods(cfg):
    corrupt = []
    for wd in workshop_dirs(cfg):
        if not os.path.isdir(wd):
            continue
        for mid in os.listdir(wd):
            path = os.path.join(wd, mid)
            if not os.path.isdir(path) or not mid.isdigit():
                continue
            if not validate_mod_folder(path)[0]:
                corrupt.append(path)
    return corrupt

def _mod_name_from_path(path, mid):
    name = mid
    meta = os.path.join(path, "meta.cpp")
    if os.path.exists(meta):
        try:
            for line in open(meta, errors="ignore"):
                if "name" in line.lower() and "=" in line:
                    name = line.split("=")[-1].strip().strip('";\n')
                    break
        except OSError:
            pass
    return name

def get_installed_mods(cfg):
    mods = []
    seen = set()
    for wd in workshop_dirs(cfg):
        if not os.path.isdir(wd):
            continue
        for mid in sorted(os.listdir(wd)):
            path = os.path.join(wd, mid)
            if not os.path.isdir(path) or mid in seen:
                continue
            seen.add(mid)
            mods.append({"id": mid, "name": _mod_name_from_path(path, mid), "path": path})
    return mods
