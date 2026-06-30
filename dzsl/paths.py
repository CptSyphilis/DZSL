from pathlib import Path
import os


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
ASSETS_DIR = PACKAGE_DIR / "assets"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "dzsl"
ENV_FILE = PROJECT_ROOT / ".env" if (PROJECT_ROOT / ".git").is_dir() else CONFIG_DIR / ".env"


def asset_path(name):
    return ASSETS_DIR / name
