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
from dzsl.steam.api import run_workshop_helper
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


def effective_progress(bytes_done, bytes_total, staging_allocated, size_hint):
    """Fill in progress from staged bytes while the manifest lags behind.

    Steam flushes BytesDownloaded/BytesToDownload to the workshop manifest
    lazily; small mods can finish before the fields ever appear. The bytes
    Steam has staged on disk, measured against the size the web API reported,
    give a usable estimate until the manifest catches up.
    """
    if not bytes_total and size_hint and staging_allocated:
        return min(staging_allocated, size_hint), size_hint
    return bytes_done, bytes_total


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
        return self._queue_native(mid, mod_name)

    def _queue_native(self, mod_id, mod_name=None):
        # Native Workshop calls run in a disposable subprocess: a process that
        # initialises Steamworks for AppID 221100 counts as "playing DayZ"
        # until it exits, and Steam drops DayZ launch requests while it does.
        ok, error = run_workshop_helper("download", [mod_id])
        if not ok:
            log.error(
                "Steamworks queue failed for %s: %s",
                mod_name or mod_id,
                error or "Steam rejected the request",
            )
            return False
        return True

    def queue_mods(self, mod_ids):
        ids = [str(mid) for mid in mod_ids or []]
        if not ids:
            return True
        ok, error = run_workshop_helper("download", ids, timeout=max(30, 2 * len(ids)))
        if not ok:
            log.error("Steamworks queue failed for %d mod(s): %s", len(ids), error or "Steam rejected the request")
        return ok

    def close_native_session(self):
        # Native sessions live in short-lived helper subprocesses now, so the
        # main process never holds one. Kept for the connector's pre-launch
        # safety call.
        return False

    def suspend_downloads(self):
        ok, error = run_workshop_helper("suspend")
        if not ok and error:
            log.error("Could not suspend Workshop downloads: %s", error)
        return ok

    def cancel_downloads(self, mod_ids):
        # SuspendDownloads only holds while the calling process lives, so a
        # helper's suspend lifts the moment it exits and Steam resumes.
        # Unsubscribing is the one cancel signal Steam honours afterwards.
        ids = [str(mid) for mid in mod_ids or []]
        if not ids:
            return True
        ok, error = run_workshop_helper("unsubscribe", ids)
        if not ok and error:
            log.error("Could not cancel Workshop downloads: %s", error)
        return ok

    def steam_item_status(self, mod_id):
        # Progress and state come from Steam's workshop ACF manifests
        # (mod_download_progress / mod_staging_signature); querying the live
        # item state would need an in-process Steamworks session, which would
        # mark DZSL as a running DayZ instance.
        return 0, (0, 0)

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
            staging = mod_staging_signature(self.cfg, mid)
            staging_active = staging != last_staging and staging != (0, 0)
            bytes_done, bytes_total = effective_progress(
                bytes_done, bytes_total, staging[0], size_bytes
            )
            if bytes_done != last_bytes:
                last_bytes = bytes_done
                last_activity = now
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
