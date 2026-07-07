import threading
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from dzsl.core.logging import get_logger
from dzsl.http import RequestError
from dzsl.runtime import open_external_uri
from dzsl.services.owner import poll_app_link, start_app_link

log = get_logger("owner")

POLL_INTERVAL = 2.0
POLL_TIMEOUT = 600


class OwnerLoginWindow(Adw.Window):
    """Browser-approve sign-in for dayzlinux.com.

    Opens {site}/link?code=<code> in the user's default browser — where they
    are usually already signed in with Steam — and polls the site until they
    click Approve, then hands the fresh session token to success_cb. One-shot
    window: a new one is created per sign-in attempt.
    """

    def __init__(self, parent, success_cb):
        super().__init__()
        self._success_cb = success_cb
        self._cancelled = False
        self._link = None

        self.set_title("Sign in with Steam")
        self.set_default_size(440, 240)
        self.set_modal(True)
        if parent is not None:
            self.set_transient_for(parent)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.append(Adw.HeaderBar())

        self._status = Gtk.Label(label="Contacting dayzlinux.com…", wrap=True)
        self._status.set_margin_start(24)
        self._status.set_margin_end(24)
        box.append(self._status)

        self._spinner = Gtk.Spinner()
        self._spinner.start()
        box.append(self._spinner)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_halign(Gtk.Align.CENTER)
        row.set_margin_bottom(18)
        self._open_btn = Gtk.Button(label="OPEN PAGE AGAIN")
        self._open_btn.add_css_class("btn-ghost")
        self._open_btn.set_sensitive(False)
        self._open_btn.connect("clicked", lambda _: self._open_page())
        row.append(self._open_btn)
        cancel = Gtk.Button(label="CANCEL")
        cancel.add_css_class("btn-ghost")
        cancel.connect("clicked", lambda _: self.close())
        row.append(cancel)
        box.append(row)

        self.set_content(box)
        self.connect("close-request", self._on_close)

        threading.Thread(target=self._run, daemon=True).start()

    def _on_close(self, *_args):
        self._cancelled = True
        return False

    def _set_msg(self, text, stop_spinner=False):
        def apply():
            self._status.set_text(text)
            if stop_spinner:
                self._spinner.stop()

        GLib.idle_add(apply)

    def _open_page(self):
        if self._link and not open_external_uri(self._link["url"]):
            self._status.set_text(f"Could not open a browser. Visit:\n{self._link['url']}")

    def _run(self):
        try:
            self._link = start_app_link()
        except RequestError as exc:
            log.warning("Owner sign-in could not start: %s", exc)
            self._set_msg(
                "Could not reach dayzlinux.com — check your connection, "
                "then close this window and try again.",
                stop_spinner=True,
            )
            return
        GLib.idle_add(self._open_btn.set_sensitive, True)
        GLib.idle_add(self._open_page)
        self._set_msg(
            "Approve the sign-in in your browser, then come back here.\n"
            "The page opened in your default browser."
        )

        deadline = time.monotonic() + POLL_TIMEOUT
        while not self._cancelled and time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL)
            if self._cancelled:
                return
            try:
                token = poll_app_link(self._link["code"], self._link["poll"])
            except RequestError as exc:
                if getattr(exc, "status", None) in (400, 404):
                    self._set_msg(
                        "The sign-in request expired — close this window and try again.",
                        stop_spinner=True,
                    )
                    return
                continue  # transient network error — keep polling
            if token:
                GLib.idle_add(self._finish, token)
                return
        if not self._cancelled:
            self._set_msg(
                "Timed out waiting for approval — close this window and try again.",
                stop_spinner=True,
            )

    def _finish(self, token):
        if self._cancelled:
            return
        self._cancelled = True
        log.info("Owner sign-in approved in the browser")
        callback = self._success_cb
        self.close()
        callback(token)
