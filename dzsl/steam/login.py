"""Local Steam account detection used by the startup login gate."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re

from dzsl.core.config import is_steam_ready
from dzsl.steam.workshop import parse_keyvalues


LOGIN_USERS_PATHS = (
    os.path.expanduser("~/.local/share/Steam/config/loginusers.vdf"),
    os.path.expanduser("~/.steam/steam/config/loginusers.vdf"),
    os.path.expanduser(
        "~/.var/app/com.valvesoftware.Steam/.local/share/Steam/config/loginusers.vdf"
    ),
)

CONNECTION_LOG_PATHS = (
    os.path.expanduser("~/.local/share/Steam/logs/connection_log.txt"),
    os.path.expanduser("~/.steam/steam/logs/connection_log.txt"),
    os.path.expanduser(
        "~/.var/app/com.valvesoftware.Steam/.local/share/Steam/logs/connection_log.txt"
    ),
)

_CONNECTION_STATE = re.compile(r"^\[[^\]]+\] \[(Logged On|Logged Off),", re.MULTILINE)


@dataclass(frozen=True)
class SteamAccount:
    steam_id: str
    account_name: str
    persona_name: str

    @property
    def display_name(self):
        return self.persona_name or self.account_name or self.steam_id


def read_login_account(paths=LOGIN_USERS_PATHS):
    """Return Steam's most-recent account from loginusers.vdf."""
    seen = set()
    for path in paths:
        real = os.path.realpath(path)
        if real in seen:
            continue
        seen.add(real)
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                users = parse_keyvalues(handle.read()).get("users", {})
        except (OSError, ValueError):
            continue

        candidates = []
        for steam_id, value in users.items():
            if not str(steam_id).isdigit() or not isinstance(value, dict):
                continue
            try:
                timestamp = int(value.get("Timestamp", 0) or 0)
            except (TypeError, ValueError):
                timestamp = 0
            candidates.append((value.get("MostRecent") == "1", timestamp, steam_id, value))
        if not candidates:
            continue

        _recent, _timestamp, steam_id, value = max(candidates)
        return SteamAccount(
            steam_id=str(steam_id),
            account_name=str(value.get("AccountName", "")).strip(),
            persona_name=str(value.get("PersonaName", "")).strip(),
        )
    return None


def connection_logged_on(paths=CONNECTION_LOG_PATHS):
    """Return the latest explicit Steam connection state, if available."""
    newest = None
    for path in paths:
        try:
            modified = os.path.getmtime(path)
            with open(path, "rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - 512 * 1024))
                text = handle.read().decode("utf-8", "replace")
        except OSError:
            continue
        matches = list(_CONNECTION_STATE.finditer(text))
        if matches and (newest is None or modified > newest[0]):
            newest = (modified, matches[-1].group(1) == "Logged On")
    return None if newest is None else newest[1]


def steam_login_account(
    ready_check=is_steam_ready,
    login_paths=LOGIN_USERS_PATHS,
    connection_paths=CONNECTION_LOG_PATHS,
):
    """Return the active Steam account only after the client is logged on."""
    if not ready_check():
        return None
    account = read_login_account(login_paths)
    if not account:
        return None
    return account if connection_logged_on(connection_paths) is True else None
