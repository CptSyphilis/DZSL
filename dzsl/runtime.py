import os


def is_flatpak():
    return bool(os.environ.get("FLATPAK_ID"))


def open_external_uri(uri):
    from gi.repository import Gio, GLib

    try:
        Gio.AppInfo.launch_default_for_uri(uri, None)
        return True
    except GLib.Error:
        return False
