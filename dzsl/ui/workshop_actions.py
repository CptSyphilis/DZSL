import os
import shutil
import threading
import time

from gi.repository import GLib

from dzsl.core.config import (
    find_corrupt_mods,
    get_installed_mods,
    is_steam_running,
    load_cfg,
    mod_installed,
    workshop_dirs,
)
from dzsl.core.logging import get_logger
from dzsl.steam import gate as workshop_gate
from dzsl.ui.download import ModDownloadManager
from dzsl.ui.progress import ModProgressDialog
from dzsl.ui.subscribe import SteamSubscriptionManager, launch_steam

log = get_logger("workshop")


def _wait_for_steam_start(iterations=60, step=2, ready_sleep=2):
    for _ in range(iterations):
        if is_steam_running():
            time.sleep(ready_sleep)
            return True
        time.sleep(step)
    return False


class WorkshopActionRunner:
    def __init__(self, cfg, set_status, set_downloading=None):
        self.cfg = cfg
        self.set_status = set_status
        self.set_downloading = set_downloading or (lambda *_: None)
        self.subscriptions = SteamSubscriptionManager(
            lambda: self.cfg,
            self._refresh_cfg,
            self.set_status,
            is_steam_running,
            _wait_for_steam_start,
            launch_steam,
        )
        self.downloads = ModDownloadManager(
            lambda: self.cfg,
            self._refresh_cfg,
            self.set_status,
            self.subscriptions,
        )

    def _refresh_cfg(self):
        self.cfg = load_cfg()

    def _ensure_steam(self):
        if is_steam_running():
            return True
        self.set_status("Starting Steam...")
        try:
            launch_steam()
        except OSError as exc:
            log.error("Could not start Steam: %s", exc)
            self.set_status("Could not start Steam. Start Steam manually and try again.")
            return False
        if _wait_for_steam_start():
            self.set_status("Steam ready.")
            return True
        self.set_status("Steam did not start in time.")
        return False

    def _open_progress(self, mod_ids, names):
        progress = ModProgressDialog(
            mod_ids,
            names,
            on_open_downloads=self.subscriptions.open_steam_downloads,
        )
        self.set_downloading(True, progress)
        return progress

    def install_mods(
        self,
        mod_ids,
        names=None,
        label="Installing Workshop mods",
        repair=False,
        redownload=False,
    ):
        ids = [str(mid).strip() for mid in mod_ids or [] if str(mid).strip().isdigit()]
        names = names or {mid: mid for mid in ids}
        if not ids:
            self.set_status("No Workshop mods selected.")
            return
        acquired, active = workshop_gate.try_begin(label)
        if not acquired:
            self.set_status(f"Wait for the current Workshop operation to finish: {active}")
            return

        progress = self._open_progress(ids, names)
        try:
            threading.Thread(
                target=self._install_worker,
                args=(ids, names, label, repair, redownload, progress),
                daemon=True,
            ).start()
        except Exception:
            workshop_gate.finish()
            raise

    def verify_installed_mods(self):
        mods = get_installed_mods(self.cfg)
        if not mods:
            self.set_status("No Workshop mods found. Check Steam Library Root in Settings.")
            return
        ids = [m["id"] for m in mods]
        names = {m["id"]: m["name"] for m in mods}
        self.install_mods(ids, names, label=f"Verifying {len(ids)} Workshop mod(s)", repair=True)

    def _delete_corrupt_mods(self):
        corrupt = find_corrupt_mods(self.cfg)
        for path in corrupt:
            if os.path.isdir(path):
                log.warning("Removing corrupt Workshop mod before repair: %s", path)
                shutil.rmtree(path, ignore_errors=True)
        return len(corrupt)

    def _delete_mod_dirs(self, ids):
        removed = 0
        for mid in ids:
            for wd in workshop_dirs(self.cfg):
                path = os.path.join(wd, str(mid))
                if os.path.isdir(path):
                    log.warning("Removing Workshop mod before redownload: %s", path)
                    shutil.rmtree(path, ignore_errors=True)
                    removed += 1
        return removed

    def _install_worker(self, ids, names, label, repair, redownload, progress):
        try:
            self._refresh_cfg()
            if not self._ensure_steam():
                return

            if repair:
                removed = self._delete_corrupt_mods()
                if removed:
                    self.set_status(f"Repairing {removed} corrupt Workshop mod(s)...")

            if redownload:
                removed = self._delete_mod_dirs(ids)
                if removed:
                    self.set_status(f"Redownloading {removed} Workshop mod(s)...")

            for mid in ids:
                if progress.is_cancelled():
                    self.set_status("Workshop action cancelled.")
                    return
                self.subscriptions.subscribe_mod_steam(mid, names.get(mid, mid))
                time.sleep(0.25)
            self.subscriptions.open_steam_downloads()

            sizes = self.downloads.fetch_mod_sizes(ids)
            queue = sorted(ids, key=lambda mid: sizes.get(mid, 0))
            progress.set_download_progress(0, len(queue))
            self.set_status(label + "...")

            ok, err = self.downloads.subscribe_and_wait_mods(
                queue,
                names,
                progress,
                sizes,
            )
            self.set_downloading(False)

            if err == "cancelled" or progress.is_cancelled():
                self.set_status("Workshop action cancelled.")
                return
            if not ok:
                self.set_status(f"Workshop action failed: {err}")
                return

            installed = sum(1 for mid in ids if mod_installed(self.cfg, mid))
            self.set_status(f"Workshop mods ready: {installed}/{len(ids)}")
        finally:
            workshop_gate.finish()
            self.set_downloading(False)
            GLib.idle_add(progress.close)
