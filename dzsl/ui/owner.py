import threading
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from dzsl.core.logging import get_logger
from dzsl.http import RequestError
from dzsl.runtime import open_external_uri
from dzsl.services import owner as owner_api
from dzsl.services.owner import TEXT_LIMITS, URL_LIMITS, dashboard_url
from dzsl.ui.helpers import clear_box
from dzsl.ui.owner_login import OwnerLoginWindow

log = get_logger("owner")


def _date(ms):
    try:
        return time.strftime("%Y-%m-%d", time.localtime(int(ms) / 1000))
    except (TypeError, ValueError, OSError, OverflowError):
        return "?"


class OwnerView:
    def __init__(self, panel, set_status, win=None, steam_account=None):
        self.panel = panel
        self.set_status = set_status
        self.win = win
        self.steam_account = steam_account

    # ── layout helpers (mirrors SettingsView) ──────────────────────────

    def _shell(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(24)
        outer.set_margin_bottom(24)
        outer.set_margin_start(40)
        outer.set_margin_end(40)
        scroll.set_child(outer)
        self.panel.append(scroll)
        return outer

    def _card(self, outer, title):
        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        wrapper.add_css_class("settings-card")
        wrapper.set_margin_bottom(20)
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        hdr.add_css_class("settings-card-header")
        lbl = Gtk.Label(label=title)
        lbl.add_css_class("settings-card-title")
        lbl.set_halign(Gtk.Align.START)
        hdr.append(lbl)
        wrapper.append(hdr)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        body.add_css_class("settings-card-body")
        wrapper.append(body)
        outer.append(wrapper)
        return body

    def _label(self, body, text, dim=False):
        lbl = Gtk.Label(label=text, wrap=True, xalign=0)
        lbl.set_halign(Gtk.Align.START)
        if dim:
            lbl.add_css_class("dim-label")
        body.append(lbl)
        return lbl

    def _button_row(self, body, buttons):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for label, css, cb in buttons:
            b = Gtk.Button(label=label)
            b.add_css_class(css)
            b.connect("clicked", lambda _, cb=cb: cb())
            row.append(b)
        body.append(row)
        return row

    def _entry(self, body, label, text, limit):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        lbl = Gtk.Label(label=label)
        lbl.add_css_class("settings-field-label")
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)
        e = Gtk.Entry()
        e.add_css_class("settings-input")
        e.set_max_length(limit)
        e.set_text(text or "")
        e.set_hexpand(True)
        box.append(e)
        body.append(box)
        return e

    def _text_area(self, body, label, text, height=90):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        lbl = Gtk.Label(label=label)
        lbl.add_css_class("settings-field-label")
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)
        view = Gtk.TextView()
        view.add_css_class("settings-input")
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.get_buffer().set_text(text or "")
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(height)
        scroll.set_max_content_height(height)
        scroll.set_child(view)
        box.append(scroll)
        body.append(box)
        return view.get_buffer()

    # ── view states ─────────────────────────────────────────────────────

    def build(self):
        session = owner_api.load_session()
        if session.get("token"):
            self._build_signed_in(session)
        else:
            self._build_signed_out()

    def _rebuild(self):
        clear_box(self.panel)
        self.build()

    def _open_dashboard(self):
        if not open_external_uri(dashboard_url()):
            self.set_status("Could not open the browser.")

    def _build_signed_out(self, message=None):
        outer = self._shell()
        body = self._card(outer, "SERVER OWNERS")
        if message:
            self._label(body, message)
        self._label(
            body,
            "Own a DayZ server? Sign in with Steam to manage your dayzlinux.com "
            "listing from inside DZSL — edit your description, Discord and banner, "
            "and see your Gold promotion status.",
        )
        self._label(
            body,
            "Signing in opens your browser for a one-click approval. Claiming and "
            "verifying a new server happens on the web dashboard.",
            dim=True,
        )
        self._button_row(
            body,
            [
                ("SIGN IN WITH STEAM", "btn-steam", self._start_sign_in),
                ("OPEN WEB DASHBOARD", "btn-ghost", self._open_dashboard),
            ],
        )

    def _build_signed_in(self, session):
        outer = self._shell()
        account = self._card(outer, "ACCOUNT")
        persona = session.get("persona") or session.get("steamId") or "Steam user"
        self._label(account, f"Signed in as {persona}")
        self._button_row(
            account,
            [
                ("REFRESH", "btn-ghost", self._rebuild),
                ("OPEN WEB DASHBOARD", "btn-ghost", self._open_dashboard),
                ("SIGN OUT", "btn-danger", self._sign_out),
            ],
        )
        self._servers_outer = outer
        loading = self._card(outer, "MY SERVERS")
        self._label(loading, "Loading your servers…", dim=True)
        self._loading_card = loading.get_parent()

        token = session["token"]

        def worker():
            try:
                items = owner_api.fetch_claims(token)
            except RequestError as exc:
                GLib.idle_add(self._claims_failed, exc)
                return
            GLib.idle_add(self._render_claims, token, items)

        threading.Thread(target=worker, daemon=True).start()

    def _claims_failed(self, exc):
        if getattr(exc, "status", None) == 401:
            owner_api.clear_session()
            clear_box(self.panel)
            self._build_signed_out("Your session expired — please sign in again.")
            return
        log.warning("Fetching claims failed: %s", exc)
        clear_box(self.panel)
        outer = self._shell()
        body = self._card(outer, "MY SERVERS")
        self._label(body, "Could not reach dayzlinux.com. Check your connection.")
        self._button_row(body, [("RETRY", "btn-ghost", self._rebuild)])

    def _render_claims(self, token, items):
        outer = self._servers_outer
        outer.remove(self._loading_card)
        if not items:
            body = self._card(outer, "MY SERVERS")
            self._label(body, "No claimed servers yet.")
            self._label(
                body,
                "Claim your server on the web dashboard, then come back here to manage it.",
                dim=True,
            )
            self._button_row(body, [("CLAIM A SERVER", "btn-steam", self._open_dashboard)])
            return
        for item in items:
            self._render_claim(outer, token, item)

    def _render_claim(self, outer, token, item):
        listing = item.get("listing") or {}
        title = item["serverKey"]
        if listing.get("name"):
            title = f'{listing["name"]}  ({item["serverKey"]})'
        body = self._card(outer, title)

        if item["verified"]:
            expiry = _date(item.get("verifiedExpiresAt"))
            self._label(body, f"Ownership verified — re-verify by {expiry}.", dim=True)
        else:
            self._label(
                body,
                "Ownership not verified. Verify on the web dashboard "
                "(keep the claim token in your server name).",
            )

        if item["gold"]:
            if item.get("goldStatus") == "canceled":
                self._label(body, f"GOLD — canceled, ends {_date(item.get('goldUntil'))}.")
            else:
                self._label(body, f"GOLD — active until {_date(item.get('goldUntil'))}.")
        else:
            self._label(body, "Not promoted. Gold is purchased on the website.", dim=True)
            self._button_row(body, [("BUY GOLD ON DAYZLINUX.COM", "btn-steam", self._open_dashboard)])

        if not item["verified"]:
            return

        name = self._entry(body, "Listing Name", listing.get("name"), TEXT_LIMITS["name"])
        description = self._text_area(body, "Description", listing.get("description"))
        discord = self._entry(body, "Discord Invite URL", listing.get("discord"), URL_LIMITS["discord"])
        banner = self._entry(body, "Banner Image URL", listing.get("banner"), URL_LIMITS["banner"])
        rules = self._text_area(body, "Server Rules", listing.get("rules"))

        def collect():
            return {
                "name": name.get_text(),
                "description": description.get_text(
                    description.get_start_iter(), description.get_end_iter(), False
                ),
                "discord": discord.get_text(),
                "banner": banner.get_text(),
                "rules": rules.get_text(rules.get_start_iter(), rules.get_end_iter(), False),
            }

        save = Gtk.Button(label="SAVE LISTING")
        save.add_css_class("btn-success")
        save.set_halign(Gtk.Align.START)
        save.connect("clicked", lambda _: self._save_listing(token, item["serverKey"], collect, save))
        body.append(save)

    # ── actions ─────────────────────────────────────────────────────────

    def _start_sign_in(self):
        OwnerLoginWindow(self.win, self._on_signed_in).present()

    def _on_signed_in(self, token):
        try:
            owner_api.save_session(token)
        except ValueError:
            self.set_status("Sign-in returned an invalid session.")
            return
        self.set_status("Signed in to dayzlinux.com.")

        def worker():
            try:
                user = owner_api.auth_me(token)
            except RequestError as exc:
                log.warning("auth/me after sign-in failed: %s", exc)
                user = None
            if user:
                owner_api.save_session(token, user)
                mine = getattr(self.steam_account, "steam_id", "") or ""
                web = str(user.get("steamId") or "")
                if mine and web and mine != web:
                    GLib.idle_add(
                        self._alert,
                        "Different Steam account",
                        "You signed in to the website as a different Steam account "
                        "than the one running in your Steam client. Listings you "
                        "manage here belong to the website account.",
                    )
            GLib.idle_add(self._rebuild)

        threading.Thread(target=worker, daemon=True).start()

    def _sign_out(self):
        session = owner_api.load_session()
        token = session.get("token")
        owner_api.clear_session()
        if token:
            threading.Thread(target=owner_api.logout, args=(token,), daemon=True).start()
        self.set_status("Signed out.")
        self._rebuild()

    def _save_listing(self, token, server_key, collect, button):
        fields = collect()
        try:
            owner_api.clean_listing_fields(fields)
        except ValueError as exc:
            self.set_status(str(exc))
            return
        button.set_sensitive(False)
        self.set_status("Saving listing…")

        def worker():
            try:
                owner_api.save_listing(token, server_key, fields)
            except (RequestError, ValueError) as exc:
                GLib.idle_add(self._save_failed, exc, button)
                return
            GLib.idle_add(self._save_done, button)

        threading.Thread(target=worker, daemon=True).start()

    def _save_done(self, button):
        button.set_sensitive(True)
        self.set_status("Listing saved — changes are live on dayzlinux.com.")

    def _save_failed(self, exc, button):
        button.set_sensitive(True)
        status = getattr(exc, "status", None)
        if status == 401:
            owner_api.clear_session()
            clear_box(self.panel)
            self._build_signed_out("Your session expired — please sign in again.")
            self.set_status("Session expired.")
        elif status == 403:
            self.set_status("Ownership verification expired — re-verify on the web dashboard.")
        else:
            log.warning("Saving listing failed: %s", exc)
            self.set_status(f"Saving listing failed: {exc}")

    def _alert(self, heading, body):
        dialog = Adw.MessageDialog(transient_for=self.win, heading=heading, body=body)
        dialog.add_response("ok", "OK")
        dialog.present()
