"""Read Steam Workshop state from Steam's local KeyValues manifests."""

from __future__ import annotations

import os
import re


_TOKEN = re.compile(r'"((?:\\.|[^"\\])*)"|([{}])')


def parse_keyvalues(text):
    """Parse the subset of Valve KeyValues used by Steam ACF files."""
    tokens = []
    for match in _TOKEN.finditer(text):
        if match.group(2):
            tokens.append(match.group(2))
        else:
            value = match.group(1).replace(r'\"', '"').replace(r'\\', '\\')
            tokens.append(value)

    def parse_object(index, nested=False):
        result = {}
        while index < len(tokens):
            token = tokens[index]
            if token == "}":
                return result, index + 1
            if token == "{":
                raise ValueError("unexpected opening brace")
            key = token
            index += 1
            if index >= len(tokens):
                raise ValueError(f"missing value for {key}")
            if tokens[index] == "{":
                value, index = parse_object(index + 1, nested=True)
            else:
                value = tokens[index]
                index += 1
            result[key] = value
        if nested:
            raise ValueError("unclosed object")
        return result, index

    parsed, _ = parse_object(0)
    return parsed


def read_manifest(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            root = parse_keyvalues(handle.read())
    except (OSError, ValueError):
        return {}
    return root.get("AppWorkshop", root)


def item_record(paths, mod_id):
    """Merge one item's installed and subscription records across libraries."""
    mid = str(mod_id)
    merged = {"subscribed": False, "installed": None, "details": None}
    for path in paths:
        manifest = read_manifest(path)
        installed = manifest.get("WorkshopItemsInstalled", {}).get(mid)
        details = manifest.get("WorkshopItemDetails", {}).get(mid)
        if installed:
            merged["installed"] = installed
        if details:
            merged["details"] = details
            if details.get("subscribedby"):
                merged["subscribed"] = True
    return merged


def item_download_progress(paths, mod_id):
    record = item_record(paths, mod_id)
    details = record.get("details") or {}
    try:
        downloaded = int(details.get("BytesDownloaded", 0))
        total = int(details.get("BytesToDownload", 0))
    except (TypeError, ValueError):
        return 0, 0
    return downloaded, total


def folder_has_content(path):
    if not os.path.isdir(path):
        return False
    try:
        return any(not name.startswith(".") for name in os.listdir(path))
    except OSError:
        return False


def validate_mod_folder(path):
    """Validate the minimum on-disk structure required by a DayZ mod."""
    if not os.path.isdir(path):
        return False, "mod folder is missing"

    found_pbo = False
    for root, dirs, files in os.walk(path):
        dirs[:] = [name for name in dirs if not name.startswith(".")]
        for name in files:
            if not name.lower().endswith(".pbo"):
                continue
            found_pbo = True
            try:
                if os.path.getsize(os.path.join(root, name)) > 0:
                    return True, ""
            except OSError:
                continue

    if found_pbo:
        return False, "all PBO payload files are empty or unreadable"
    return False, "no PBO payload files were found"


def item_ready(paths, folders, mod_id):
    mid = str(mod_id)
    record = item_record(paths, mid)
    installed = record.get("installed") or {}
    details = record.get("details") or {}
    if not installed:
        return False
    current = installed.get("manifest")
    latest = details.get("latest_manifest")
    if current and latest and current != latest:
        return False
    return any(validate_mod_folder(os.path.join(folder, mid))[0] for folder in folders)
