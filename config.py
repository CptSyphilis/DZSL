import os, json, re, subprocess

CONFIG_FILE = os.path.expanduser("~/.config/dzsl/config.json")
FAVS_FILE   = os.path.expanduser("~/.config/dzsl/favorites.json")
RECENT_FILE = os.path.expanduser("~/.config/dzsl/recent.json")

os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

def detect_steam_root():
    """Detect the Steam *library* root that contains the DayZ installation.
    Prefers the library that actually has steamapps/common/DayZ .
    Searches candidate paths + any additional libraries listed in Steam\'s libraryfolders.vdf .
    """
    candidates = [
        os.path.expanduser("~/.local/share/Steam"),
        os.path.expanduser("~/.steam/steam"),
        "/mnt/Storage1tb/SteamLibrary",
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
    # Prefer a lib that actually contains the DayZ game
    for p in libs:
        if os.path.isdir(os.path.join(p, "steamapps", "common", "DayZ")):
            return p
    # Fallback: first one that looks like a Steam library (has steamapps)
    for p in libs:
        if os.path.isdir(os.path.join(p, "steamapps")):
            return p
    return os.path.expanduser("~/.local/share/Steam")

def _detect_launcher():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "bin", "dayz-launcher.sh")

def _detect_steamcmd():
    bundled = os.path.expanduser("~/.config/dzsl/steamcmd/steamcmd.sh")
    if os.path.isfile(bundled):
        return bundled
    for path in ("/usr/games/steamcmd", "/usr/bin/steamcmd"):
        if os.path.isfile(path):
            return path
    return ""

DEFAULT_CFG = {
    "steam_root":    detect_steam_root(),
    "launcher_path": _detect_launcher(),
    "steamcmd_path": _detect_steamcmd(),
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

    # Flatpak Steam detection
    try:
        res = subprocess.run(
            ["flatpak", "ps", "--columns=application"],
            capture_output=True, text=True, timeout=3
        )
        if "com.valvesoftware.Steam" in (res.stdout or ""):
            return True
    except Exception:
        pass

    # Broader pgrep for any "steam" in cmdline (filter with _is_steam_client_process to exclude steamcmd and validate client)
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

    # Additional flatpak-specific pgrep (the actual process may show as bwrap or steam wrapper)
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

def _steam_library_paths(steam_root):
    paths = set()
    if steam_root and os.path.isdir(steam_root):
        paths.add(steam_root)
    for vdf in (
        os.path.expanduser("~/.local/share/Steam/steamapps/libraryfolders.vdf"),
        os.path.join(steam_root or "", "steamapps", "libraryfolders.vdf"),
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
        return cfg["mods_dir"]
    return f"{cfg['steam_root']}/steamapps/workshop/content/{DAYZ_APPID}"

def workshop_dirs(cfg):
    if cfg.get("mods_dir"):
        return [cfg["mods_dir"]]
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
        try:
            text = open(path, errors="ignore").read()
            idx = text.find("WorkshopItemsInstalled")
            if idx < 0:
                continue
            chunk = text[idx:]
            for match in re.finditer(r'"(\d{6,})"\s*\n\s*\{', chunk):
                ids.add(match.group(1))
        except OSError:
            pass
    return ids

def mod_subscribed(cfg, mod_id):
    return str(mod_id) in subscribed_mods(cfg)

def mod_installed(cfg, mod_id):
    mid = str(mod_id)
    for wd in workshop_dirs(cfg):
        if os.path.isdir(os.path.join(wd, mid)):
            return True
    return False

def get_installed_mods(cfg):
    wd = workshop_dir(cfg)
    mods = []
    if not os.path.isdir(wd): return mods
    for mid in sorted(os.listdir(wd)):
        path = os.path.join(wd, mid)
        if not os.path.isdir(path): continue
        name = mid
        meta = os.path.join(path, "meta.cpp")
        if os.path.exists(meta):
            try:
                for line in open(meta, errors="ignore"):
                    if "name" in line.lower() and "=" in line:
                        name = line.split("=")[-1].strip().strip('";\n'); break
            except: pass
        mods.append({"id": mid, "name": name, "path": path})
    return mods
