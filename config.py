import os, json

CONFIG_FILE = os.path.expanduser("~/.config/dzsl/config.json")
FAVS_FILE   = os.path.expanduser("~/.config/dzsl/favorites.json")
RECENT_FILE = os.path.expanduser("~/.config/dzsl/recent.json")

os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

def _detect_steam_root():
    candidates = [
        os.path.expanduser("~/.local/share/Steam"),
        os.path.expanduser("~/.steam/steam"),
        "/mnt/Storage1tb/SteamLibrary",
        "/mnt/games/SteamLibrary",
    ]
    for p in candidates:
        if os.path.isdir(os.path.join(p, "steamapps")):
            return p
    return os.path.expanduser("~/.local/share/Steam")

def _detect_launcher():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "bin", "dayz-launcher.sh")

DEFAULT_CFG = {
    "steam_root":    _detect_steam_root(),
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

def workshop_dir(cfg):
    if cfg.get("mods_dir"): return cfg["mods_dir"]
    return f"{cfg['steam_root']}/steamapps/workshop/content/221100"

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
