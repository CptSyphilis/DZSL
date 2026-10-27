import os
import re
import shlex
import subprocess

from dzsl.core.config import get_installed_mods, workshop_acf_paths
from dzsl.core.constants import VERSION
from dzsl.http import download_file, get_json
from dzsl.services.listings import _base_url
from dzsl.steam.web_api import published_file_details
from dzsl.steam.workshop import item_record

APP_ID = "com.dayzlinux.dzsl"


def outdated_mods(cfg, timeout=15, mod_ids=None):
    mods = get_installed_mods(cfg)
    if mod_ids is not None:
        wanted = {str(mid) for mid in mod_ids}
        mods = [m for m in mods if m["id"] in wanted]
    if not mods:
        return []
    manifests = workshop_acf_paths(cfg)
    details = {
        str(d.get("publishedfileid")): d
        for d in published_file_details([m["id"] for m in mods], timeout=timeout)
    }
    stale = []
    for mod in mods:
        remote = int((details.get(mod["id"]) or {}).get("time_updated", 0) or 0)
        if not remote:
            continue
        installed = item_record(manifests, mod["id"]).get("installed") or {}
        local = int(installed.get("timeupdated", 0) or 0)
        if not local:
            try:
                local = int(os.path.getmtime(mod["path"]))
            except OSError:
                continue
        if remote > local:
            stale.append({**mod, "time_updated": remote})
    return stale


def _version_tuple(value):
    return tuple(int(part) for part in re.findall(r"\d+", value)[:3])


def app_update_available(timeout=8):
    data = get_json(f"{_base_url()}/version.json", timeout=timeout)
    remote = str(data.get("version") or "") if isinstance(data, dict) else ""
    if remote and _version_tuple(remote) > _version_tuple(VERSION):
        return {"version": remote, "force": bool(data.get("force"))}
    return None


def _cache_dir():
    path = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "dzsl")
    os.makedirs(path, exist_ok=True)
    return path


def update_failed():
    marker = os.path.join(_cache_dir(), "update-failed")
    if os.path.exists(marker):
        os.remove(marker)
        return True
    return False


def download_app_update(progress=None):
    dest = os.path.join(_cache_dir(), "dzsl-update.flatpak")
    download_file(f"{_base_url()}/download/dzsl.flatpak", dest, progress, timeout=60)
    return dest


def install_app_update_and_restart(bundle):
    cache = _cache_dir()
    q = shlex.quote
    script = (
        f"sleep 2; "
        f"flatpak install --user -y --noninteractive --reinstall --bundle {q(bundle)} >{q(cache + '/update.log')} 2>&1 "
        f"|| touch {q(cache + '/update-failed')}; "
        f"rm -f {q(bundle)}; "
        f"flatpak run {APP_ID}"
    )
    subprocess.Popen(
        ["flatpak-spawn", "--host", "setsid", "sh", "-c", script],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


# Release notes for this version and older, plus operator notices, newest first.
def fetch_changelog(timeout=8):
    data = get_json(f"{_base_url()}/changelog.json", timeout=timeout)
    entries = data.get("entries") if isinstance(data, dict) else None
    out = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("notice") and isinstance(entry.get("text"), str):
            out.append({"notice": True, "date": str(entry.get("date") or ""), "text": entry["text"]})
        elif isinstance(entry.get("version"), str) and _version_tuple(entry["version"]) <= _version_tuple(VERSION):
            items = [str(i) for i in entry.get("items") or [] if isinstance(i, str)]
            out.append({"version": entry["version"], "date": str(entry.get("date") or ""), "items": items})
    return out
