import json
import os
import subprocess
import sys
import threading
import time

from config import mod_download_progress, mod_installed, mod_subscribed
from ui.helpers import forward_steam_uri, notify_check_steam
from applog import get_logger

log = get_logger("subscribe")


def launch_steam():
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
        helper = os.path.join(os.path.dirname(os.path.dirname(__file__)), "steam_api.py")
        try:
            result = subprocess.run(
                [sys.executable, helper, "subscribe", mid],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True
            error = (result.stderr or result.stdout or "helper failed").strip().splitlines()[-1]
            log.warning("Native Steam API helper failed: %s", error)
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("Native Steam API helper unavailable: %s", exc)
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
        notify_check_steam()
        for mid in ids:
            self.subscribe_mod_steam(mid, mid)

    def wait_for_mod_installed(self, mod_id, progress, mod_name, size_bytes=0):
        mid = str(mod_id)
        self.set_status(f"Waiting for {mod_name} download...")
        native_result = self._wait_with_native_monitor(mid, progress, mod_name, size_bytes)
        if native_result is not None:
            return native_result

        log.warning("Steam API monitor unavailable for %s; using Workshop manifest", mod_name)
        start = time.time()
        step = 2
        steps = 3600 // step
        for _ in range(steps):
            elapsed = int(time.time() - start)
            if progress and progress.is_cancelled():
                log.info("Wait for %s cancelled after %ds", mod_name, elapsed)
                return False

            self.refresh_cfg()
            subscribed = mod_subscribed(self.cfg, mid)
            if mod_installed(self.cfg, mid):
                log.info("%s installed and current after %ds", mod_name, elapsed)
                return True

            bytes_done, bytes_total = mod_download_progress(self.cfg, mid)
            if elapsed and elapsed % 3600 == 0 and not subscribed:
                log.warning("No progress on %s after %ds; resending subscribe URI", mod_name, elapsed)
                self.subscribe_mod_steam(mid, mod_name)

            if progress:
                progress.set_action_prompt(f"Waiting for download: {mod_name}")
                total = bytes_total or size_bytes
                fraction = bytes_done / total if total else 0.0
                progress.set_mod_progress(mid, fraction, bytes_done, total)
                if bytes_total and bytes_done < bytes_total:
                    progress.set_action_prompt(f"Steam is downloading: {mod_name}")

            time.sleep(step)

        ok = mod_installed(self.cfg, mid)
        if not ok:
            log.error("Timed out waiting for %s after %ds", mod_name, int(time.time() - start))
        return ok

    def _wait_with_native_monitor(self, mid, progress, mod_name, size_bytes):
        helper = os.path.join(os.path.dirname(os.path.dirname(__file__)), "steam_api.py")
        try:
            proc = subprocess.Popen(
                [sys.executable, helper, "monitor", mid],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except OSError:
            return None

        previous_bytes = 0
        previous_time = time.monotonic()
        received = False
        try:
            for line in proc.stdout:
                if progress and progress.is_cancelled():
                    proc.terminate()
                    proc.wait(timeout=5)
                    log.info("Wait for %s cancelled by user", mod_name)
                    return False
                try:
                    snapshot = json.loads(line)
                except json.JSONDecodeError:
                    continue
                received = True
                downloaded = int(snapshot.get("downloaded", 0) or 0)
                steam_total = int(snapshot.get("total", 0) or 0)
                total = steam_total or size_bytes
                fraction = downloaded / total if total else 0.0
                now = time.monotonic()
                if progress:
                    progress.set_mod_progress(mid, fraction, downloaded, total)
                    if snapshot.get("downloading"):
                        progress.set_mod_status(mid, f"{int(fraction * 100)}%", "active")
                        progress.set_action_prompt(f"Steam is downloading: {mod_name}")
                    elif snapshot.get("pending"):
                        progress.set_mod_status(mid, "Pending in Steam", "active")
                    elif snapshot.get("subscribed"):
                        progress.set_mod_status(mid, "Waiting for Steam", "active")
                    elapsed = now - previous_time
                    if downloaded > previous_bytes and elapsed >= 0.25:
                        rate = (downloaded - previous_bytes) / elapsed
                        progress.set_speed(self._format_rate(rate))
                previous_bytes, previous_time = downloaded, now
                if snapshot.get("installed") and not snapshot.get("needs_update"):
                    proc.wait(timeout=5)
                    log.info("%s installed and current according to Steam", mod_name)
                    return True
            proc.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            if proc.poll() is None:
                proc.terminate()
            return None if not received else False
        return None if not received else proc.returncode == 0

    @staticmethod
    def _format_rate(rate):
        if rate >= 1024 ** 2:
            return f"{rate / 1024 ** 2:.1f} MB/s"
        if rate >= 1024:
            return f"{rate / 1024:.1f} KB/s"
        return f"{rate:.0f} B/s"
