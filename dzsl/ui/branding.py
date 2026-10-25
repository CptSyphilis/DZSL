from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from dzsl.paths import ASSETS_DIR

_TITLE = ASSETS_DIR / "dzsl-title.png"


def wordmark(height):
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(_TITLE), -1, height, True)
    except GLib.Error:
        label = Gtk.Label(label="DZSL")
        label.add_css_class("app-title")
        return label
    pic = Gtk.Picture.new_for_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
    pic.set_can_shrink(False)
    pic.set_halign(Gtk.Align.CENTER)
    pic.set_valign(Gtk.Align.CENTER)
    pic.set_alternative_text("DZSL")
    return pic
