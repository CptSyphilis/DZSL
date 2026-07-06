import subprocess
import threading
import time

from dzsl.core.config import (
    mod_download_progress,
    mod_installed,
    mod_staging_signature,
    mod_subscribed,
)
from dzsl.core.logging import get_logger
from dzsl.runtime import is_flatpak
from dzsl.steam.api import SteamWorkshopAPI
from dzsl.ui.helpers import forward_steam_uri

log = get_logger("subscribe")

STEAM_ITEM_SUBSCRIBED = 1
STEAM_ITEM_LEGACY = 2
STEAM_ITEM_INSTALLED = 4
STEAM_ITEM_NEEDS_UPDATE = 8
STEAM_ITEM_DOWNLOADING = 16
STEAM_ITEM_DOWNLOAD_PENDING = 32


def steam_progress_phase(
    bytes_done,
    bytes_total,
    stalled_seconds,
    manifest_delayed=False,
    steam_state=0,
):
    if steam_state & (STEAM_ITEM_NEEDS_UPDATE | STEAM_ITEM_DOWNLOAD_PENDING):
        if steam_state & STEAM_ITEM_DOWNLOADING:
            return "Steam is staging download"
        return "Steam is paused in Steam"
    if not bytes_total:
        return "Waiting for Steam progress"
    if bytes_done >= bytes_total:
        return "Steam is installing files"
    if stalled_seconds >= 30:
        return "Steam is paused or waiting"
    if manifest_delayed:
        return "Steam is downloading (live progress in Steam)"
    return "Steam is staging download"


def launch_steam():
    if is_flatpak():
        return forward_steam_uri("steam://open/main")
    proc = subprocess.Popen(
        ["steam"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )

    def _log_stderr():
        for line in proc.stderr:
            line = line.strip()
            if line:
                log.warning("steam: %s", line)

    threading.Thread(target=_log_stderr, daemon=True).start()


class SteamSubscriptionManager:
    def __init__(
        self,
        cfg_provider,
        refresh_cfg,
        set_status,
        is_steam_running,
        wait_for_steam_start,
        launch_steam,
    ):
        self.cfg_provider = cfg_provider
        self.refresh_cfg = refresh_cfg
        self.set_status = set_status
        self.is_steam_running = is_steam_running
        self.wait_for_steam_start = wait_for_steam_start
        self.launch_steam = launch_steam
        self._native_api = None
        self._native_lock = threading.RLock()

    @property
    def cfg(self):
        return self.cfg_provider()

    def forward_steam_uri(self, uri):
        return forward_steam_uri(uri)

    def open_steam_downloads(self):
        return self.forward_steam_uri("steam://open/downloads")

    def subscribe_mod_steam(self, mod_id, mod_name=None):
        mid = str(mod_id)
        log.info("Queueing through Steam: %s (%s)", mod_name or mid, mid)
        if is_flatpak():
            return self.forward_steam_uri(f"steam://installworkshop/221100/{mid}")
        return self._queue_native(mid, mod_name)

    def _queue_native(self, mod_id, mod_name=None):
        api = self._native_session()
        if not api:
            return False
        needs_subscription = not mod_subscribed(self.cfg, mod_id)
        if not api.queue_download(mod_id, subscribe=needs_subscription):
            log.error(
                "Steamworks queue failed for %s: %s",
                mod_name or mod_id,
                api.error or "Steam rejected the request",
            )
            return False
        return True

    def _native_session(self):
        with self._native_lock:
            if self._native_api:
                return self._native_api
            api = SteamWorkshopAPI()
            if not api.initialize():
                log.error("Steamworks is unavailable: %s", api.error)
                api.close()
                return None
            self._native_api = api
            return api

    def close_native_session(self):
        with self._native_lock:
            if self._native_api:
                self._native_api.close()
                self._native_api = None

    def suspend_downloads(self):
        if is_flatpak():
            return False
        api = self._native_session()
        return bool(api and api.suspend_downloads(True))

    def steam_item_status(self, mod_id):
        if is_flatpak():
            return 0, (0, 0)
        api = self._native_session()
        if not api:
            return 0, (0, 0)
        return api.item_state(mod_id), api.download_info(mod_id)

    def sync_steam_subscriptions(self, mod_ids, start_if_needed=True):
        ids = [str(mid) for mid in mod_ids or []]
        if not ids:
            return
        if start_if_needed and not self.is_steam_running():
            self.set_status("Starting Steam to subscribe mods...")
            self.launch_steam()
            self.wait_for_steam_start(iterations=20, ready_sleep=2)
        if not self.is_steam_running():
            return
        for mid in ids:
            self.subscribe_mod_steam(mid, mid)

    def wait_for_mod_installed(self, mod_id, progress, mod_name, size_bytes=0):
        mid = str(mod_id)
        self.set_status(f"Waiting for {mod_name} download...")
        start = time.time()
        last_bytes = 0
        last_activity = start
        last_staging = (0, 0)
        next_subscribe_retry = 15
        step = 2
        while True:
            now = time.time()
            elapsed = int(now - start)
            if progress and progress.is_cancelled():
                log.info("Wait for %s cancelled after %ds", mod_name, elapsed)
                return False

            self.refresh_cfg()
            subscribed = mod_subscribed(self.cfg, mid)
            if mod_installed(self.cfg, mid):
                log.info("%s installed and current after %ds", mod_name, elapsed)
                return True

            steam_state, steam_progress = self.steam_item_status(mid)
            steam_bytes_done, steam_bytes_total = steam_progress
            bytes_done, bytes_total = mod_download_progress(self.cfg, mid)
            if steam_bytes_total:
                bytes_done, bytes_total = steam_progress
            elif steam_bytes_done and not bytes_done:
                bytes_done = steam_bytes_done
            if bytes_done != last_bytes:
                last_bytes = bytes_done
                last_activity = now
            staging = mod_staging_signature(self.cfg, mid)
            staging_active = staging != last_staging and staging != (0, 0)
            if staging_active:
                last_activity = now
            last_staging = staging
            if elapsed >= next_subscribe_retry and not subscribed and not bytes_total and staging == (0, 0):
                log.warning("Steam still has not queued %s after %ds; retrying", mod_name, elapsed)
                self.subscribe_mod_steam(mid, mod_name)
                next_subscribe_retry += 30

            if progress:
                steam_downloading = bool(steam_state & STEAM_ITEM_DOWNLOADING)
                steam_paused = bool(steam_state & (STEAM_ITEM_NEEDS_UPDATE | STEAM_ITEM_DOWNLOAD_PENDING))
                if steam_paused and not steam_downloading:
                    progress.set_mod_status(mid, "Paused in Steam", "active")
                    progress.set_action_prompt(f"Paused in Steam: {mod_name}")
                    time.sleep(step)
                    continue
                manifest_delayed = staging[0] > bytes_done + 16 * 1024 * 1024
                stalled = now - last_activity
                if manifest_delayed and stalled < 30:
                    progress.set_mod_activity(mid)
                else:
                    fraction = bytes_done / bytes_total if bytes_total else 0.0
                    progress.set_mod_progress(mid, fraction, bytes_done, bytes_total)
                phase = steam_progress_phase(
                    bytes_done,
                    bytes_total,
                    stalled,
                    manifest_delayed,
                    steam_state=steam_state,
                )
                progress.set_action_prompt(f"{phase}: {mod_name}")

            time.sleep(step)
