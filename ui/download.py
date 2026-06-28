import concurrent.futures
import fcntl
import os
import pty
import re
import shutil
import struct
import subprocess
import termios
import threading
import time

import requests
from gi.repository import GLib

from config import DAYZ_APPID, mod_installed, mod_subscribed, workshop_dir
from steam_workshop import validate_mod_folder
from ui.helpers import notify_check_steam
from applog import get_logger

log = get_logger("download")


class ModDownloadManager:
    def __init__(self, cfg_provider, refresh_cfg, set_status, subscriptions):
        self.cfg_provider = cfg_provider
        self.refresh_cfg = refresh_cfg
        self.set_status = set_status
        self.subscriptions = subscriptions
        self._active_procs = set()
        self._active_lock = threading.Lock()

    def _register_proc(self, proc):
        with self._active_lock:
            self._active_procs.add(proc)

    def _unregister_proc(self, proc):
        with self._active_lock:
            self._active_procs.discard(proc)

    def kill_all_active(self):
        with self._active_lock:
            procs = list(self._active_procs)
        for proc in procs:
            try:
                proc.terminate()
            except OSError:
                pass
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except OSError:
                    pass
        with self._active_lock:
            self._active_procs.clear()

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

    def mod_download_timeout(self, nbytes):
        nbytes = int(nbytes or 0)
        if nbytes >= 5 * 1024 ** 3:
            return 6 * 3600
        if nbytes >= 1024 ** 3:
            return 3 * 3600
        if nbytes >= 100 * 1024 ** 2:
            return 3600
        return 900

    def depotdownloader_path(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.expanduser("~/tools/depotdownloader/DepotDownloader"),
            os.path.join(root, "bin", "DepotDownloader"),
        ]
        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return None

    def get_steam_username(self):
        vdf = os.path.expanduser("~/.local/share/Steam/config/loginusers.vdf")
        try:
            text = open(vdf, errors="ignore").read()
            for match in re.finditer(r'"(\d{17})"[^{]*\{([^}]*)\}', text, re.DOTALL):
                block = match.group(2)
                if '"MostRecent"\t\t"1"' in block or '"MostRecent"  "1"' in block:
                    name = re.search(r'"AccountName"\s+"([^"]+)"', block)
                    if name:
                        return name.group(1)
        except OSError:
            pass
        return None

    def download_mod_depotdownloader(self, mid, mod_name, dest_dir, progress=None, size_bytes=0):
        depot_bin = self.depotdownloader_path()
        username = self.get_steam_username()
        if not depot_bin or not username:
            return False, "DepotDownloader not available"

        staging_dir = dest_dir + ".dzsl-partial"
        self._recover_staged_mod(dest_dir)
        self.cleanup_partial_mod(staging_dir, mid)
        os.makedirs(staging_dir, exist_ok=True)
        max_chunks = int(self.cfg.get("download_max_chunks", 8))
        cmd = [
            depot_bin,
            "-app",
            DAYZ_APPID,
            "-pubfile",
            str(mid),
            "-username",
            username,
            "-remember-password",
            "-dir",
            staging_dir,
            "-max-downloads",
            str(max(1, min(max_chunks, 8))),
        ]
        speed_kbps = int(self.cfg.get("download_speed_kbps", 0) or 0)
        if speed_kbps > 0:
            if shutil.which("trickle"):
                cmd = ["trickle", "-d", str(speed_kbps)] + cmd
            else:
                log.warning("Speed limit set but trickle not found; downloading unlimited")

        log.info("DepotDownloader: %s (%s) -> %s", mod_name, mid, staging_dir)
        try:
            master_fd, slave_fd = pty.openpty()
            # DepotDownloader detects a 0×0 terminal size and throttles its live
            # progress redraw; give it a real-looking size so updates keep flowing.
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack('HHHH', 50, 200, 0, 0))
            proc = subprocess.Popen(cmd, stdout=slave_fd, stderr=slave_fd, close_fds=True)
            os.close(slave_fd)
            self._register_proc(proc)
            last_lines = []
            speed_window = []
            window_secs = 4.0
            ansi_re = re.compile(rb'\x1b\[[0-9;]*[a-zA-Z]')
            buf = b""

            def read_lines():
                nonlocal buf
                while True:
                    try:
                        chunk = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    buf += ansi_re.sub(b"", chunk)
                    while True:
                        idx_r = buf.find(b"\r")
                        idx_n = buf.find(b"\n")
                        if idx_r == -1 and idx_n == -1:
                            break
                        idx = min(i for i in (idx_r, idx_n) if i != -1)
                        raw, buf = buf[:idx], buf[idx + 1:]
                        yield raw.decode(errors="ignore").strip()
                if buf.strip():
                    yield buf.decode(errors="ignore").strip()

            for line in read_lines():
                if not line:
                    continue
                log.debug("depot: %s", line)
                last_lines.append(line)
                if len(last_lines) > 8:
                    last_lines.pop(0)
                match = re.match(r"\s*(\d+\.\d+)%", line)
                if match:
                    pct = float(match.group(1))
                    now = time.time()
                    bytes_done = pct / 100.0 * size_bytes if size_bytes else None
                    if progress:
                        GLib.idle_add(progress.set_mod_progress, mid, pct / 100.0, bytes_done, size_bytes)
                    if size_bytes:
                        speed_window.append((now, bytes_done))
                        cutoff = now - window_secs
                        while len(speed_window) > 1 and speed_window[0][0] < cutoff:
                            speed_window.pop(0)
                        if len(speed_window) >= 2:
                            dt = speed_window[-1][0] - speed_window[0][0]
                            db = speed_window[-1][1] - speed_window[0][1]
                            if dt >= 0.5 and db >= 0:
                                GLib.idle_add(progress.set_speed, self.format_size(db / dt) + "/s")
                elif progress:
                    GLib.idle_add(progress.set_hint, f"{mod_name}: {line}")
                if progress and progress.is_cancelled():
                    proc.terminate()
                    proc.wait()
                    os.close(master_fd)
                    self._unregister_proc(proc)
                    self.cleanup_partial_mod(staging_dir, mid)
                    return False, "cancelled"

            proc.wait()
            os.close(master_fd)
            self._unregister_proc(proc)
            if progress:
                GLib.idle_add(progress.set_speed, "-")
            if proc.returncode == 0:
                valid, reason = validate_mod_folder(staging_dir)
                if not valid:
                    self.cleanup_partial_mod(staging_dir, mid)
                    error = f"Downloaded Workshop content failed validation: {reason}"
                    log.error("DepotDownloader produced invalid mod %s: %s", mid, reason)
                    return False, error
                self._commit_staged_mod(staging_dir, dest_dir)
                log.info("DepotDownloader done: %s (%s)", mod_name, mid)
                return True, ""

            self.cleanup_partial_mod(staging_dir, mid)
            tail = "\n".join(last_lines[-3:]) if last_lines else ""
            err_msg = f"DepotDownloader exited {proc.returncode}"
            if tail:
                err_msg += f":\n{tail}"
            log.error("DepotDownloader failed for %s: %s", mod_name, err_msg)
            return False, err_msg
        except Exception as exc:
            log.error("DepotDownloader error for %s: %s", mid, exc)
            if 'proc' in locals():
                self._unregister_proc(proc)
            try:
                os.close(master_fd)
            except OSError:
                pass
            self.cleanup_partial_mod(staging_dir, mid)
            return False, str(exc)

    def _recover_staged_mod(self, dest_dir):
        backup_dir = dest_dir + ".dzsl-backup"
        if not os.path.exists(backup_dir):
            return
        if not os.path.exists(dest_dir):
            os.replace(backup_dir, dest_dir)
        else:
            shutil.rmtree(backup_dir, ignore_errors=True)

    def _commit_staged_mod(self, staging_dir, dest_dir):
        backup_dir = dest_dir + ".dzsl-backup"
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir, ignore_errors=True)
        if os.path.exists(dest_dir):
            os.replace(dest_dir, backup_dir)
        try:
            os.replace(staging_dir, dest_dir)
        except Exception:
            if os.path.exists(backup_dir) and not os.path.exists(dest_dir):
                os.replace(backup_dir, dest_dir)
            raise
        shutil.rmtree(backup_dir, ignore_errors=True)

    def cleanup_partial_mod(self, dest_dir, mid):
        if os.path.isdir(dest_dir):
            log.warning("Cleaning up partial download for %s: %s", mid, dest_dir)
            try:
                shutil.rmtree(dest_dir)
            except OSError as exc:
                log.error("Failed to clean up %s: %s", dest_dir, exc)

    def subscribe_and_wait_mods(
        self,
        mod_ids,
        mod_names=None,
        progress=None,
        sizes=None,
        force_steam=False,
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

        backend = "steam" if force_steam else self.cfg.get("download_backend", "auto")
        # Steam is authoritative for Workshop manifests and updates. Keep the
        # alternate downloader opt-in so auto mode cannot race Steam writes.
        use_depot = backend == "depot"
        if not use_depot:
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

            if use_depot:
                dest = os.path.join(workshop_dir(self.cfg), mid)
                ok, err = self.download_mod_depotdownloader(
                    mid,
                    mod_name,
                    dest,
                    progress,
                    size_bytes=sizes.get(mid, 0) if sizes else 0,
                )
            else:
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
