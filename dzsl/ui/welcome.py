import os
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, GLib, Gtk

from dzsl.core.config import RECENT_FILE, VERSION, load_cfg, load_json
from dzsl.http import RequestError
from dzsl.services.dayz import launch_without_mods
from dzsl.services.updates import fetch_changelog
from dzsl.paths import asset_path
from dzsl.ui.branding import wordmark

BG_PATH = str(asset_path("dzsl-bg.png"))


class WelcomeView:
    """The landing screen: hero background image with quick actions on top."""

    def __init__(self, panel, show_view, connect_cb, favorites):
        self.panel = panel
        self.show_view = show_view
        self.connect_cb = connect_cb
        self.favorites = favorites

    def build(self):
        recent = load_json(RECENT_FILE) or []
        n_fav = len(self.favorites or [])
        n_recent = len(recent)

        overlay = Gtk.Overlay()
        overlay.set_vexpand(True)
        overlay.set_hexpand(True)

        # ── Background hero image (cover-fit, fills the panel) ──
        if os.path.exists(BG_PATH):
            picture = Gtk.Picture.new_for_filename(BG_PATH)
            picture.set_content_fit(Gtk.ContentFit.COVER)
            picture.set_can_shrink(True)
            picture.set_size_request(1, 1)
            picture.set_vexpand(True)
            picture.set_hexpand(True)
            overlay.set_child(picture)
        else:
            filler = Gtk.Box()
            filler.add_css_class("welcome-bg-fallback")
            overlay.set_child(filler)

        # ── Dark scrim + centered content layered on top ──
        scrim = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrim.add_css_class("welcome-scrim")
        scrim.set_vexpand(True)
        scrim.set_hexpand(True)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        vbox.set_vexpand(True)

        title = wordmark(150)
        title.add_css_class("welcome-title")
        vbox.append(title)

        sub = Gtk.Label(label="DAYZ SERVER BROWSER FOR LINUX")
        sub.add_css_class("welcome-sub")
        vbox.append(sub)

        spacer = Gtk.Box()
        spacer.set_size_request(-1, 8)
        vbox.append(spacer)

        # ── Jump back in: quick-connect to the most recent server ──
        if recent:
            last = recent[0]
            card = self._build_resume_card(last)
            vbox.append(card)

        browse = Gtk.Button(label="BROWSE SERVERS")
        browse.add_css_class("welcome-primary")
        browse.set_halign(Gtk.Align.CENTER)
        browse.connect("clicked", lambda _: self.show_view("servers"))
        vbox.append(browse)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_halign(Gtk.Align.CENTER)
        for label, view in [("Favorites", "favorites"), ("Recent", "recent"), ("Mods", "mods")]:
            b = Gtk.Button(label=label)
            b.add_css_class("welcome-secondary")
            b.connect("clicked", lambda _, v=view: self.show_view(v))
            row.append(b)
        vanilla = Gtk.Button(label="Play without mods")
        vanilla.add_css_class("welcome-secondary")
        vanilla.connect("clicked", self._play_without_mods)
        row.append(vanilla)
        news = Gtk.Button(label="What's new")
        news.add_css_class("welcome-secondary")
        news.connect("clicked", lambda _: self._show_changelog())
        row.append(news)
        vbox.append(row)

        # ── Stat line ──
        stats = Gtk.Label(
            label=f"{n_fav} favourite{'s' if n_fav != 1 else ''}  ·  "
                  f"{n_recent} recently played"
        )
        stats.add_css_class("welcome-stats")
        vbox.append(stats)

        self.notice = Gtk.Label()
        self.notice.add_css_class("welcome-notice")
        self.notice.set_wrap(True)
        self.notice.set_max_width_chars(70)
        self.notice.set_justify(Gtk.Justification.CENTER)
        self.notice.set_visible(False)
        vbox.append(self.notice)
        self.changelog = None
        threading.Thread(target=self._load_changelog, daemon=True).start()

        scrim.append(vbox)
        overlay.add_overlay(scrim)

        # ── Version footer (bottom-right corner) ──
        ver = Gtk.Label(label=f"v{VERSION}")
        ver.add_css_class("welcome-version")
        ver.set_halign(Gtk.Align.END)
        ver.set_valign(Gtk.Align.END)
        ver.set_margin_end(14)
        ver.set_margin_bottom(10)
        overlay.add_overlay(ver)

        self.panel.append(overlay)

    def _play_without_mods(self, button):
        button.set_sensitive(False)
        button.set_label("Starting DayZ…")

        def run():
            ok = launch_without_mods(load_cfg())
            GLib.idle_add(done, ok)

        def reset():
            button.set_sensitive(True)
            button.set_label("Play without mods")
            return False

        def done(ok):
            button.set_label("Play without mods" if ok else "Couldn't start DayZ")
            GLib.timeout_add_seconds(5, reset)
            return False

        threading.Thread(target=run, daemon=True).start()

    def _load_changelog(self):
        try:
            entries = fetch_changelog()
        except RequestError:
            entries = None
        GLib.idle_add(self._changelog_loaded, entries)

    def _changelog_loaded(self, entries):
        self.changelog = entries
        notice = next((e for e in entries or [] if e.get("notice")), None)
        if notice:
            self.notice.set_text(f"NOTICE  ·  {notice['text']}")
            self.notice.set_visible(True)
        return False

    def _show_changelog(self):
        dlg = Adw.Dialog()
        dlg.set_title("What's new")
        dlg.set_content_width(520)
        dlg.set_content_height(520)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(Adw.HeaderBar())
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        body.set_margin_start(20)
        body.set_margin_end(20)
        body.set_margin_bottom(20)
        if self.changelog is None:
            msg = Gtk.Label(label="Couldn't load the changelog. Check your connection and try again.")
            msg.set_wrap(True)
            body.append(msg)
        for entry in self.changelog or []:
            if entry.get("notice"):
                head = Gtk.Label(label=f"NOTICE  ·  {entry['date']}" if entry["date"] else "NOTICE")
                head.add_css_class("changelog-notice")
                lines = [entry["text"]]
            else:
                head = Gtk.Label(label=f"v{entry['version']}" + (f"  ·  {entry['date']}" if entry["date"] else ""))
                head.add_css_class("changelog-version")
                lines = [f"•  {item}" for item in entry["items"]]
            head.set_halign(Gtk.Align.START)
            head.set_margin_top(12)
            body.append(head)
            for line in lines:
                lbl = Gtk.Label(label=line)
                lbl.set_wrap(True)
                lbl.set_xalign(0)
                lbl.add_css_class("changelog-item")
                body.append(lbl)
        scroll.set_child(body)
        box.append(scroll)
        dlg.set_child(box)
        dlg.present(self.panel.get_root())

    def _build_resume_card(self, server):
        name = server.get("name", "Unknown server")
        players = server.get("players", 0)
        maxp = server.get("maxPlayers", 0)
        mp = server.get("map", "")

        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        card.add_css_class("welcome-resume-card")
        card.set_halign(Gtk.Align.CENTER)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.set_valign(Gtk.Align.CENTER)

        eyebrow = Gtk.Label(label="JUMP BACK IN")
        eyebrow.add_css_class("welcome-resume-eyebrow")
        eyebrow.set_halign(Gtk.Align.START)
        info.append(eyebrow)

        nm = Gtk.Label(label=name)
        nm.add_css_class("welcome-resume-name")
        nm.set_halign(Gtk.Align.START)
        nm.set_max_width_chars(38)
        nm.set_ellipsize(3)
        info.append(nm)

        meta_bits = []
        if mp:
            meta_bits.append(mp)
        meta_bits.append(f"{players}/{maxp} players")
        meta = Gtk.Label(label="  ·  ".join(meta_bits))
        meta.add_css_class("welcome-resume-meta")
        meta.set_halign(Gtk.Align.START)
        info.append(meta)

        card.append(info)

        connect = Gtk.Button(label="CONNECT")
        connect.add_css_class("welcome-resume-btn")
        connect.set_valign(Gtk.Align.CENTER)
        connect.connect("clicked", lambda _: self.connect_cb(server))
        card.append(connect)

        return card
