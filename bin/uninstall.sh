#!/bin/bash
set -euo pipefail

BIN_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${DZSL_INSTALL_DIR:-$HOME/DZSL}"
CONFIG_DIR="$HOME/.config/dzsl"
DESKTOP="$HOME/.local/share/applications/dzsl.desktop"

_resolve() { readlink -f "$1" 2>/dev/null || echo "$1"; }
if [ "$(_resolve "$INSTALL_DIR")" = "$(_resolve "$(cd "$BIN_DIR/.." && pwd)")" ]; then
    exit 1
fi

read -p "Uninstall DZSL? [y/N] " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || exit 0

[ -f "$DESKTOP" ] && rm "$DESKTOP"
[ -d "$CONFIG_DIR" ] && rm -rf "$CONFIG_DIR"
[ -d "$INSTALL_DIR" ] && rm -rf "$INSTALL_DIR"