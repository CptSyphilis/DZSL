import os
import sys


def configure_display():
    wayland = (
        os.environ.get("XDG_SESSION_TYPE") == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
    )
    if not os.environ.get("FLATPAK_ID") and os.environ.get("DZSL_USE_WAYLAND") != "1" and (
        wayland or os.environ.get("DZSL_USE_X11") == "1"
    ):
        os.environ["GDK_BACKEND"] = "x11"

    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print(
            "DZSL: no display found. Run from a graphical terminal on your desktop.",
            file=sys.stderr,
        )
        return False
    return True
