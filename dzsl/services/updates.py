import os
import re

from dzsl.core.config import get_installed_mods, workshop_acf_paths
from dzsl.core.constants import VERSION
from dzsl.http import get_json, get_text
from dzsl.services.listings import _base_url
from dzsl.steam.web_api import published_file_details
from dzsl.steam.workshop import item_record

REMOTE_VERSION_URL = "https://raw.githubusercontent.com/CptSyphilis/DZSL/main/dzsl/core/constants.py"


def outdated_mods(cfg, timeout=15):
    mods = get_installed_mods(cfg)
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
            stale.append(mod)
    return stale


def _version_tuple(value):
    return tuple(int(part) for part in re.findall(r"\d+", value)[:3])


def app_update_available(timeout=8):
    text = get_text(REMOTE_VERSION_URL, timeout=timeout)
    match = re.search(r'VERSION\s*=\s*"([^"]+)"', text)
    if not match:
        return None
    remote = match.group(1)
    if _version_tuple(remote) > _version_tuple(VERSION):
        return remote
    return None


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
