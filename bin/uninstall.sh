#!/bin/bash
set -euo pipefail

INSTALL_DIR="${DZSL_INSTALL_DIR:-$HOME/DZSL}"
CONFIG_DIR="$HOME/.config/dzsl"
DESKTOP="$HOME/.local/share/applications/dzsl.desktop"

# ── colours ───────────────────────────────────────────────────────────────────
R='\033[0;31m'
Y='\033[0;33m'
W='\033[0;37m'
D='\033[0m'

_gold()  { echo -e "${Y}$*${D}"; }
_white() { echo -e "${W}$*${D}"; }
_ok()    { echo -e "${Y}  ✓${W} $*${D}"; }
_step()  { echo -e "${Y}  ›${W} $*${D}"; }
_err()   { echo -e "${R}  ✗ $*${D}"; }

# ── safety check ──────────────────────────────────────────────────────────────
_resolve() { readlink -f "$1" 2>/dev/null || echo "$1"; }
TARGET="$(_resolve "$INSTALL_DIR")"

if [ "$TARGET" = "$(_resolve "/")" ] || [ "$TARGET" = "$(_resolve "$HOME")" ]; then
    _err "Unsafe install path ($INSTALL_DIR) — aborting."
    exit 1
fi

clear

# ── scene: grim survivor in the rain ─────────────────────────────────────────
BL='\033[0;34m'; DK='\033[1;30m'; GR='\033[0;37m'
printf "${BL}  ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │\n"
printf "   ╲│  ╲│  ╲│  ╲│  ╲│  ╲│  ╲│  ╲│  ╲│  ╲│  ╲│  ╲│  ╲│ \n"
printf "${DK}  ▓░▒▓░▒░▓▒░▓░▒▓░▒░▓▒░▓░▒▓░▒░▓▒░▓░▒▓░▒░▓▒░▓░▒▓░▒░▓▒░▓░▒\n"
printf "  ░▒▓▒░░▓░▒░▒▓▒░░▓░▒░▒▓▒░░▓░▒░▒▓▒░░▓░▒░▒▓▒░░▓░▒░▒▓▒░░▓░▒░\n"
printf "${BL}  ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │\n"
printf "${GR}               .──────.\n"
printf "              /  ○     \\──── pistol\n"
printf "              '────────'\n"
printf "${DK}             ╔══════════╗\n"
printf "            ╔╝  ██████  ╚╗\n"
printf "           ╔╝   ██████   ╚╗   ╲\n"
printf "           ║    ██████    ║    ╲╲\n"
printf "           ╚══════════════╝\n"
printf "${BL}  ╲ │ ╲${DK}░▒░▓▒░░▓░▒░▒▓▒░░▓░▒░▒▓▒${BL}╲ │ ╲ │ ╲ │ ╲ │ ╲ │ ╲ │\n"
printf "${DK}  ▓▓▓▒▒░░▓▓▓▒▒░░▓▓▓▒▒░░▓▓▓▒▒░░▓▓▓▒▒░░▓▓▓▒▒░░▓▓▓▒▒░░▓▓▓▒▒${D}\n"
echo ""

echo -e "${R}"
cat << 'BANNER'
  ██████╗ ███████╗███████╗██╗
  ██╔══██╗   ███╔╝██╔════╝██║
  ██║  ██║  ███╔╝ ███████╗██║
  ██║  ██║ ███╔╝  ╚════██║██║
  ██████╔╝███████╗███████║███████╗
  ╚═════╝ ╚══════╝╚══════╝╚══════╝
BANNER
echo -e "${W}  DayZ Server List for Linux${D}"
echo -e "${R}  ─────────────────────────────────────────${D}"
echo -e "${W}  UNINSTALLER${D}"
echo ""

_white "  The following will be removed:"
echo ""
_white "    $INSTALL_DIR"
_white "    $CONFIG_DIR"
_white "    $DESKTOP"
echo ""
echo -e "${R}  This cannot be undone.${D}"
echo ""

read -p "$(echo -e "${Y}  Are you sure? [y/N] ${D}")" confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo ""
    _white "  Cancelled. DZSL lives to fight another day."
    echo ""
    exit 0
fi

echo ""
_gold "  [ REMOVING ]"

if [ -f "$DESKTOP" ]; then
    rm "$DESKTOP"
    _ok "Desktop shortcut removed."
else
    _white "  No desktop shortcut found."
fi

if [ -d "$CONFIG_DIR" ]; then
    rm -rf "$CONFIG_DIR"
    _ok "Config removed: $CONFIG_DIR"
else
    _white "  No config at $CONFIG_DIR"
fi

if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    _ok "App removed: $INSTALL_DIR"
else
    _white "  No install found at $INSTALL_DIR"
fi

echo ""
echo -e "${R}  ═══════════════════════════════════════════${D}"
echo -e "${W}  DZSL has been removed.${D}"
echo -e "${R}  ═══════════════════════════════════════════${D}"
echo ""
echo -e "${W}  You didn't make it this time, survivor.${D}"
echo ""
