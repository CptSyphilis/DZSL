from __future__ import annotations

import ctypes
import os
import sys
import threading
import time

from dzsl.core.logging import get_logger


log = get_logger("steam_api")

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
        lib.SteamAPI_ISteamUGC_UnsubscribeItem.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        lib.SteamAPI_ISteamUGC_UnsubscribeItem.restype = ctypes.c_uint64

    def subscribe_and_download(self, mod_id):
        with self.lock:
            if not self.initialize():
                return False
            call = self.lib.SteamAPI_ISteamUGC_SubscribeItem(self.ugc, int(mod_id))
            self.lib.SteamAPI_RunCallbacks()
            queued = self.lib.SteamAPI_ISteamUGC_DownloadItem(self.ugc, int(mod_id), True)
            return bool(call) and bool(queued)

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


def _workshop_command(command, mod_ids):
    api = SteamWorkshopAPI()
    try:
        for mod_id in mod_ids:
            if command == "subscribe":
                ok = mod_id.isdigit() and api.subscribe_and_download(mod_id)
            else:
                ok = mod_id.isdigit() and api.unsubscribe(mod_id)
            if not ok:
                if api.error:
                    print(api.error, file=sys.stderr)
                return 1
        deadline = time.monotonic() + 0.75
        while time.monotonic() < deadline:
            api.lib.SteamAPI_RunCallbacks()
            time.sleep(0.05)
        return 0
    finally:
        api.close()


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in {"subscribe", "unsubscribe"}:
        print("usage: steam_api.py subscribe|unsubscribe MOD_ID [MOD_ID ...]", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(_workshop_command(sys.argv[1], sys.argv[2:]))
