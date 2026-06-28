import concurrent.futures
import threading

import requests

from config import mod_installed, mod_subscribed
from ui.helpers import notify_check_steam
from applog import get_logger

log = get_logger("download")


class ModDownloadManager:
    def __init__(self, cfg_provider, refresh_cfg, set_status, subscriptions):
        self.cfg_provider = cfg_provider
        self.refresh_cfg = refresh_cfg
        self.set_status = set_status
        self.subscriptions = subscriptions

    @property
    def cfg(self):
        return self.cfg_provider()

    def download_cancelled(self, progress):
        return progress and progress.is_cancelled()

    def count_installed_mods(self, mod_ids):
        return sum(1 for mid in mod_ids if mod_installed(self.cfg, mid))

    def format_size(self, nbytes):
        nbytes = int(nbytes or 0)
        if nbytes < 1024:
            return f"{nbytes} B"
        if nbytes < 1024 ** 2:
            return f"{nbytes / 1024:.1f} KB"
        if nbytes < 1024 ** 3:
            return f"{nbytes / 1024 ** 2:.1f} MB"
        return f"{nbytes / 1024 ** 3:.2f} GB"

    def subscribe_and_wait_mods(
        self,
        mod_ids,
        mod_names=None,
        progress=None,
        sizes=None,
    ):
        self.refresh_cfg()
        names = mod_names or {}
        ids = [str(mid) for mid in mod_ids or []]
        total = len(ids)
        log.info("Need %d mod(s): %s", total, ", ".join(names.get(mid, mid) for mid in ids))

        pending = []
        done = 0
        for mid in ids:
            if mod_installed(self.cfg, mid) and mod_subscribed(self.cfg, mid):
                log.info("Already installed: %s", names.get(mid, mid))
                self.mark_mod_progress(progress, mid)
                done += 1
            else:
                pending.append(mid)
        if progress:
            progress.set_download_progress(done, total)
        if not pending:
            return True, ""
        if progress and progress.is_cancelled():
            return False, "cancelled"

        notify_check_steam()

        n_parallel = 1
        log.info("Downloading %d mod(s) with up to %d in parallel", len(pending), n_parallel)
        if progress:
            progress.set_action_prompt(f"Downloading {len(pending)} mod(s)...")

        done_lock = threading.Lock()
        done_ref = [done]
        errors = []

        def download_one(mid):
            if progress and progress.is_cancelled():
                return
            mod_name = names.get(mid, mid)
            log.info("Downloading: %s (%s)", mod_name, mid)
            self.set_status(f"Downloading {mod_name}...")
            if progress:
                progress.set_mod_status(mid, "Starting", "active")

            self.subscriptions.subscribe_mod_steam(mid, mod_name)
            ok = self.subscriptions.wait_for_mod_installed(
                mid,
                progress,
                mod_name,
                size_bytes=sizes.get(mid, 0) if sizes else 0,
            )
            err = "" if ok else f"Timeout waiting for {mod_name}"

            if not ok:
                log.error("Failed %s: %s", mod_name, err)
                if progress:
                    progress.set_mod_status(mid, "Failed", "failed")
                with done_lock:
                    errors.append(err)
                return

            self.mark_mod_progress(progress, mid)
            with done_lock:
                done_ref[0] += 1
                current_done = done_ref[0]
            if progress:
                progress.set_download_progress(current_done, total)
            log.info("Done: %s", mod_name)

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_parallel) as executor:
            futures = {executor.submit(download_one, mid): mid for mid in pending}
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    mid = futures[future]
                    log.error("Unhandled error downloading %s: %s", mid, exc)
                    with done_lock:
                        errors.append(str(exc))

        if progress and progress.is_cancelled():
            return False, "cancelled"
        if errors:
            return False, errors[0]
        return True, ""

    def fetch_mod_sizes(self, mod_ids):
        sizes = {}
        ids = [str(mid) for mid in mod_ids or []]
        if not ids:
            return sizes
        try:
            payload = {"itemcount": len(ids)}
            for i, mid in enumerate(ids):
                payload[f"publishedfileids[{i}]"] = mid
            response = requests.post(
                "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                data=payload,
                timeout=120,
            ).json()
            for detail in response.get("response", {}).get("publishedfiledetails", []):
                mid = str(detail.get("publishedfileid", ""))
                if mid:
                    sizes[mid] = int(detail.get("file_size", 0) or 0)
        except Exception as exc:
            log.warning("Could not fetch mod sizes: %s", exc)
        return sizes

    def prepare_mod_queue(self, mod_ids, mod_names=None):
        sizes = self.fetch_mod_sizes(mod_ids)
        queue = sorted([str(mid) for mid in mod_ids or []], key=lambda mid: sizes.get(mid, 0))
        if queue:
            order = ", ".join(
                f"{(mod_names or {}).get(mid, mid)} ({self.format_size(sizes.get(mid, 0))})"
                for mid in queue[:6]
            )
            log.info("Mod queue (smallest first): %s", order)
        return queue, sizes

    def mark_mod_progress(self, progress, mod_id):
        mid = str(mod_id)
        if not progress:
            return
        if mod_installed(self.cfg, mid):
            progress.mark_installed(mid)
        elif mod_subscribed(self.cfg, mid):
            progress.mark_subscribed(mid)
