"""Direct DayZ mod setup and Steam launch helpers used by the GTK app."""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
from urllib.parse import quote

from dzsl.core.config import DAYZ_APPID, _steam_library_paths, steam_library_root, workshop_dirs

EXPERIMENTAL_APPID = "1024020"
from dzsl.steam.workshop import validate_mod_folder

class ModSetupError(RuntimeError):
    pass


def mod_link_name(mod_id):
    """Return the link name used by DayZ's -mod argument for a Workshop ID."""
    value = int(str(mod_id))
    raw = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "little")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return "@" + encoded


def dayz_dir(cfg):
    root = steam_library_root(cfg.get("steam_root", ""))
    return os.path.join(root, "steamapps", "common", "DayZ")


_version_cache = {"key": None, "version": ""}
_PRODUCT_VERSION = re.compile(rb"P\0r\0o\0d\0u\0c\0t\0V\0e\0r\0s\0i\0o\0n\0(?:\0\0)+((?:[0-9.]\0)+)")


# The exe's ProductVersion ("1.30.164200.56") matches the version servers report minus the last part.
def experimental_state(cfg):
    for lib in _steam_library_paths(cfg.get("steam_root", "")):
        acf = os.path.join(lib, "steamapps", f"appmanifest_{EXPERIMENTAL_APPID}.acf")
        try:
            text = open(acf, errors="ignore").read()
        except OSError:
            continue
        installdir = re.search(r'"installdir"\s*"([^"]+)"', text)
        flags = re.search(r'"StateFlags"\s*"(\d+)"', text)
        game_dir = os.path.join(lib, "steamapps", "common", installdir.group(1) if installdir else "DayZ Exp")
        ready = bool(flags) and int(flags.group(1)) == 4 and os.path.isfile(os.path.join(game_dir, "DayZ_x64.exe"))
        return ("installed" if ready else "downloading"), game_dir
    return "missing", ""


def same_major(a, b):
    return bool(a and b) and a.split(".")[:2] == b.split(".")[:2]


def installed_version(cfg, game_dir=None):
    exe = os.path.join(game_dir or dayz_dir(cfg), "DayZ_x64.exe")
    try:
        key = (exe, os.path.getmtime(exe))
    except OSError:
        return ""
    if _version_cache["key"] == key:
        return _version_cache["version"]
    version = ""
    try:
        with open(exe, "rb") as fh:
            match = _PRODUCT_VERSION.search(fh.read())
        if match:
            version = ".".join(match.group(1).decode("utf-16-le").split(".")[:3])
    except OSError:
        pass
    if not game_dir:
        _version_cache.update(key=key, version=version)
    return version


def cached_installed_version():
    return _version_cache["version"]


def _find_mod_dir(cfg, mod_id):
    mid = str(mod_id)
    for root in workshop_dirs(cfg):
        path = os.path.join(root, mid)
        if os.path.isdir(path):
            return path
    return ""


def _missing_mod_error(cfg, mod_id):
    # A custom mods folder overrides auto-detection entirely, so a mod that
    # Steam downloaded into its own library becomes invisible to DZSL. Point
    # at the setting instead of reporting the mod as missing outright.
    custom = cfg.get("mods_dir")
    if custom:
        for root in workshop_dirs({**cfg, "mods_dir": ""}):
            if validate_mod_folder(os.path.join(root, str(mod_id)))[0]:
                return (
                    f"Workshop mod {mod_id} is not in the custom mods folder "
                    f"({custom}) but Steam has it in {root} — fix or clear "
                    "'Custom Mods Folder' in Settings"
                )
    return f"Missing Workshop mod {mod_id}"


def setup_mod_links(cfg, mod_ids, game_dir=None):
    """Validate Workshop mods and ensure DayZ-relative symlinks exist."""
    game_dir = game_dir or dayz_dir(cfg)
    if not os.path.isdir(game_dir):
        raise ModSetupError(f"DayZ directory is missing: {game_dir}")

    links = []
    seen = set()
    for raw_id in mod_ids or []:
        mid = str(raw_id).strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        source = _find_mod_dir(cfg, mid)
        if not source:
            raise ModSetupError(_missing_mod_error(cfg, mid))
        valid, reason = validate_mod_folder(source)
        if not valid:
            raise ModSetupError(f"Invalid Workshop mod {mid}: {reason}")

        link_name = mod_link_name(mid)
        link_path = os.path.join(game_dir, link_name)
        relative_source = os.path.relpath(source, game_dir)
        if os.path.lexists(link_path):
            if not (os.path.islink(link_path) and os.readlink(link_path) == relative_source):
                if os.path.isdir(link_path) and not os.path.islink(link_path):
                    raise ModSetupError(f"Cannot replace real directory: {link_path}")
                os.unlink(link_path)
                os.symlink(relative_source, link_path)
        else:
            os.symlink(relative_source, link_path)

        # DayZ silently ignores -mod entries whose link does not reach real
        # PBO content, which ends in a server kick instead of an error here.
        valid, reason = validate_mod_folder(link_path)
        if not valid:
            raise ModSetupError(
                f"Mod link {link_name} for {mid} does not reach usable mod "
                f"content ({reason}): {link_path} -> {os.path.realpath(link_path)}"
            )
        links.append(link_name)
    return links


def steam_launch_prefix():
    steam = shutil.which("steam")
    if steam:
        return [steam]
    if shutil.which("flatpak"):
        try:
            running = subprocess.run(
                ["flatpak", "ps", "--columns=application"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if "com.valvesoftware.Steam" in (running.stdout or ""):
                return [
                    "flatpak", "run", "--branch=stable", "--arch=x86_64",
                    "--command=/app/bin/steam-wrapper", "com.valvesoftware.Steam",
                ]
        except (OSError, subprocess.SubprocessError):
            pass
    raise FileNotFoundError("Steam executable was not found")


def build_launch_command(server_address, mod_links, profile_name="", game_params=None, appid=DAYZ_APPID):
    arguments = build_launch_arguments(server_address, mod_links, profile_name, game_params)
    return steam_launch_prefix() + ["-applaunch", str(appid)] + arguments


def build_host_launch_command(server_address, mod_links, profile_name="", game_params=None, appid=DAYZ_APPID):
    arguments = build_launch_arguments(server_address, mod_links, profile_name, game_params)
    return ["flatpak-spawn", "--host", "steam", "-applaunch", str(appid)] + arguments


def build_launch_arguments(server_address, mod_links, profile_name="", game_params=None):
    arguments = []
    if mod_links:
        arguments.append("-mod=" + ";".join(mod_links))
    if server_address:
        arguments.extend([f"-connect={server_address}", "-nolauncher", "-world=empty"])
    if profile_name:
        arguments.append(f"-name={profile_name}")
    arguments.extend(game_params or [])
    return arguments


def launch_without_mods(cfg):
    from dzsl.runtime import is_flatpak, open_external_uri

    profile = (cfg.get("profile_name") or "").strip()
    params = ["-nolauncher", "-world=empty"]
    if is_flatpak():
        cmd = build_host_launch_command("", [], profile, params)
        try:
            if subprocess.run(cmd, capture_output=True, timeout=20).returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
        return open_external_uri(build_launch_uri("", [], profile, params))
    try:
        cmd = build_launch_command("", [], profile, params)
        return subprocess.run(cmd, capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def build_launch_uri(server_address, mod_links, profile_name="", game_params=None, appid=DAYZ_APPID):
    arguments = build_launch_arguments(server_address, mod_links, profile_name, game_params)
    encoded = quote(subprocess.list2cmdline(arguments), safe="")
    return f"steam://run/{appid}//{encoded}/"
