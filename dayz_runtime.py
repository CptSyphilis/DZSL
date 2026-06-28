"""Direct DayZ mod setup and Steam launch helpers used by the GTK app."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess

from config import DAYZ_APPID, steam_library_root, workshop_dirs
from steam_workshop import validate_mod_folder


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


def _find_mod_dir(cfg, mod_id):
    mid = str(mod_id)
    for root in workshop_dirs(cfg):
        path = os.path.join(root, mid)
        if os.path.isdir(path):
            return path
    return ""


def setup_mod_links(cfg, mod_ids):
    """Validate Workshop mods and ensure DayZ-relative symlinks exist."""
    game_dir = dayz_dir(cfg)
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
            raise ModSetupError(f"Missing Workshop mod {mid}")
        valid, reason = validate_mod_folder(source)
        if not valid:
            raise ModSetupError(f"Invalid Workshop mod {mid}: {reason}")

        link_name = mod_link_name(mid)
        link_path = os.path.join(game_dir, link_name)
        relative_source = os.path.relpath(source, game_dir)
        if os.path.lexists(link_path):
            if os.path.islink(link_path) and os.readlink(link_path) == relative_source:
                links.append(link_name)
                continue
            if os.path.isdir(link_path) and not os.path.islink(link_path):
                raise ModSetupError(f"Cannot replace real directory: {link_path}")
            os.unlink(link_path)
        os.symlink(relative_source, link_path)
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


def build_launch_command(server_address, mod_links, profile_name="", game_params=None):
    command = steam_launch_prefix() + ["-applaunch", DAYZ_APPID]
    if mod_links:
        command.append("-mod=" + ";".join(mod_links))
    if server_address:
        command.extend([f"-connect={server_address}", "-nolauncher", "-world=empty"])
    if profile_name:
        command.append(f"-name={profile_name}")
    command.extend(game_params or [])
    return command
