import ctypes
import ctypes.util

from dzsl.paths import ASSETS_DIR


FONT_FILES = (
    ASSETS_DIR / "fonts" / "BlackOpsOne-Regular.ttf",
    ASSETS_DIR / "fonts" / "Oswald.ttf",
)


def load_bundled_fonts():
    library_name = ctypes.util.find_library("fontconfig")
    if not library_name:
        return False

    try:
        fontconfig = ctypes.CDLL(library_name)
        fontconfig.FcConfigGetCurrent.restype = ctypes.c_void_p
        fontconfig.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        fontconfig.FcConfigAppFontAddFile.restype = ctypes.c_int
        fontconfig.FcConfigBuildFonts.argtypes = [ctypes.c_void_p]
        fontconfig.FcConfigBuildFonts.restype = ctypes.c_int

        config = fontconfig.FcConfigGetCurrent()
        if not config:
            return False
        loaded = all(
            path.is_file() and fontconfig.FcConfigAppFontAddFile(config, str(path).encode())
            for path in FONT_FILES
        )
        return bool(loaded and fontconfig.FcConfigBuildFonts(config))
    except (AttributeError, OSError):
        return False
