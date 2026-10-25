from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import time

from dzsl.core.logging import get_logger


log = get_logger("steam_api")

_BUNDLED_LIB = os.path.join(os.path.dirname(__file__), "redist", "libsteam_api.so")

class SteamWorkshopAPI:
    def __init__(self, app_id="221100"):
        self.app_id = str(app_id)
        self.lib = None
        self.ugc = None
        self.lock = threading.RLock()
        self.error = ""
        self._previous_app_env = None

    def _set_app_environment(self):
        self._previous_app_env = {
            "SteamAppId": os.environ.get("SteamAppId"),
            "SteamGameId": os.environ.get("SteamGameId"),
        }
        os.environ["SteamAppId"] = self.app_id
        os.environ["SteamGameId"] = self.app_id

    def _restore_app_environment(self):
        if self._previous_app_env is None:
            return
        for key, value in self._previous_app_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._previous_app_env = None

    def _library_candidates(self):
        configured = os.environ.get("DZSL_STEAM_API")
        candidates = [
            configured,
            _BUNDLED_LIB,
            os.path.expanduser("~/.local/share/Steam/steamrt64/libsteam_api.so"),
            os.path.expanduser("~/.steam/root/steamrt64/libsteam_api.so"),
            os.path.expanduser(
                "~/.var/app/com.valvesoftware.Steam/data/Steam/steamrt64/libsteam_api.so"
            ),
        ]
        return [path for path in candidates if path and os.path.isfile(path)]

    def initialize(self):
        with self.lock:
            if self.ugc:
                return True
            candidates = self._library_candidates()
            if not candidates:
                self.error = "Steam API library was not found"
                return False
            self._set_app_environment()
            try:
                self.lib = ctypes.CDLL(candidates[0])
                self._set_signatures()
                error = ctypes.create_string_buffer(1024)
                result = self.lib.SteamAPI_InitFlat(error)
                if result != 0:
                    self.error = error.value.decode("utf-8", "replace") or f"Steam init error {result}"
                    self.lib = None
                    self._restore_app_environment()
                    return False
                self.ugc = self.lib.SteamAPI_SteamUGC_v021()
                if not self.ugc:
                    self.error = "Steam Workshop interface is unavailable"
                    self.lib.SteamAPI_Shutdown()
                    self.lib = None
                    self._restore_app_environment()
                    return False
                log.info("Native Steam Workshop API ready")
                return True
            except (OSError, AttributeError) as exc:
                self.error = str(exc)
                self.lib = None
                self.ugc = None
                self._restore_app_environment()
                return False

    def _set_signatures(self):
        lib = self.lib
        lib.SteamAPI_InitFlat.argtypes = [ctypes.c_char_p]
        lib.SteamAPI_InitFlat.restype = ctypes.c_int
        lib.SteamAPI_SteamUGC_v021.restype = ctypes.c_void_p
        lib.SteamAPI_ISteamUGC_SubscribeItem.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        lib.SteamAPI_ISteamUGC_SubscribeItem.restype = ctypes.c_uint64
        lib.SteamAPI_ISteamUGC_DownloadItem.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_bool]
        lib.SteamAPI_ISteamUGC_DownloadItem.restype = ctypes.c_bool
        lib.SteamAPI_ISteamUGC_SuspendDownloads.argtypes = [ctypes.c_void_p, ctypes.c_bool]
        lib.SteamAPI_ISteamUGC_SuspendDownloads.restype = None
        lib.SteamAPI_ISteamUGC_UnsubscribeItem.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        lib.SteamAPI_ISteamUGC_UnsubscribeItem.restype = ctypes.c_uint64

    def subscribe(self, mod_id):
        with self.lock:
            if not self.initialize():
                return False
            call = self.lib.SteamAPI_ISteamUGC_SubscribeItem(self.ugc, int(mod_id))
            self.lib.SteamAPI_RunCallbacks()
            return bool(call)

    def queue_download(self, mod_id, subscribe=False):
        with self.lock:
            if not self.initialize():
                return False
            subscribed = True
            if subscribe:
                subscribed = bool(
                    self.lib.SteamAPI_ISteamUGC_SubscribeItem(self.ugc, int(mod_id))
                )
                self.lib.SteamAPI_RunCallbacks()
            self.lib.SteamAPI_ISteamUGC_SuspendDownloads(self.ugc, False)
            queued = self.lib.SteamAPI_ISteamUGC_DownloadItem(
                self.ugc, int(mod_id), True
            )
            self.lib.SteamAPI_RunCallbacks()
            return subscribed and bool(queued)

    def suspend_downloads(self, suspend=True):
        with self.lock:
            if not self.initialize():
                return False
            self.lib.SteamAPI_ISteamUGC_SuspendDownloads(self.ugc, bool(suspend))
            self.lib.SteamAPI_RunCallbacks()
            return True

    def unsubscribe(self, mod_id):
        with self.lock:
            if not self.initialize():
                return False
            call = self.lib.SteamAPI_ISteamUGC_UnsubscribeItem(self.ugc, int(mod_id))
            self.lib.SteamAPI_RunCallbacks()
            return bool(call)

    def close(self):
        with self.lock:
            if self.lib:
                self.lib.SteamAPI_Shutdown()
            self.lib = None
            self.ugc = None
            self._restore_app_environment()


def _flatpak_app_path():
    try:
        with open("/.flatpak-info") as fh:
            for line in fh:
                if line.startswith("app-path="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def run_workshop_helper(command, mod_ids=(), timeout=30):
    """Run a native Workshop call in a short-lived subprocess.

    Steam treats any process that initialises the Steamworks API for AppID
    221100 as a running DayZ session until that process *exits* —
    SteamAPI_Shutdown alone does not end the session, which makes Steam
    silently drop real DayZ launch requests. Doing every native call in a
    disposable helper keeps the main DZSL process clean.

    Returns (ok, error_text).
    """
    cmd = [sys.executable, "-m", "dzsl.steam.api", command]
    app_path = _flatpak_app_path()
    if app_path:
        cmd = ["flatpak-spawn", "--host", f"--env=PYTHONPATH={app_path}/lib/dzsl", "python3", "-m", "dzsl.steam.api", command]
    cmd.extend(str(mid) for mid in mod_ids)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return proc.returncode == 0, (proc.stderr or "").strip()


def _workshop_command(command, mod_ids):
    api = SteamWorkshopAPI()
    try:
        if command == "suspend":
            if not api.suspend_downloads(True):
                if api.error:
                    print(api.error, file=sys.stderr)
                return 1
        for mod_id in mod_ids:
            if not mod_id.isdigit():
                return 1
            if command == "subscribe":
                ok = api.subscribe(mod_id)
            elif command == "download":
                ok = api.queue_download(mod_id, subscribe=True)
            elif command == "unsubscribe":
                ok = api.unsubscribe(mod_id)
            else:
                return 2
            if not ok:
                if api.error:
                    print(api.error, file=sys.stderr)
                return 1
        if not api.lib:
            return 0
        deadline = time.monotonic() + 0.75
        while time.monotonic() < deadline:
            api.lib.SteamAPI_RunCallbacks()
            time.sleep(0.05)
        return 0
    finally:
        api.close()


if __name__ == "__main__":
    _commands = {"subscribe", "unsubscribe", "download", "suspend"}
    if (
        len(sys.argv) < 2
        or sys.argv[1] not in _commands
        or (sys.argv[1] != "suspend" and len(sys.argv) < 3)
    ):
        print(
            "usage: steam_api.py subscribe|unsubscribe|download MOD_ID [MOD_ID ...] | suspend",
            file=sys.stderr,
        )
        raise SystemExit(2)
    raise SystemExit(_workshop_command(sys.argv[1], sys.argv[2:]))
