import subprocess
import threading
import time
import webbrowser

from config import mod_installed, mod_subscribed, mod_subscribed_per_steam_log
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
        log.info("Subscribing via Steam: %s (%s)", mod_name or mid, mid)
        return self.forward_steam_uri(f"steam://installworkshop/221100/{mid}")

    def open_workshop_page(self, mod_id, mod_name):
        mid = str(mod_id)
        log.warning(
            "Auto-subscribe unresponsive for %s (%s); opening Workshop page",
            mod_name,
            mid,
        )
        self.set_status(
            f"Opened Steam Workshop page for {mod_name} - click Subscribe there to continue."
        )
        webbrowser.open(f"https://steamcommunity.com/sharedfiles/filedetails/?id={mid}")

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
        start = time.time()
        step = 2
        steps = 3600 // step
        fallback_opened = False

        for _ in range(steps):
            elapsed = int(time.time() - start)
            if progress and progress.is_cancelled():
                log.info("Wait for %s cancelled after %ds", mod_name, elapsed)
                return False

            self.refresh_cfg()
            if mod_installed(self.cfg, mid):
                log.info("%s installed after %ds", mod_name, elapsed)
                return True

            subscribed = mod_subscribed(self.cfg, mid) or mod_subscribed_per_steam_log(mid)
            opened_fallback_now = False
            if progress and progress.continue_requested():
                if subscribed:
                    log.info("User advanced past %s after subscription confirmation", mod_name)
                    progress.clear_continue()
                    return True

                log.warning("Next-mod click for %s ignored; not subscribed yet", mod_name)
                progress.clear_continue()
                progress.set_hint(f"Not subscribed yet in Steam - click Subscribe first for:\n{mod_name}")
                if not fallback_opened and elapsed >= 10:
                    fallback_opened = True
                    opened_fallback_now = True
                    self.open_workshop_page(mid, mod_name)
                    notify_check_steam()

            elif elapsed and elapsed % 3600 == 0 and not subscribed:
                log.warning("No progress on %s after %ds; resending subscribe URI", mod_name, elapsed)
                self.subscribe_mod_steam(mid, mod_name)

            if progress:
                if opened_fallback_now:
                    progress.set_action_prompt(f"Click Subscribe in Steam for:\n{mod_name}")
                else:
                    progress.set_action_prompt(f"Waiting for download: {mod_name}")
                if size_bytes:
                    progress.set_mod_progress(mid, 0.0, None, size_bytes)

            time.sleep(step)

        ok = mod_installed(self.cfg, mid)
        if not ok:
            log.error("Timed out waiting for %s after %ds", mod_name, int(time.time() - start))
        return ok
