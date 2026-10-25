import subprocess

from gi.repository import GLib, Gtk

from dzsl.core.constants import VERSION
from dzsl.paths import ASSETS_DIR


class SplashWindow(Gtk.Window):
    def __init__(self, application):
        super().__init__(application=application)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(380, 250)
        self.set_title("DZSL")
        overlay = "wayland" in type(self.get_display()).__name__.lower()
        if overlay:
            self.add_css_class("splash-overlay")
            self.maximize()
        else:
            self.add_css_class("splash")
            self.connect("map", lambda _: GLib.idle_add(self._center_on_monitor))

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.set_margin_top(30)
        box.set_margin_bottom(30)
        box.set_margin_start(40)
        box.set_margin_end(40)

        icon_path = ASSETS_DIR / "icon.png"
        if icon_path.exists():
            img = Gtk.Image.new_from_file(str(icon_path))
            img.set_pixel_size(72)
            box.append(img)

        title = Gtk.Label(label="DZSL")
        title.add_css_class("app-title")
        box.append(title)

        version = Gtk.Label(label=f"v{VERSION}")
        version.add_css_class("splash-version")
        box.append(version)

        self.spinner = Gtk.Spinner()
        self.spinner.start()
        box.append(self.spinner)

        self.step_lbl = Gtk.Label(label="Starting…")
        self.step_lbl.add_css_class("splash-step")
        box.append(self.step_lbl)

        self.choice = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, visible=False)
        self.later_btn = Gtk.Button(label="Later"); self.later_btn.add_css_class("btn-ghost")
        self.update_btn = Gtk.Button(label="Update now"); self.update_btn.add_css_class("btn-connect")
        self.choice.append(self.later_btn); self.choice.append(self.update_btn)
        box.append(self.choice)

        if overlay:
            card = Gtk.Box()
            card.add_css_class("splash")
            card.set_size_request(380, 250)
            card.set_valign(Gtk.Align.CENTER)
            card.set_halign(Gtk.Align.CENTER)
            box.set_hexpand(True)
            card.append(box)
            self.set_child(card)
        else:
            self.set_child(box)

    def set_step(self, text):
        GLib.idle_add(self.step_lbl.set_text, text)

    def ask_update(self, version, on_update, on_later):
        def pick(cb):
            self.choice.set_visible(False)
            self.spinner.set_visible(True)
            cb()
        self.spinner.set_visible(False)
        self.step_lbl.set_text(f"DZSL {version} is available")
        self.update_btn.connect("clicked", lambda _: pick(on_update))
        self.later_btn.connect("clicked", lambda _: pick(on_later))
        self.choice.set_visible(True)
        return False

    def _center_on_monitor(self):
        # GTK4 has no window-positioning API; on X11 move it ourselves.
        surface = self.get_surface()
        if not surface or not hasattr(surface, "get_xid"):
            return False
        monitor = self.get_display().get_monitor_at_surface(surface)
        if not monitor:
            return False
        geo = monitor.get_geometry()
        x = geo.x + (geo.width - (self.get_width() or 380)) // 2
        y = geo.y + (geo.height - (self.get_height() or 250)) // 2
        try:
            subprocess.Popen(
                ["xdotool", "windowmove", str(surface.get_xid()), str(x), str(y)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass
        return False
