#!/bin/bash
# DZSL - DayZ Server List for Linux
# Install script - supports Ubuntu/Debian, Fedora/RHEL, Arch

set -e

echo "╔══════════════════════════════════╗"
echo "║   DZSL - DayZ Server List        ║"
echo "║   Linux Installer                ║"
echo "╚══════════════════════════════════╝"
echo ""

# Detect distro
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo "Cannot detect distro. Install dependencies manually."
    exit 1
fi

echo "Detected: $PRETTY_NAME"
echo ""

install_deps() {
    case "$DISTRO" in
        ubuntu|debian|pop|linuxmint|elementary)
            echo "Installing dependencies (apt)..."
            sudo apt update
            sudo apt install -y python3 python3-gi python3-gi-cairo \
                gir1.2-gtk-4.0 gir1.2-adw-1 python3-requests \
                libgirepository1.0-dev
            ;;
        fedora|rhel|centos)
            echo "Installing dependencies (dnf)..."
            sudo dnf install -y python3 python3-gobject python3-requests \
                gtk4 libadwaita
            ;;
        arch|manjaro|endeavouros)
            echo "Installing dependencies (pacman)..."
            sudo pacman -Sy --noconfirm python python-gobject python-requests \
                gtk4 libadwaita
            ;;
        opensuse*|sles)
            echo "Installing dependencies (zypper)..."
            sudo zypper install -y python3 python3-gobject python3-requests \
                typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1
            ;;
        *)
            echo "Unknown distro: $DISTRO"
            echo "Please install manually: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, python3-requests"
            ;;
    esac
}

detect_steam() {
    echo "Detecting Steam library..."
    STEAM_PATHS=(
        "$HOME/.local/share/Steam"
        "$HOME/.steam/steam"
        "/mnt/Storage1tb/SteamLibrary"
        "/mnt/games/SteamLibrary"
        "/opt/steam"
    )
    for p in "${STEAM_PATHS[@]}"; do
        if [ -d "$p/steamapps/common/DayZ" ]; then
            echo "Found DayZ at: $p"
            STEAM_ROOT="$p"
            return
        fi
    done
    echo "DayZ not found automatically. You can set the path in Settings."
    STEAM_ROOT="$HOME/.local/share/Steam"
}

write_config() {
    echo "Writing config..."
    mkdir -p "$HOME/.config/dzsl"
    cat > "$HOME/.config/dzsl/config.json" << CFGEOF
{
  "steam_root": "$STEAM_ROOT",
  "launcher_path": "$LAUNCHER_PATH",
  "mods_dir": "",
  "profile_name": "",
  "extra_args": "",
  "no_splash": true,
  "no_pause": true,
  "no_benchmark": false,
  "window_mode": false,
  "script_debug": false,
  "skip_battleye": false
}
CFGEOF
    echo "Config written to ~/.config/dzsl/config.json"
}

create_desktop_entry() {
    echo "Creating desktop shortcut..."
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/dzsl.desktop" << DESKEOF
[Desktop Entry]
Name=DZSL
Comment=DayZ Server List for Linux
Exec=python3 $SCRIPT_DIR/main.py
Icon=$SCRIPT_DIR/assets/icon.png
Terminal=false
Type=Application
Categories=Game;
StartupNotify=true
DESKEOF
    echo "Desktop shortcut created."
}

# Run
install_deps
detect_steam
detect_launcher
write_config
create_desktop_entry

echo ""
echo "✓ DZSL installed successfully!"
echo ""
echo "Run with:  python3 $(pwd)/main.py"
echo "Or find DZSL in your application menu."
echo ""
