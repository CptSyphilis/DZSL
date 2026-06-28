#!/bin/bash
# DZSL - DayZ Server List for Linux
# Installs dependencies, copies the app to ~/DZSL, writes config + desktop entry.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$(cd "$BIN_DIR/.." && pwd)"
INSTALL_DIR="${DZSL_INSTALL_DIR:-$HOME/DZSL}"
CONFIG_FILE="$HOME/.config/dzsl/config.json"

# ── colours ──────────────────────────────────────────────────────────────────
R='\033[0;31m'   # red
Y='\033[0;33m'   # gold/amber
W='\033[0;37m'   # dim white
B='\033[1;37m'   # bright white
D='\033[0m'      # reset

_gold()  { echo -e "${Y}$*${D}"; }
_white() { echo -e "${W}$*${D}"; }
_bold()  { echo -e "${B}$*${D}"; }
_red()   { echo -e "${R}$*${D}"; }
_ok()    { echo -e "${Y}  ✓${W} $*${D}"; }
_step()  { echo -e "${Y}  ›${W} $*${D}"; }
_err()   { echo -e "${R}  ✗ $*${D}"; }

clear

echo -e "${Y}"
cat << 'BANNER'
  ██████╗ ███████╗███████╗██╗
  ██╔══██╗   ███╔╝██╔════╝██║
  ██║  ██║  ███╔╝ ███████╗██║
  ██║  ██║ ███╔╝  ╚════██║██║
  ██████╔╝███████╗███████║███████╗
  ╚═════╝ ╚══════╝╚══════╝╚══════╝
BANNER
echo -e "${W}  DayZ Server List for Linux${D}"
echo -e "${Y}  ─────────────────────────────────────────${D}"
echo -e "${W}  INSTALLER${D}"
echo ""

# ── detect distro ─────────────────────────────────────────────────────────────
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO="${ID:-unknown}"
else
    _err "Cannot detect distro. Install dependencies manually."
    exit 1
fi

_white "  System   : ${PRETTY_NAME:-$DISTRO}"
_white "  Source   : $SOURCE_DIR"
_white "  Target   : $INSTALL_DIR"
echo ""

# ── dependency helpers ────────────────────────────────────────────────────────
python_deps_ok() {
    python3 - <<'PY' >/dev/null 2>&1
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw  # noqa: F401
import requests  # noqa: F401
import dotenv  # noqa: F401
PY
}

launcher_deps_ok() {
    command -v gawk >/dev/null && command -v curl >/dev/null && command -v jq >/dev/null
}

install_deps() {
    if python_deps_ok && launcher_deps_ok; then
        _ok "Dependencies already satisfied."
        return
    fi

    if ! command -v sudo >/dev/null; then
        _err "sudo not found. Install manually:"
        _white "  python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1,"
        _white "  python3-requests, python3-dotenv, gawk, curl, jq"
        exit 1
    fi

    echo ""
    _gold "  [ DEPENDENCIES ]"
    case "$DISTRO" in
        ubuntu|debian|pop|linuxmint|elementary)
            _step "Installing via apt..."
            sudo apt update -qq
            sudo apt install -y python3 python3-gi python3-gi-cairo \
                gir1.2-gtk-4.0 gir1.2-adw-1 python3-requests python3-dotenv \
                gawk curl jq rsync
            ;;
        fedora|rhel|centos)
            _step "Installing via dnf..."
            sudo dnf install -y python3 python3-gobject python3-requests \
                python3-dotenv gtk4 libadwaita gawk curl jq rsync
            ;;
        arch|manjaro|endeavouros)
            _step "Installing via pacman..."
            sudo pacman -Sy --noconfirm python python-gobject python-requests \
                python-dotenv gtk4 libadwaita gawk curl jq rsync
            ;;
        opensuse*|sles)
            _step "Installing via zypper..."
            sudo zypper install -y python3 python3-gobject python3-requests \
                python3-dotenv typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 gawk curl jq rsync
            ;;
        *)
            _err "Unknown distro: $DISTRO"
            _white "  Install manually: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1,"
            _white "  python3-requests, python3-dotenv, gawk, curl, jq, rsync"
            ;;
    esac

    if ! python_deps_ok; then
        _err "Python/GTK dependencies still missing after install."
        exit 1
    fi
}

# ── steam detection ───────────────────────────────────────────────────────────
detect_steam() {
    echo ""
    _gold "  [ STEAM ]"
    _step "Scanning for Steam library..."

    STEAM_PATHS=(
        "$HOME/.local/share/Steam"
        "$HOME/.steam/steam"
        "/mnt/games/SteamLibrary"
        "/opt/steam"
        "$HOME/Steam"
    )

    for vdf in \
        "$HOME/.local/share/Steam/steamapps/libraryfolders.vdf" \
        "$HOME/.steam/steam/steamapps/libraryfolders.vdf"; do
        if [ -f "$vdf" ]; then
            while IFS= read -r p; do
                [ -n "$p" ] && STEAM_PATHS+=("$p")
            done < <(grep -oP '"path"\s*"\K[^"]+' "$vdf" 2>/dev/null | sed 's|\\\\|/|g')
        fi
    done

    STEAM_ROOT=""
    for p in "${STEAM_PATHS[@]}"; do
        [ -z "$p" ] && continue
        if [ -d "$p/steamapps/common/DayZ" ]; then
            _ok "Found DayZ at: $p"
            STEAM_ROOT="$p"
            return
        fi
    done

    for p in "${STEAM_PATHS[@]}"; do
        [ -z "$p" ] && continue
        if [ -d "$p/steamapps" ]; then
            _ok "Found Steam library at: $p"
            STEAM_ROOT="$p"
            return
        fi
    done

    _white "  DayZ not found automatically — set the path in Settings after launch."
    STEAM_ROOT="$HOME/.local/share/Steam"
}

# ── copy files ────────────────────────────────────────────────────────────────
copy_app() {
    echo ""
    _gold "  [ INSTALL ]"
    _step "Copying files to $INSTALL_DIR ..."
    mkdir -p "$INSTALL_DIR"

    if command -v rsync >/dev/null; then
        rsync -a --delete \
            --exclude '.git' \
            --exclude '__pycache__' \
            --exclude '*.pyc' \
            "$SOURCE_DIR/" "$INSTALL_DIR/"
    else
        rm -rf "$INSTALL_DIR"
        mkdir -p "$INSTALL_DIR"
        cp -a "$SOURCE_DIR/." "$INSTALL_DIR/"
        rm -rf "$INSTALL_DIR/.git" "$INSTALL_DIR"/**/__pycache__ 2>/dev/null || true
        find "$INSTALL_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
        find "$INSTALL_DIR" -name '*.pyc' -delete 2>/dev/null || true
    fi

    chmod +x "$INSTALL_DIR/bin/"*.sh 2>/dev/null || true
    _ok "Files installed."
}

# ── write config ──────────────────────────────────────────────────────────────
write_config() {
    local launcher_path="$INSTALL_DIR/bin/dayz-launcher.sh"
    _step "Writing config..."
    mkdir -p "$HOME/.config/dzsl"

    python3 - "$CONFIG_FILE" "$STEAM_ROOT" "$launcher_path" <<'PY'
import json, os, sys

path, steam_root, launcher_path = sys.argv[1:4]
defaults = {
    "steam_root": steam_root,
    "launcher_path": launcher_path,
    "mods_dir": "",
    "profile_name": "",
    "extra_args": "",
    "extra_mods": "",
    "no_splash": True,
    "no_pause": True,
    "no_benchmark": False,
    "window_mode": False,
    "script_debug": False,
    "skip_battleye": False,
    "close_on_launch": True,
}
existing = {}
if os.path.isfile(path):
    try:
        with open(path) as f:
            existing = json.load(f)
    except Exception:
        pass
merged = {**defaults, **existing, "steam_root": steam_root, "launcher_path": launcher_path}
with open(path, "w") as f:
    json.dump(merged, f, indent=2)
PY
    _ok "Config written."
}

# ── desktop entry ─────────────────────────────────────────────────────────────
create_desktop_entry() {
    _step "Creating desktop shortcut..."
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/dzsl.desktop" << DESKEOF
[Desktop Entry]
Name=DZSL
Comment=DayZ Server List for Linux
Exec=$INSTALL_DIR/bin/dzsl.sh
Icon=$INSTALL_DIR/assets/icon.png
Path=$INSTALL_DIR
Terminal=false
Type=Application
Categories=Game;
StartupNotify=true
DESKEOF
    _ok "Desktop shortcut created."
}

# ── run ───────────────────────────────────────────────────────────────────────
install_deps
detect_steam
copy_app
write_config
create_desktop_entry

echo ""
echo -e "${Y}  ═══════════════════════════════════════════${D}"
echo -e "${Y}  DZSL installed successfully.${D}"
echo -e "${Y}  ═══════════════════════════════════════════${D}"
echo ""
_white "  Location : $INSTALL_DIR"
_white "  Run with : $INSTALL_DIR/bin/dzsl.sh"
_white "  Or find DZSL in your application menu."
echo ""
echo -e "${W}  Stay frosty, survivor.${D}"
echo ""
