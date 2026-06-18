#!/bin/bash
# DZSL - DayZ Server List for Linux
# Installs dependencies, copies the app to ~/DZSL, writes config + desktop entry.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$(cd "$BIN_DIR/.." && pwd)"
INSTALL_DIR="${DZSL_INSTALL_DIR:-$HOME/DZSL}"
CONFIG_FILE="$HOME/.config/dzsl/config.json"

echo "╔══════════════════════════════════╗"
echo "║   DZSL - DayZ Server List        ║"
echo "║   Linux Installer                ║"
echo "╚══════════════════════════════════╝"
echo ""

if [ -f /etc/os-release ]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    DISTRO="${ID:-unknown}"
else
    echo "Cannot detect distro. Install dependencies manually."
    exit 1
fi

echo "Detected: ${PRETTY_NAME:-$DISTRO}"
echo "Source:   $SOURCE_DIR"
echo "Install:  $INSTALL_DIR"
echo ""

python_deps_ok() {
    python3 - <<'PY' >/dev/null 2>&1
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw  # noqa: F401
import requests  # noqa: F401
PY
}

launcher_deps_ok() {
    command -v gawk >/dev/null && command -v curl >/dev/null && command -v jq >/dev/null
}

install_deps() {
    if python_deps_ok && launcher_deps_ok; then
        echo "Dependencies already installed."
        return
    fi

    if ! command -v sudo >/dev/null; then
        echo "sudo not found. Install manually: python3, python3-gi, gir1.2-gtk-4.0,"
        echo "gir1.2-adw-1, python3-requests, gawk, curl, jq"
        exit 1
    fi

    case "$DISTRO" in
        ubuntu|debian|pop|linuxmint|elementary)
            echo "Installing dependencies (apt)..."
            sudo apt update
            sudo apt install -y python3 python3-gi python3-gi-cairo \
                gir1.2-gtk-4.0 gir1.2-adw-1 python3-requests \
                gawk curl jq rsync
            ;;
        fedora|rhel|centos)
            echo "Installing dependencies (dnf)..."
            sudo dnf install -y python3 python3-gobject python3-requests \
                gtk4 libadwaita gawk curl jq rsync
            ;;
        arch|manjaro|endeavouros)
            echo "Installing dependencies (pacman)..."
            sudo pacman -Sy --noconfirm python python-gobject python-requests \
                gtk4 libadwaita gawk curl jq rsync
            ;;
        opensuse*|sles)
            echo "Installing dependencies (zypper)..."
            sudo zypper install -y python3 python3-gobject python3-requests \
                typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 gawk curl jq rsync
            ;;
        *)
            echo "Unknown distro: $DISTRO"
            echo "Install manually: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1,"
            echo "python3-requests, gawk, curl, jq, rsync"
            ;;
    esac

    if ! python_deps_ok; then
        echo "Error: Python/GTK dependencies still missing."
        exit 1
    fi
}

detect_steam() {
    echo "Detecting Steam library..."
    STEAM_PATHS=(
        "$HOME/.local/share/Steam"
        "$HOME/.steam/steam"
        "/mnt/Storage1tb/SteamLibrary"
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
            echo "Found DayZ at: $p"
            STEAM_ROOT="$p"
            return
        fi
    done

    for p in "${STEAM_PATHS[@]}"; do
        [ -z "$p" ] && continue
        if [ -d "$p/steamapps" ]; then
            echo "Found Steam library at: $p"
            STEAM_ROOT="$p"
            return
        fi
    done

    echo "DayZ not found automatically. Set the path in Settings after launch."
    STEAM_ROOT="$HOME/.local/share/Steam"
}

copy_app() {
    echo "Installing DZSL to $INSTALL_DIR ..."
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
    echo "Installed to $INSTALL_DIR"
}

write_config() {
    local launcher_path="$INSTALL_DIR/bin/dayz-launcher.sh"
    echo "Writing config..."
    mkdir -p "$HOME/.config/dzsl"

    python3 - "$CONFIG_FILE" "$STEAM_ROOT" "$launcher_path" <<'PY'
import json, os, sys

path, steam_root, launcher_path = sys.argv[1:4]
steamcmd = os.path.expanduser("~/.config/dzsl/steamcmd/steamcmd.sh")
if not os.path.isfile(steamcmd):
    for p in ("/usr/games/steamcmd", "/usr/bin/steamcmd"):
        if os.path.isfile(p):
            steamcmd = p
            break
    else:
        steamcmd = ""
defaults = {
    "steam_root": steam_root,
    "launcher_path": launcher_path,
    "steamcmd_path": steamcmd,
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
    echo "Config written to $CONFIG_FILE"
}

create_desktop_entry() {
    echo "Creating desktop shortcut..."
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
    echo "Desktop shortcut created."
}

install_deps
detect_steam
copy_app
write_config
create_desktop_entry

echo ""
echo "✓ DZSL installed successfully!"
echo ""
echo "Installed to: $INSTALL_DIR"
echo "Run with:     $INSTALL_DIR/bin/dzsl.sh"
echo "Or find DZSL in your application menu."
echo ""