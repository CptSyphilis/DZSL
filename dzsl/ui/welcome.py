import os

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

from dzsl.core.config import RECENT_FILE, VERSION, load_json
from dzsl.paths import asset_path

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

        title = Gtk.Picture.new_for_filename(str(asset_path("dzsl-wordmark.svg")))
        title.set_alternative_text("DZSL")
        title.set_content_fit(Gtk.ContentFit.CONTAIN)
        title.set_can_shrink(True)
        title.set_size_request(360, 112)
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
        vbox.append(row)

        # ── Stat line ──
        stats = Gtk.Label(
            label=f"{n_fav} favourite{'s' if n_fav != 1 else ''}  ·  "
                  f"{n_recent} recently played"
        )
        stats.add_css_class("welcome-stats")
        vbox.append(stats)

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
