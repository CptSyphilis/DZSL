import subprocess
import sys
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
from dzsl.ui.helpers import forward_steam_uri

log = get_logger("subscribe")


def steam_progress_phase(bytes_done, bytes_total, stalled_seconds, staging_active=False):
    if not bytes_total:
        return "Waiting for Steam progress"
    if bytes_done >= bytes_total:
        return "Steam is installing files"
    if staging_active and stalled_seconds >= 10:
        return "Steam is staging (progress delayed)"
    if stalled_seconds >= 30:
        return "Steam is paused or waiting"
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

    @property
    def cfg(self):
        return self.cfg_provider()

    def forward_steam_uri(self, uri):
        return forward_steam_uri(uri)

    def open_steam_downloads(self):
        return self.forward_steam_uri("steam://open/downloads")

    def subscribe_mod_steam(self, mod_id, mod_name=None):
        mid = str(mod_id)
        log.info("Subscribing through Steam: %s (%s)", mod_name or mid, mid)
        if not is_flatpak():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "dzsl.steam.api", "subscribe", mid],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode != 0:
                    error = (result.stderr or result.stdout or "helper failed").strip().splitlines()[-1]
                    log.error("Steam subscription failed: %s", error)
                    return False
            except (OSError, subprocess.SubprocessError) as exc:
                log.error("Steam subscription helper failed: %s", exc)
                return False
        return self.forward_steam_uri(f"steam://installworkshop/221100/{mid}")

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
        last_change = start
        last_staging = (0, 0)
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

            bytes_done, bytes_total = mod_download_progress(self.cfg, mid)
            if bytes_done != last_bytes:
                last_bytes = bytes_done
                last_change = now
            staging = mod_staging_signature(self.cfg, mid)
            staging_active = staging != last_staging and staging != (0, 0)
            last_staging = staging
            if elapsed and elapsed % 3600 == 0 and not subscribed:
                log.warning("No progress on %s after %ds; resending subscribe URI", mod_name, elapsed)
                self.subscribe_mod_steam(mid, mod_name)

            if progress:
                fraction = bytes_done / bytes_total if bytes_total else 0.0
                progress.set_mod_progress(mid, fraction, bytes_done, bytes_total)
                phase = steam_progress_phase(
                    bytes_done,
                    bytes_total,
                    now - last_change,
                    staging_active,
                )
                progress.set_action_prompt(f"{phase}: {mod_name}")

            time.sleep(step)
