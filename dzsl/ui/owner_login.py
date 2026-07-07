import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from dzsl.core.logging import get_logger
from dzsl.services.listings import _base_url
from dzsl.services.owner import SESSION_COOKIE

log = get_logger("owner")


def _load_webkit():
    try:
        gi.require_version("WebKit", "6.0")
        from gi.repository import WebKit

        return WebKit
    except (ImportError, ValueError):
        return None


def webkit_available():
    return _load_webkit() is not None


WEBKIT_INSTALL_HINT = (
    "The in-app Steam sign-in needs WebKitGTK.\n"
    "Install it with e.g.:  sudo apt install gir1.2-webkit-6.0"
)


class OwnerLoginWindow(Adw.Window):
    """One-shot embedded browser window for the dayzlinux.com Steam sign-in.

    Uses an ephemeral WebKit session so nothing persists on disk except the
    dzsl_session token we hand to success_cb; a new window is created per
    sign-in attempt, so it is safe to let it be destroyed on close.
    """

    def __init__(self, parent, success_cb, base_url=None):
        super().__init__()
        webkit = _load_webkit()
        if webkit is None:
            raise RuntimeError(WEBKIT_INSTALL_HINT)
        self._webkit = webkit
        self._base = _base_url(base_url)
        self._success_cb = success_cb
        self._done = False

        self.set_title("Sign in with Steam")
        self.set_default_size(520, 720)
        self.set_modal(True)
        if parent is not None:
            self.set_transient_for(parent)

        self._session = webkit.NetworkSession.new_ephemeral()
        self._view = webkit.WebView(network_session=self._session)
        self._view.connect("load-changed", self._on_load_changed)
        self._view.connect("load-failed", self._on_load_failed)

        self._status = Gtk.Label(label="", wrap=True, margin_top=4, margin_bottom=4)
        self._status.set_visible(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(Adw.HeaderBar())
        box.append(self._status)
        self._view.set_vexpand(True)
        box.append(self._view)
        self.set_content(box)

        self._view.load_uri(f"{self._base}/api/auth/steam/login")

    def _show_status(self, message):
        self._status.set_text(message)
        self._status.set_visible(True)

    def _on_load_failed(self, view, event, uri, error):
        if self._done:
            return False
        log.warning("Owner login load failed for %s: %s", uri, error)
        self._show_status("Could not reach the sign-in page. Check your connection and close this window to retry.")
        return False

    def _on_load_changed(self, view, event):
        if self._done or event != self._webkit.LoadEvent.FINISHED:
            return
        uri = view.get_uri() or ""
        if not uri.startswith(f"{self._base}/dashboard"):
            return
        if "error=auth" in uri:
            self._show_status("Steam sign-in failed. Trying again…")
            GLib.timeout_add(1500, self._restart_login)
            return
        manager = self._session.get_cookie_manager()
        manager.get_cookies(self._base + "/", None, self._on_cookies_ready)

    def _restart_login(self):
        if not self._done:
            self._status.set_visible(False)
            self._view.load_uri(f"{self._base}/api/auth/steam/login")
        return False

    def _on_cookies_ready(self, manager, result):
        if self._done:
            return
        try:
            cookies = manager.get_cookies_finish(result)
        except GLib.Error as exc:
            log.warning("Owner login could not read cookies: %s", exc)
            self._show_status("Sign-in finished but the session could not be read. Close and retry.")
            return
        token = ""
        for cookie in cookies or []:
            if cookie.get_name() == SESSION_COOKIE:
                token = cookie.get_value() or ""
                break
        if not token:
            log.warning("Owner login finished without a %s cookie", SESSION_COOKIE)
            self._show_status("Sign-in finished but no session was created. Close and retry.")
            return
        self._done = True
        log.info("Owner sign-in captured a website session")
        callback = self._success_cb
        self.close()
        callback(token)
